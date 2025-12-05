#!/usr/bin/env python3
"""
Script to re-download invoices from ANAF and extract unsigned XML.
This is needed if invoices don't have ZIP files saved or have signed XML stored.

Usage:
    python redownload_invoices_from_anaf.py [--company-id COMPANY_ID] [--invoice-id INVOICE_ID] [--all] [--verbose]
"""

import sys
import os
import zipfile
import io

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Invoice, Company, User
from app.services.invoice_service import InvoiceService
from app.services.anaf_service import ANAFService
from app.services.storage_service import InvoiceStorageService
from flask import current_app

def check_invoice_needs_redownload(invoice):
    """
    Check if invoice needs to be re-downloaded from ANAF.
    
    Returns:
        tuple: (needs_redownload: bool, reason: str)
    """
    # Check if ZIP file exists
    has_zip = False
    if invoice.zip_file_path:
        has_zip = InvoiceStorageService.zip_file_exists(invoice.zip_file_path)
    
    # Check if XML content is signed (wrong)
    xml_is_signed = False
    if invoice.xml_content:
        stripped = invoice.xml_content.strip()
        xml_is_signed = stripped.startswith('<Signature') or '<Signature' in stripped[:200]
    
    # Need re-download if:
    # 1. No ZIP file saved
    # 2. ZIP file doesn't exist on disk
    # 3. XML content is signed (should be unsigned)
    if not invoice.zip_file_path:
        return True, "No ZIP file path in database"
    elif not has_zip:
        return True, f"ZIP file not found on disk: {invoice.zip_file_path}"
    elif xml_is_signed:
        return True, "XML content is signed (should be unsigned)"
    else:
        return False, "ZIP file exists and XML is unsigned"

def redownload_invoice(invoice_id, verbose=False):
    """Re-download a specific invoice from ANAF and extract unsigned XML"""
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        print(f"Invoice {invoice_id} not found")
        return False
    
    # Get company and user
    company = Company.query.get(invoice.company_id)
    if not company:
        print(f"Company {invoice.company_id} not found for invoice {invoice_id}")
        return False
    
    user = User.query.get(company.user_id)
    if not user:
        print(f"User {company.user_id} not found for company {company.id}")
        return False
    
    print(f"\nProcessing invoice {invoice.id} (ANAF ID: {invoice.anaf_id})...")
    
    # Check if needs re-download
    needs_redownload, reason = check_invoice_needs_redownload(invoice)
    
    if verbose:
        print(f"  ZIP file path: {invoice.zip_file_path or 'None'}")
        if invoice.zip_file_path:
            zip_exists = InvoiceStorageService.zip_file_exists(invoice.zip_file_path)
            print(f"  ZIP file exists: {'Yes' if zip_exists else 'No'}")
        
        if invoice.xml_content:
            stripped = invoice.xml_content.strip()
            xml_is_signed = stripped.startswith('<Signature') or '<Signature' in stripped[:200]
            print(f"  XML is signed: {'Yes' if xml_is_signed else 'No (unsigned)'}")
        
        print(f"  Needs re-download: {needs_redownload} ({reason})")
    
    if not needs_redownload:
        print(f"  ✓ Invoice {invoice.id} already has unsigned XML - skipping")
        return False
    
    # Re-download from ANAF
    try:
        print(f"  Downloading from ANAF...")
        anaf_service = ANAFService(user.id)
        file_content = anaf_service.descarcare_factura(invoice.anaf_id)
        
        if not file_content:
            print(f"  ✗ Failed to download invoice {invoice.id} from ANAF")
            return False
        
        # Check if it's a ZIP file
        if not file_content.startswith(b'PK\x03\x04'):
            print(f"  ✗ Downloaded content is not a ZIP file for invoice {invoice.id}")
            return False
        
        # Extract unsigned XML from ZIP
        with zipfile.ZipFile(io.BytesIO(file_content)) as zip_file:
            xml_content, xml_filename = InvoiceService.extract_unsigned_xml_from_zip(zip_file)
            
            if not xml_content:
                print(f"  ✗ Failed to extract unsigned XML from ZIP for invoice {invoice.id}")
                return False
            
            if verbose:
                print(f"  ✓ Extracted unsigned XML from {xml_filename}")
            
            # Verify it's unsigned
            if xml_content.strip().startswith('<Signature') or '<Signature' in xml_content[:200]:
                print(f"  ✗ ERROR: Extracted XML is still signed for invoice {invoice.id}")
                return False
        
        # Update invoice with unsigned XML
        invoice.xml_content = xml_content
        
        # Save ZIP file
        try:
            zip_path = InvoiceStorageService.save_zip_file(
                company_id=invoice.company_id,
                invoice_id=invoice.anaf_id,
                zip_content=file_content,
                invoice_date=invoice.invoice_date
            )
            invoice.zip_file_path = zip_path
            if verbose:
                print(f"  ✓ Saved ZIP file: {zip_path}")
        except Exception as e:
            current_app.logger.warning(f"Error saving ZIP file for invoice {invoice.id}: {str(e)}")
            print(f"  ⚠️  Warning: Failed to save ZIP file: {str(e)}")
        
        # Commit ZIP and XML content update first
        db.session.commit()
        
        # Now parse and update invoice fields from unsigned XML
        if verbose:
            print(f"  Parsing unsigned XML to extract invoice fields...")
        
        try:
            parsed_data = InvoiceService.parse_xml_to_json(xml_content)
            supplier_name, supplier_cif, invoice_date_from_xml, total_amount, currency, \
            issuer_name, receiver_name, issuer_vat_id, receiver_vat_id = \
                InvoiceService.extract_invoice_fields(parsed_data)
            
            fields_updated = False
            
            # Update missing fields (treat "-" as missing)
            if InvoiceService._is_empty_or_dash(invoice.issuer_name) and issuer_name:
                invoice.issuer_name = issuer_name
                fields_updated = True
            
            if InvoiceService._is_empty_or_dash(invoice.receiver_name) and receiver_name:
                invoice.receiver_name = receiver_name
                fields_updated = True
            
            if InvoiceService._is_empty_or_dash(invoice.cif_emitent) and issuer_vat_id:
                invoice.cif_emitent = issuer_vat_id
                fields_updated = True
            
            if InvoiceService._is_empty_or_dash(invoice.cif_beneficiar) and receiver_vat_id:
                invoice.cif_beneficiar = receiver_vat_id
                fields_updated = True
            
            if invoice.total_amount is None and total_amount is not None:
                invoice.total_amount = total_amount
                fields_updated = True
            
            if InvoiceService._is_empty_or_dash(invoice.currency) and currency:
                invoice.currency = currency
                fields_updated = True
            
            if InvoiceService._is_empty_or_dash(invoice.supplier_name) and issuer_name:
                invoice.supplier_name = issuer_name
                fields_updated = True
            
            if InvoiceService._is_empty_or_dash(invoice.supplier_cif) and issuer_vat_id:
                invoice.supplier_cif = issuer_vat_id
                fields_updated = True
            
            if fields_updated:
                db.session.commit()
                if verbose:
                    print(f"  ✓ Updated invoice fields:")
                    print(f"    - Total Amount: {invoice.total_amount} {invoice.currency or ''}")
                    print(f"    - Issuer Name: {invoice.issuer_name}")
                    print(f"    - Receiver Name: {invoice.receiver_name}")
        except Exception as e:
            current_app.logger.warning(f"Error parsing unsigned XML for invoice {invoice.id}: {str(e)}")
            if verbose:
                print(f"  ⚠️  Warning: Failed to parse invoice fields: {str(e)}")
        
        print(f"  ✓ Invoice {invoice.id} updated with unsigned XML")
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error re-downloading invoice {invoice.id}: {str(e)}", exc_info=True)
        print(f"  ✗ Error: {str(e)}")
        db.session.rollback()
        return False

def redownload_company_invoices(company_id, verbose=False):
    """Re-download all invoices for a specific company"""
    company = Company.query.get(company_id)
    if not company:
        print(f"Company {company_id} not found")
        return
    
    print(f"Re-downloading invoices for company {company_id} ({company.name})...")
    
    invoices = Invoice.query.filter_by(company_id=company_id).all()
    print(f"Found {len(invoices)} invoices")
    
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    
    for invoice in invoices:
        needs_redownload, _ = check_invoice_needs_redownload(invoice)
        
        if needs_redownload:
            if redownload_invoice(invoice.id, verbose=verbose):
                updated_count += 1
            else:
                failed_count += 1
        else:
            skipped_count += 1
    
    print(f"\n✓ Updated {updated_count} invoices")
    if skipped_count > 0:
        print(f"  Skipped {skipped_count} invoices (already have unsigned XML)")
    if failed_count > 0:
        print(f"✗ Failed {failed_count} invoices")

def redownload_all_invoices(verbose=False):
    """Re-download all invoices that need it"""
    print("Checking all invoices for re-download...")
    
    all_invoices = Invoice.query.all()
    print(f"Found {len(all_invoices)} total invoices")
    
    needs_redownload = []
    for invoice in all_invoices:
        needs, reason = check_invoice_needs_redownload(invoice)
        if needs:
            needs_redownload.append((invoice, reason))
    
    print(f"Found {len(needs_redownload)} invoices that need re-download")
    
    if not needs_redownload:
        print("✓ All invoices already have unsigned XML - nothing to do")
        return
    
    updated_count = 0
    failed_count = 0
    
    for invoice, reason in needs_redownload:
        if verbose:
            print(f"\nReason: {reason}")
        
        if redownload_invoice(invoice.id, verbose=verbose):
            updated_count += 1
        else:
            failed_count += 1
    
    print(f"\n✓ Updated {updated_count} invoices")
    if failed_count > 0:
        print(f"✗ Failed {failed_count} invoices")
    
    # After re-downloading, suggest reparsing
    if updated_count > 0:
        print(f"\n💡 Tip: Run 'python reparse_invoices.py --all --verbose' to parse and update invoice fields")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Re-download invoices from ANAF and extract unsigned XML')
    parser.add_argument('--company-id', type=int, help='Re-download invoices for specific company')
    parser.add_argument('--invoice-id', type=int, help='Re-download specific invoice')
    parser.add_argument('--all', action='store_true', help='Re-download all invoices that need it')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    
    args = parser.parse_args()
    
    # Create app context
    app = create_app(os.getenv('FLASK_ENV', 'default'))
    
    with app.app_context():
        if args.invoice_id:
            redownload_invoice(args.invoice_id, verbose=args.verbose)
        elif args.company_id:
            redownload_company_invoices(args.company_id, verbose=args.verbose)
        elif args.all:
            redownload_all_invoices(verbose=args.verbose)
        else:
            parser.print_help()
