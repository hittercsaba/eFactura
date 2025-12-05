#!/usr/bin/env python3
"""Test unsigned XML extraction and parsing"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Invoice
from app.services.invoice_service import InvoiceService

app = create_app(os.getenv('FLASK_ENV', 'default'))

with app.app_context():
    # Get invoice with missing total_amount
    invoice = Invoice.query.filter(Invoice.total_amount.is_(None)).first()
    
    if not invoice:
        print("No invoice with missing total_amount found")
        sys.exit(0)
    
    print(f"Testing Invoice ID: {invoice.id}, ANAF ID: {invoice.anaf_id}")
    print("="*80)
    
    # Check if ZIP file exists
    from app.services.storage_service import InvoiceStorageService
    has_zip = False
    if invoice.zip_file_path:
        has_zip = InvoiceStorageService.zip_file_exists(invoice.zip_file_path)
        print(f"\n0. ZIP File Status:")
        print(f"   ZIP Path: {invoice.zip_file_path}")
        print(f"   ZIP Exists: {'✓ Yes' if has_zip else '✗ No'}")
    
    # Test parsing current XML
    print("\n1. Testing current XML parsing:")
    parsed = InvoiceService.parse_xml_to_json(invoice.xml_content)
    
    print(f"   Total Amount: {parsed.get('total_amount')}")
    print(f"   Currency: {parsed.get('currency')}")
    print(f"   Issuer Name: {parsed.get('issuer_name')}")
    print(f"   Receiver Name: {parsed.get('receiver_name')}")
    
    # Check if XML is signed or unsigned
    if invoice.xml_content.strip().startswith('<Signature') or '<Signature' in invoice.xml_content[:200]:
        print("\n   ⚠️  WARNING: Current XML appears to be SIGNED (has Signature wrapper)")
        if has_zip:
            print("   ✓ ZIP file exists - reparse will extract unsigned XML from ZIP")
        else:
            print("   ⚠️  No ZIP file - cannot extract unsigned XML. Need to re-sync.")
    else:
        print("\n   ✓ XML appears to be UNSIGNED (Invoice root element)")
    
    # Test reparsing
    print("\n2. Testing reparse (will extract unsigned XML from ZIP if available):")
    updated = InvoiceService.reparse_invoice(invoice)
    if updated:
        db.session.commit()
        print(f"   ✓ Invoice updated!")
        print(f"   Total Amount: {invoice.total_amount}")
        print(f"   Currency: {invoice.currency}")
        print(f"   Issuer Name: {invoice.issuer_name}")
        print(f"   Receiver Name: {invoice.receiver_name}")
        
        # Check if XML was updated to unsigned
        if invoice.xml_content.strip().startswith('<Invoice') or (invoice.xml_content.strip().startswith('<?xml') and '<Invoice' in invoice.xml_content[:500] and '<Signature' not in invoice.xml_content[:500]):
            print(f"   ✓ XML content updated to unsigned Invoice XML")
    else:
        print(f"   ✗ No updates made")
        print(f"   Invoice still incomplete: {InvoiceService.is_invoice_incomplete(invoice)}")
