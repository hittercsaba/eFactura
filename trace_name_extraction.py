#!/usr/bin/env python3
"""Trace how issuer_name is extracted to understand the XML structure"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Invoice
from app.services.invoice_service import InvoiceService
import xmltodict

app = create_app(os.getenv('FLASK_ENV', 'default'))

with app.app_context():
    invoice = Invoice.query.filter(Invoice.total_amount.is_(None)).first()
    
    if not invoice:
        print("No invoice found")
        sys.exit(0)
    
    print(f"Invoice ID: {invoice.id}")
    print(f"DB Issuer Name: {invoice.issuer_name}")
    print(f"DB Receiver Name: {invoice.receiver_name}")
    print("="*80)
    
    # Check json_content first
    if invoice.json_content:
        print("\n✓ Invoice has json_content")
        import json
        json_str = json.dumps(invoice.json_content, indent=2)
        print(f"json_content length: {len(json_str)} chars")
        print(f"\nFirst 1000 chars of json_content:")
        print(json_str[:1000])
        
        # Check if amounts are in json_content
        if isinstance(invoice.json_content, dict):
            def find_in_json(obj, path="", depth=0):
                if depth > 5:
                    return
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if any(word in str(k).lower() for word in ['amount', 'total', 'currency']):
                            print(f"\nFound in json_content at {path}.{k}:")
                            print(f"  Type: {type(v)}")
                            print(f"  Value: {v}")
                        if isinstance(v, dict):
                            find_in_json(v, f"{path}.{k}" if path else k, depth + 1)
            
            print("\nSearching json_content for amount/currency:")
            find_in_json(invoice.json_content)
    
    # Now try parsing XML
    print(f"\n{'='*80}")
    print("Parsing XML to see structure:")
    print(f"{'='*80}")
    
    invoice_dict = xmltodict.parse(invoice.xml_content)
    
    print(f"\nTop-level keys: {list(invoice_dict.keys())}")
    
    # Try to extract names using our parser
    parsed = InvoiceService.parse_xml_to_json(invoice.xml_content)
    
    print(f"\nParser Results:")
    print(f"  Issuer Name: {parsed.get('issuer_name')}")
    print(f"  Receiver Name: {parsed.get('receiver_name')}")
    print(f"  Total Amount: {parsed.get('total_amount')}")
    print(f"  Currency: {parsed.get('currency')}")
    
    if parsed.get('error'):
        print(f"\nParser Error: {parsed.get('error')}")
