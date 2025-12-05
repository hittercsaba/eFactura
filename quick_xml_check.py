#!/usr/bin/env python3
"""
Quick check - see actual XML and trace how names are extracted
"""

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
    print(f"Issuer Name (from DB): {invoice.issuer_name}")
    print(f"Receiver Name (from DB): {invoice.receiver_name}")
    print("="*80)
    
    # Parse XML
    invoice_dict = xmltodict.parse(invoice.xml_content)
    
    print(f"\nTop-level keys: {list(invoice_dict.keys())}")
    
    # Since issuer_name is extracted, let's see what the parser returns
    parsed = InvoiceService.parse_xml_to_json(invoice.xml_content)
    
    print(f"\nParser Results:")
    print(f"  Issuer Name: {parsed.get('issuer_name')}")
    print(f"  Receiver Name: {parsed.get('receiver_name')}")
    print(f"  Total Amount: {parsed.get('total_amount')}")
    print(f"  Currency: {parsed.get('currency')}")
    
    # Check raw dict structure
    print(f"\n{'='*80}")
    print("Exploring XML dict structure:")
    print(f"{'='*80}")
    
    def explore_dict(obj, path="", max_depth=3, current_depth=0):
        """Explore dictionary structure"""
        if current_depth > max_depth:
            return
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                
                # Look for interesting keys
                if any(word in str(key).lower() for word in ['amount', 'total', 'monetary', 'payable', 'currency', 'invoice']):
                    print(f"\n{current_path}: {type(value)}")
                    if isinstance(value, dict):
                        print(f"  Keys: {list(value.keys())[:10]}")
                        if '#text' in value:
                            print(f"  Value: {value.get('#text')}")
                        if '@currencyID' in value:
                            print(f"  Currency: {value.get('@currencyID')}")
                    elif isinstance(value, str):
                        print(f"  Value: {value[:100]}")
                
                # Also look for supplier/customer to trace the name extraction
                if any(word in str(key).lower() for word in ['supplier', 'customer', 'party', 'seller', 'buyer']):
                    print(f"\n{current_path}: {type(value)}")
                    if isinstance(value, dict):
                        print(f"  Keys: {list(value.keys())[:10]}")
                
                # Recurse
                if isinstance(value, dict) and current_depth < max_depth:
                    explore_dict(value, current_path, max_depth, current_depth + 1)
                elif isinstance(value, list) and value and current_depth < max_depth:
                    for i, item in enumerate(value[:2]):  # Only first 2 items
                        if isinstance(item, dict):
                            explore_dict(item, f"{current_path}[{i}]", max_depth, current_depth + 1)
    
    explore_dict(invoice_dict)
    
    # Show a snippet of the XML
    print(f"\n{'='*80}")
    print("XML Snippet (first 500 chars):")
    print(f"{'='*80}")
    print(invoice.xml_content[:500])
