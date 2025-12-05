#!/usr/bin/env python3
"""Dump full XML to file for inspection"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Invoice

app = create_app(os.getenv('FLASK_ENV', 'default'))

with app.app_context():
    invoice = Invoice.query.filter(Invoice.total_amount.is_(None)).first()
    
    if not invoice:
        print("No invoice found")
        sys.exit(0)
    
    print(f"Dumping XML for Invoice ID: {invoice.id}, ANAF ID: {invoice.anaf_id}")
    print(f"XML length: {len(invoice.xml_content)} characters")
    
    # Write to file
    output_file = f"/tmp/invoice_{invoice.id}_xml.xml"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(invoice.xml_content)
    
    print(f"XML saved to: {output_file}")
    print(f"\nFirst 1000 characters:")
    print("="*80)
    print(invoice.xml_content[:1000])
    print("\n...")
    print("\nLast 500 characters:")
    print("="*80)
    print(invoice.xml_content[-500:])
