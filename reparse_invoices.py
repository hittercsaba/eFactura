#!/usr/bin/env python3
"""
Manual script to reparse invoices with missing fields.
This can be used for testing or to immediately fix existing invoices.

Usage:
    python reparse_invoices.py [--company-id COMPANY_ID] [--invoice-id INVOICE_ID] [--all]
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Invoice, Company
from app.services.invoice_service import InvoiceService
from flask import current_app

def reparse_invoice(invoice_id, verbose=False):
    """Reparse a specific invoice"""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        print(f"Invoice {invoice_id} not found")
        return False
    
    print(f"\nReparsing invoice {invoice_id} (ANAF ID: {invoice.anaf_id})...")
    
    if verbose:
        print(f"  Current state:")
        print(f"    - Total Amount: {invoice.total_amount}")
        print(f"    - Currency: {invoice.currency}")
        print(f"    - Has XML: {'Yes' if invoice.xml_content else 'No'}")
    
    if not invoice.xml_content:
        print(f"✗ Invoice {invoice_id} has no XML content - cannot reparse")
        return False
    
    # Try parsing first to see what we get
    if verbose:
        parsed_data = InvoiceService.parse_xml_to_json(invoice.xml_content)
        print(f"\n  Parsed data:")
        print(f"    - Total Amount: {parsed_data.get('total_amount')}")
        print(f"    - Currency: {parsed_data.get('currency')}")
        print(f"    - Issuer Name: {parsed_data.get('issuer_name')}")
        print(f"    - Receiver Name: {parsed_data.get('receiver_name')}")
        if parsed_data.get('error'):
            print(f"    - Error: {parsed_data.get('error')}")
    
    updated = InvoiceService.reparse_invoice(invoice)
    if updated:
        db.session.commit()
        print(f"✓ Invoice {invoice_id} updated successfully")
        print(f"  - Issuer Name: {invoice.issuer_name}")
        print(f"  - Receiver Name: {invoice.receiver_name}")
        print(f"  - Total Amount: {invoice.total_amount}")
        print(f"  - Currency: {invoice.currency}")
        return True
    else:
        print(f"✗ Invoice {invoice_id} - no updates needed or XML parsing failed")
        if verbose:
            print(f"  Invoice is incomplete: {InvoiceService.is_invoice_incomplete(invoice)}")
        return False

def reparse_company_invoices(company_id):
    """Reparse all invoices for a specific company"""
    company = Company.query.get(company_id)
    if not company:
        print(f"Company {company_id} not found")
        return
    
    print(f"Reparsing invoices for company {company_id} ({company.name})...")
    
    invoices = Invoice.query.filter_by(company_id=company_id).all()
    print(f"Found {len(invoices)} invoices")
    
    updated_count = 0
    for invoice in invoices:
        if InvoiceService.is_invoice_incomplete(invoice):
            if InvoiceService.reparse_invoice(invoice):
                updated_count += 1
    
    if updated_count > 0:
        db.session.commit()
        print(f"✓ Updated {updated_count} invoices")
    else:
        print("✗ No invoices needed updating")

def reparse_all_invoices(verbose=False):
    """Reparse all invoices with missing fields"""
    print("Reparsing all invoices with missing fields...")
    
    # Get all invoices and filter using is_invoice_incomplete() which handles "-" values
    all_invoices = Invoice.query.all()
    incomplete_invoices = [inv for inv in all_invoices if InvoiceService.is_invoice_incomplete(inv)]
    
    print(f"Found {len(incomplete_invoices)} invoices with missing fields")
    
    updated_count = 0
    failed_count = 0
    
    for invoice in incomplete_invoices:
        if verbose:
            print(f"\nProcessing invoice {invoice.id} (ANAF: {invoice.anaf_id})")
        
        if reparse_invoice(invoice.id, verbose=verbose):
            updated_count += 1
        else:
            failed_count += 1
            # Check if it's actually incomplete
            if InvoiceService.is_invoice_incomplete(invoice):
                if verbose:
                    print(f"  Still incomplete - XML parsing may have failed")
    
    if updated_count > 0:
        print(f"\n✓ Updated {updated_count} invoices")
    if failed_count > 0:
        print(f"✗ {failed_count} invoices could not be updated")
        print(f"  Run 'python diagnose_invoice_xml.py --all' to see details")
    
    if updated_count == 0 and failed_count == 0:
        print("✗ No invoices needed updating")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Reparse invoices to fill missing fields')
    parser.add_argument('--company-id', type=int, help='Reparse invoices for specific company')
    parser.add_argument('--invoice-id', type=int, help='Reparse specific invoice')
    parser.add_argument('--all', action='store_true', help='Reparse all invoices with missing fields')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    
    args = parser.parse_args()
    
    # Create app context
    app = create_app(os.getenv('FLASK_ENV', 'default'))
    
    with app.app_context():
        if args.invoice_id:
            reparse_invoice(args.invoice_id, verbose=args.verbose)
        elif args.company_id:
            reparse_company_invoices(args.company_id)
        elif args.all:
            reparse_all_invoices(verbose=args.verbose)
        else:
            parser.print_help()
