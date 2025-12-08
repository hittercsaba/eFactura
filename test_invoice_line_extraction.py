#!/usr/bin/env python3
"""Test script to debug invoice line extraction"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import xmltodict
from pprint import pprint

# Read the example XML
xml_file = '/Users/csabahitter/Downloads/invoice_6290533787/5750668021.xml'
with open(xml_file, 'r', encoding='utf-8') as f:
    xml_content = f.read()

print("="*80)
print("Testing XML Parsing")
print("="*80)

# Test 1: Parse with process_namespaces=True
print("\n1. Parsing with process_namespaces=True")
print("-"*80)
try:
    invoice_dict = xmltodict.parse(xml_content, process_namespaces=True, namespaces={})
    print("✓ Parsed successfully")
    print(f"Root keys: {list(invoice_dict.keys())}")
    
    # Find Invoice root
    invoice_root = invoice_dict.get('Invoice', invoice_dict)
    print(f"\nInvoice root type: {type(invoice_root)}")
    if isinstance(invoice_root, dict):
        print(f"Invoice root keys (first 20): {list(invoice_root.keys())[:20]}")
        
        # Check for InvoiceLine
        if 'InvoiceLine' in invoice_root:
            print("\n✓ Found 'InvoiceLine' key directly")
            il = invoice_root['InvoiceLine']
            print(f"  Type: {type(il)}")
            if isinstance(il, list):
                print(f"  List length: {len(il)}")
                if il:
                    print(f"  First item keys: {list(il[0].keys())[:15]}")
            elif isinstance(il, dict):
                print(f"  Dict keys: {list(il.keys())[:15]}")
        else:
            print("\n✗ 'InvoiceLine' not found directly")
            # Search for keys containing 'line' or 'Line'
            line_keys = [k for k in invoice_root.keys() if 'line' in k.lower() or 'Line' in k]
            if line_keys:
                print(f"  Found keys with 'line': {line_keys}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Parse without process_namespaces
print("\n\n2. Parsing without process_namespaces")
print("-"*80)
try:
    invoice_dict2 = xmltodict.parse(xml_content)
    print("✓ Parsed successfully")
    print(f"Root keys: {list(invoice_dict2.keys())}")
    
    # Find Invoice root
    invoice_root2 = None
    for key in ['Invoice', 'invoice', 'ubl:Invoice']:
        if key in invoice_dict2:
            invoice_root2 = invoice_dict2[key]
            break
    
    if not invoice_root2:
        root_keys = list(invoice_dict2.keys())
        for key in root_keys:
            if 'Invoice' in str(key) and 'Signature' not in str(key):
                invoice_root2 = invoice_dict2[key]
                break
    
    if not invoice_root2:
        invoice_root2 = invoice_dict2
    
    print(f"\nInvoice root type: {type(invoice_root2)}")
    if isinstance(invoice_root2, dict):
        print(f"Invoice root keys (first 20): {list(invoice_root2.keys())[:20]}")
        
        # Check for InvoiceLine with namespace
        for key in ['cac:InvoiceLine', 'InvoiceLine', 'invoiceLine']:
            if key in invoice_root2:
                print(f"\n✓ Found '{key}' key")
                il = invoice_root2[key]
                print(f"  Type: {type(il)}")
                if isinstance(il, list):
                    print(f"  List length: {len(il)}")
                    if il:
                        print(f"  First item keys: {list(il[0].keys())[:15]}")
                        # Show first item structure
                        print("\n  First item structure:")
                        pprint(il[0], depth=3, width=100)
                elif isinstance(il, dict):
                    print(f"  Dict keys: {list(il.keys())[:15]}")
                    print("\n  Structure:")
                    pprint(il, depth=3, width=100)
                break
        else:
            print("\n✗ InvoiceLine not found with any expected key")
            # Search for keys containing 'line'
            line_keys = [k for k in invoice_root2.keys() if 'line' in k.lower() or 'Line' in k]
            if line_keys:
                print(f"  Found keys with 'line': {line_keys}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
