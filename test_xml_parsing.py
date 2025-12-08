#!/usr/bin/env python3
"""Test XML parsing directly without Flask dependencies"""

import xmltodict
from pprint import pprint

# Read the example XML
xml_file = '/Users/csabahitter/Downloads/invoice_6290533787/5750668021.xml'

print("="*80)
print("Testing XML Parsing and InvoiceLine Extraction")
print("="*80)

try:
    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    print(f"\n✓ XML file loaded ({len(xml_content)} characters)")
    
    # Parse with process_namespaces=True (as used in InvoiceService)
    print("\n" + "-"*80)
    print("Parsing XML with process_namespaces=True...")
    print("-"*80)
    
    invoice_dict = xmltodict.parse(xml_content, process_namespaces=True, namespaces={})
    
    print("Root keys:", list(invoice_dict.keys()))
    
    # Find Invoice root
    invoice_root = invoice_dict.get('Invoice', invoice_dict)
    
    if isinstance(invoice_root, dict):
        print(f"\nInvoice root type: {type(invoice_root)}")
        print(f"Invoice root has {len(invoice_root)} keys")
        print("\nFirst 30 keys in invoice_root:")
        for i, key in enumerate(list(invoice_root.keys())[:30], 1):
            print(f"  {i:2d}. {key}")
        
        # Check for InvoiceLine
        print("\n" + "="*80)
        print("Looking for InvoiceLine...")
        print("="*80)
        
        if 'InvoiceLine' in invoice_root:
            print("✓ Found 'InvoiceLine' key directly!")
            il = invoice_root['InvoiceLine']
            print(f"  Type: {type(il)}")
            
            if isinstance(il, dict):
                print(f"  It's a dict with keys: {list(il.keys())}")
                print("\n  Full InvoiceLine structure:")
                pprint(il, depth=10, width=120)
                
                # Now test extraction logic
                print("\n" + "="*80)
                print("Testing Field Extraction:")
                print("="*80)
                
                # Extract line ID
                line_id = il.get('ID') or il.get('id') or il.get('cbc:ID')
                if isinstance(line_id, dict):
                    line_id = line_id.get('#text') or line_id.get('text')
                print(f"Line ID: {line_id}")
                
                # Extract quantity
                qty = il.get('InvoicedQuantity') or il.get('invoicedQuantity') or il.get('cbc:InvoicedQuantity')
                if isinstance(qty, dict):
                    unit_code = qty.get('@unitCode') or qty.get('unitCode')
                    qty_value = qty.get('#text') or qty.get('text')
                    print(f"Quantity: {qty_value}, Unit: {unit_code}")
                else:
                    print(f"Quantity: {qty}")
                
                # Extract Item
                item = il.get('Item') or il.get('item') or il.get('cac:Item')
                if item:
                    print(f"\nItem type: {type(item)}")
                    if isinstance(item, dict):
                        print(f"Item keys: {list(item.keys())}")
                        
                        # Extract Name
                        name = item.get('Name') or item.get('name') or item.get('cbc:Name')
                        if isinstance(name, dict):
                            name = name.get('#text') or name.get('text')
                        print(f"Item Name: {name}")
                        
                        # Extract Description
                        desc = item.get('Description') or item.get('description') or item.get('cbc:Description')
                        if isinstance(desc, dict):
                            desc = desc.get('#text') or desc.get('text')
                        print(f"Item Description: {desc}")
                        
                        # Extract Tax Category
                        tax_cat = item.get('ClassifiedTaxCategory') or item.get('classifiedTaxCategory') or item.get('cac:ClassifiedTaxCategory')
                        if tax_cat:
                            if isinstance(tax_cat, dict):
                                tax_id = tax_cat.get('ID') or tax_cat.get('id') or tax_cat.get('cbc:ID')
                                if isinstance(tax_id, dict):
                                    tax_id = tax_id.get('#text') or tax_id.get('text')
                                print(f"VAT Category: {tax_id}")
                
                # Extract Price
                price = il.get('Price') or il.get('price') or il.get('cac:Price')
                if price:
                    print(f"\nPrice type: {type(price)}")
                    if isinstance(price, dict):
                        print(f"Price keys: {list(price.keys())}")
                        price_amt = price.get('PriceAmount') or price.get('priceAmount') or price.get('cbc:PriceAmount')
                        if price_amt:
                            if isinstance(price_amt, dict):
                                currency = price_amt.get('@currencyID') or price_amt.get('currencyID')
                                price_value = price_amt.get('#text') or price_amt.get('text')
                                print(f"Price Amount: {price_value}, Currency: {currency}")
                            else:
                                print(f"Price Amount: {price_amt}")
                
                # Extract LineExtensionAmount
                line_total = il.get('LineExtensionAmount') or il.get('lineExtensionAmount') or il.get('cbc:LineExtensionAmount')
                if line_total:
                    if isinstance(line_total, dict):
                        currency = line_total.get('@currencyID') or line_total.get('currencyID')
                        total_value = line_total.get('#text') or line_total.get('text')
                        print(f"\nLine Total: {total_value}, Currency: {currency}")
                    else:
                        print(f"\nLine Total: {line_total}")
                
            elif isinstance(il, list):
                print(f"  It's a list with {len(il)} items")
                if il:
                    print(f"  First item keys: {list(il[0].keys())}")
                    pprint(il[0], depth=5, width=120)
        else:
            print("✗ 'InvoiceLine' not found directly")
            # Search for keys containing 'line'
            line_keys = [k for k in invoice_root.keys() if 'line' in k.lower() or 'Line' in k]
            if line_keys:
                print(f"\nBut found keys with 'line': {line_keys}")
                for key in line_keys:
                    print(f"\n  Key '{key}':")
                    val = invoice_root[key]
                    print(f"    Type: {type(val)}")
                    if isinstance(val, dict):
                        print(f"    Keys: {list(val.keys())[:15]}")
                    elif isinstance(val, list) and val:
                        print(f"    List with {len(val)} items")
                        if isinstance(val[0], dict):
                            print(f"    First item keys: {list(val[0].keys())[:15]}")
    
except FileNotFoundError:
    print(f"✗ XML file not found: {xml_file}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
