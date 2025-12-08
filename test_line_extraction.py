#!/usr/bin/env python3
"""Test invoice line extraction with actual InvoiceService"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.invoice_service import InvoiceService
from pprint import pprint

# Read the example XML
xml_file = '/Users/csabahitter/Downloads/invoice_6290533787/5750668021.xml'

print("="*80)
print("Testing Invoice Line Extraction")
print("="*80)

try:
    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    print(f"\n✓ XML file loaded ({len(xml_content)} characters)")
    print(f"XML starts with: {xml_content[:100]}...")
    
    # Extract line items using the actual service method
    print("\n" + "-"*80)
    print("Extracting line items...")
    print("-"*80)
    
    line_items = InvoiceService.extract_invoice_line_items(xml_content)
    
    print(f"\n✓ Extraction completed")
    print(f"Number of line items found: {len(line_items)}")
    
    if line_items:
        print("\n" + "="*80)
        print("EXTRACTED LINE ITEMS:")
        print("="*80)
        for i, item in enumerate(line_items, 1):
            print(f"\nLine Item {i}:")
            pprint(item, width=120, depth=10)
    else:
        print("\n✗ No line items extracted!")
        print("\nLet's debug the XML structure...")
        
        # Try to see what's in the XML
        import xmltodict
        invoice_dict = xmltodict.parse(xml_content, process_namespaces=True, namespaces={})
        
        print("\nRoot keys:", list(invoice_dict.keys()))
        
        invoice_root = invoice_dict.get('Invoice', invoice_dict)
        if isinstance(invoice_root, dict):
            print("\nInvoice root keys (first 30):")
            keys = list(invoice_root.keys())[:30]
            for key in keys:
                print(f"  - {key}")
            
            # Check for InvoiceLine
            if 'InvoiceLine' in invoice_root:
                print("\n✓ Found 'InvoiceLine' key!")
                il = invoice_root['InvoiceLine']
                print(f"  Type: {type(il)}")
                if isinstance(il, dict):
                    print(f"  Keys: {list(il.keys())}")
                    print("\n  Full structure:")
                    pprint(il, depth=5, width=120)
                elif isinstance(il, list):
                    print(f"  List with {len(il)} items")
                    if il:
                        print(f"  First item keys: {list(il[0].keys())}")
                        pprint(il[0], depth=5, width=120)
            else:
                print("\n✗ 'InvoiceLine' not found in invoice_root")
                # Search for keys containing 'line'
                line_keys = [k for k in invoice_root.keys() if 'line' in k.lower() or 'Line' in k]
                if line_keys:
                    print(f"  But found keys with 'line': {line_keys}")
                    for key in line_keys:
                        print(f"\n  Checking '{key}':")
                        val = invoice_root[key]
                        print(f"    Type: {type(val)}")
                        if isinstance(val, dict):
                            print(f"    Keys: {list(val.keys())[:10]}")
                        elif isinstance(val, list) and val:
                            print(f"    List with {len(val)} items")
                            if isinstance(val[0], dict):
                                print(f"    First item keys: {list(val[0].keys())[:10]}")
    
except FileNotFoundError:
    print(f"✗ XML file not found: {xml_file}")
    print("\nPlease check the file path.")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
