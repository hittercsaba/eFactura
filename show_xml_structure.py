#!/usr/bin/env python3
"""
Quick script to show XML structure for debugging
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Invoice
import re

app = create_app(os.getenv('FLASK_ENV', 'default'))

with app.app_context():
    # Get first invoice with missing total_amount
    invoice = Invoice.query.filter(Invoice.total_amount.is_(None)).first()
    
    if not invoice:
        print("No invoices with missing total_amount found")
        sys.exit(0)
    
    print(f"\nInvoice ID: {invoice.id}, ANAF ID: {invoice.anaf_id}")
    print("="*80)
    
    if not invoice.xml_content:
        print("No XML content")
        sys.exit(0)
    
    xml = invoice.xml_content
    
    # Find and show Invoice opening tag
    invoice_match = re.search(r'<[^>]*Invoice[^>]*>', xml, re.IGNORECASE)
    if invoice_match:
        print(f"\nInvoice opening tag found at position {invoice_match.start()}:")
        print(invoice_match.group(0))
    
    # Find LegalMonetaryTotal
    lmt_match = re.search(r'<[^>]*LegalMonetaryTotal[^>]*>', xml, re.IGNORECASE)
    if lmt_match:
        print(f"\n✓ LegalMonetaryTotal opening tag found at position {lmt_match.start()}:")
        print(lmt_match.group(0))
        
        # Show the section
        start_pos = lmt_match.start()
        # Find the closing tag
        tag_name = re.search(r'<([^:>]+:)?LegalMonetaryTotal', xml[start_pos:start_pos+100], re.IGNORECASE)
        if tag_name:
            tag = tag_name.group(0).replace('<', '').replace('>', '')
            # Find closing tag
            closing_pattern = f'</{tag}>'
            end_match = re.search(closing_pattern, xml[start_pos:start_pos+2000], re.IGNORECASE)
            if end_match:
                end_pos = start_pos + end_match.end()
                print(f"\nLegalMonetaryTotal section (first 1000 chars):")
                print(xml[start_pos:min(start_pos+1000, end_pos)])
    else:
        print("\n✗ LegalMonetaryTotal tag NOT FOUND in XML")
    
    # Search for amount-related tags
    print(f"\n{'='*80}")
    print("Searching for amount-related tags:")
    print(f"{'='*80}")
    
    amount_tags = ['PayableAmount', 'TaxInclusiveAmount', 'TaxExclusiveAmount', 
                   'TotalAmount', 'InvoiceTotal', 'Amount', 'Total']
    
    for tag in amount_tags:
        matches = list(re.finditer(rf'<[^>]*{tag}[^>]*>', xml, re.IGNORECASE))
        if matches:
            print(f"\n✓ Found {len(matches)} occurrence(s) of {tag}:")
            for i, match in enumerate(matches[:3]):  # Show first 3
                # Show context
                start = max(0, match.start() - 100)
                end = min(len(xml), match.end() + 200)
                context = xml[start:end]
                print(f"\n  Occurrence {i+1} (position {match.start()}):")
                print(f"  {context}")
