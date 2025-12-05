#!/usr/bin/env python3
"""
Diagnostic script to inspect invoice XML structure and debug parsing issues.

Usage:
    python diagnose_invoice_xml.py <invoice_id>
    python diagnose_invoice_xml.py --all
"""

import sys
import os
import json
from pprint import pprint

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Invoice
from app.services.invoice_service import InvoiceService
import xmltodict

def diagnose_invoice(invoice_id):
    """Diagnose a specific invoice's XML structure"""
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        print(f"Invoice {invoice_id} not found")
        return
    
    print(f"\n{'='*60}")
    print(f"Diagnosing Invoice ID: {invoice_id}")
    print(f"ANAF ID: {invoice.anaf_id}")
    print(f"{'='*60}\n")
    
    print(f"Current Database Values:")
    print(f"  - Total Amount: {invoice.total_amount}")
    print(f"  - Currency: {invoice.currency}")
    print(f"  - Issuer Name: {invoice.issuer_name}")
    print(f"  - Receiver Name: {invoice.receiver_name}")
    print(f"  - Has XML: {'Yes' if invoice.xml_content else 'No'}")
    print()
    
    if not invoice.xml_content:
        print("ERROR: No XML content found for this invoice!")
        return
    
    # Parse XML
    try:
        invoice_dict = xmltodict.parse(invoice.xml_content)
        print(f"✓ XML parsed successfully")
    except Exception as e:
        print(f"✗ ERROR parsing XML: {e}")
        return
    
    # Find invoice root - check all possible structures
    print(f"\n{'='*60}")
    print("Full XML Structure:")
    print(f"{'='*60}")
    print(f"Top-level keys: {list(invoice_dict.keys())}")
    
    # Since issuer_name IS being extracted, let's trace where it comes from
    print(f"\n{'='*60}")
    print("Tracing where issuer_name is extracted from:")
    print(f"{'='*60}")
    
    # Use our parser to see what it finds
    parsed_data = InvoiceService.parse_xml_to_json(invoice.xml_content)
    
    # Now search for AccountingSupplierParty to see the structure
    def find_supplier_party(obj, path="", depth=0, max_depth=6):
        """Find AccountingSupplierParty in the XML structure"""
        if depth > max_depth or not isinstance(obj, dict):
            return None, None
        
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            if isinstance(key, str):
                if 'AccountingSupplierParty' in key or 'accountingSupplierParty' in key.lower():
                    return value, current_path
                if 'SupplierParty' in key or 'supplierParty' in key.lower():
                    return value, current_path
            
            if isinstance(value, dict):
                result, result_path = find_supplier_party(value, current_path, depth + 1, max_depth)
                if result:
                    return result, result_path
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        result, result_path = find_supplier_party(item, f"{current_path}[{i}]", depth + 1, max_depth)
                        if result:
                            return result, result_path
        
        return None, None
    
    supplier_party, supplier_path = find_supplier_party(invoice_dict)
    if supplier_party:
        print(f"✓ Found supplier party at path: {supplier_path}")
        print(f"  Keys in supplier party: {list(supplier_party.keys())[:15] if isinstance(supplier_party, dict) else type(supplier_party)}")
    else:
        print("✗ Could not find AccountingSupplierParty in XML structure")
    
    # Now try to find the invoice root by looking at the structure
    invoice_root = None
    
    # Since we can extract names, the data must be accessible - let's find the actual root
    # Check if the entire dict is structured differently
    print(f"\n{'='*60}")
    print("Searching for Invoice root element:")
    print(f"{'='*60}")
    
    # Check all keys recursively
    def find_invoice_element(obj, path="", depth=0, max_depth=3):
        """Find Invoice element"""
        if depth > max_depth or not isinstance(obj, dict):
            return None, None
        
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            key_str = str(key)
            
            # Check if this looks like an Invoice element
            if ('Invoice' in key_str and 'Signature' not in key_str) or \
               (key_str.lower() == 'invoice') or \
               ('ubl' in key_str.lower() and 'invoice' in key_str.lower()):
                return value, current_path
            
            if isinstance(value, dict):
                result, result_path = find_invoice_element(value, current_path, depth + 1, max_depth)
                if result:
                    return result, result_path
        
        return None, None
    
    invoice_root, invoice_path = find_invoice_element(invoice_dict)
    if invoice_root:
        print(f"✓ Found Invoice element at path: {invoice_path}")
        print(f"  Keys: {list(invoice_root.keys())[:20] if isinstance(invoice_root, dict) else type(invoice_root)}")
    else:
        print("✗ Could not find Invoice element - using entire dict")
        invoice_root = invoice_dict
        invoice_path = "root"
    
    # Check LegalMonetaryTotal
    print(f"\n{'='*60}")
    print("Checking LegalMonetaryTotal Structure:")
    print(f"{'='*60}")
    
    legal_monetary_total = None
    for key in ['cac:LegalMonetaryTotal', 'LegalMonetaryTotal', 'legalMonetaryTotal']:
        if key in invoice_root:
            legal_monetary_total = invoice_root[key]
            print(f"✓ Found LegalMonetaryTotal with key: '{key}'")
            break
    
    if not legal_monetary_total:
        print("✗ LegalMonetaryTotal NOT FOUND!")
        print("\nSearching for amount-related fields in all keys...")
        
        # Search recursively for amount fields
        def find_amount_fields(obj, path="", depth=0):
            """Recursively search for amount fields"""
            if depth > 5:  # Limit depth
                return
            
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    key_lower = key.lower()
                    
                    # Check if this looks like an amount field
                    if any(word in key_lower for word in ['amount', 'total', 'monetary', 'payable', 'tax']):
                        print(f"  Found potential amount field: {current_path}")
                        print(f"    Type: {type(value)}")
                        if isinstance(value, dict):
                            print(f"    Keys: {list(value.keys())[:5]}")
                            # Check for currency
                            if '@currencyID' in value or 'currencyID' in value:
                                print(f"    Currency: {value.get('@currencyID') or value.get('currencyID')}")
                            # Check for text value
                            text_val = value.get('#text') or value.get('text')
                            if text_val:
                                print(f"    Value: {text_val}")
                        elif isinstance(value, str):
                            print(f"    Value: {value}")
                    
                    # Recurse into nested dicts
                    if isinstance(value, dict):
                        find_amount_fields(value, current_path, depth + 1)
                    elif isinstance(value, list):
                        for i, item in enumerate(value):
                            if isinstance(item, dict):
                                find_amount_fields(item, f"{current_path}[{i}]", depth + 1)
        
        find_amount_fields(invoice_root)
        print("\nAvailable keys in invoice_root:", list(invoice_root.keys())[:30])
        return
    
    print(f"\nLegalMonetaryTotal keys: {list(legal_monetary_total.keys()) if isinstance(legal_monetary_total, dict) else type(legal_monetary_total)}")
    
    # Check amount fields
    amount_fields = [
        'cbc:PayableAmount', 'PayableAmount', 'payableAmount',
        'cbc:TaxInclusiveAmount', 'TaxInclusiveAmount', 'taxInclusiveAmount',
        'cbc:TaxExclusiveAmount', 'TaxExclusiveAmount', 'taxExclusiveAmount',
        'cbc:LineExtensionAmount', 'LineExtensionAmount', 'lineExtensionAmount'
    ]
    
    print(f"\n{'='*60}")
    print("Amount Fields Found:")
    print(f"{'='*60}")
    
    found_amounts = {}
    for field in amount_fields:
        if isinstance(legal_monetary_total, dict) and field in legal_monetary_total:
            value = legal_monetary_total[field]
            print(f"\n✓ Found: {field}")
            print(f"  Type: {type(value)}")
            print(f"  Value: {value}")
            
            # Try to extract amount
            if isinstance(value, dict):
                print(f"  Dict keys: {list(value.keys())}")
                text_value = value.get('#text') or value.get('text') or value.get('@text')
                currency = value.get('@currencyID') or value.get('currencyID')
                print(f"  Text value: {text_value}")
                print(f"  Currency: {currency}")
                if text_value:
                    found_amounts[field] = {
                        'amount': text_value,
                        'currency': currency
                    }
            elif isinstance(value, str):
                print(f"  String value: {value}")
                found_amounts[field] = {'amount': value}
    
    # Try our parsing
    print(f"\n{'='*60}")
    print("Testing Our Parser:")
    print(f"{'='*60}")
    
    parsed_data = InvoiceService.parse_xml_to_json(invoice.xml_content)
    print(f"\nParsed Results:")
    print(f"  - Total Amount: {parsed_data.get('total_amount')}")
    print(f"  - Currency: {parsed_data.get('currency')}")
    print(f"  - Issuer Name: {parsed_data.get('issuer_name')}")
    print(f"  - Receiver Name: {parsed_data.get('receiver_name')}")
    
    # Check currency code
    print(f"\n{'='*60}")
    print("Checking Currency Code:")
    print(f"{'='*60}")
    
    currency_keys = ['cbc:DocumentCurrencyCode', 'DocumentCurrencyCode', 'documentCurrencyCode']
    for key in currency_keys:
        if key in invoice_root:
            print(f"✓ Found currency with key '{key}': {invoice_root[key]}")
    
    # Show raw XML structure - first 50 lines to see the namespace declarations
    print(f"\n{'='*60}")
    print("Raw XML - First 50 lines (to see structure and namespaces):")
    print(f"{'='*60}")
    
    xml_lines = invoice.xml_content.split('\n')
    for i, line in enumerate(xml_lines[:50]):
        print(f"{i+1:3d}: {line}")
    
    # Try to find Invoice opening tag
    print(f"\n{'='*60}")
    print("Searching for Invoice/amount-related tags in XML:")
    print(f"{'='*60}")
    
    keywords = ['Invoice', 'LegalMonetaryTotal', 'PayableAmount', 'TaxInclusiveAmount', 
                'TaxExclusiveAmount', 'DocumentCurrencyCode', 'Total', 'Amount']
    
    for keyword in keywords:
        for i, line in enumerate(xml_lines):
            if keyword in line:
                # Show context (2 lines before and after)
                start = max(0, i - 2)
                end = min(len(xml_lines), i + 3)
                print(f"\nFound '{keyword}' at line {i+1}:")
                for j in range(start, end):
                    marker = ">>>" if j == i else "   "
                    print(f"{marker} {j+1:3d}: {xml_lines[j]}")
                break  # Only show first occurrence

def diagnose_all_incomplete():
    """Diagnose all invoices with missing total_amount"""
    incomplete = Invoice.query.filter(
        db.or_(
            Invoice.total_amount.is_(None),
            Invoice.currency.is_(None)
        )
    ).limit(3).all()
    
    print(f"\nFound {len(incomplete)} invoices with missing total_amount/currency")
    
    for invoice in incomplete:
        diagnose_invoice(invoice.id)
        print(f"\n{'='*80}\n")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Diagnose invoice XML structure')
    parser.add_argument('invoice_id', type=int, nargs='?', help='Invoice ID to diagnose')
    parser.add_argument('--all', action='store_true', help='Diagnose all incomplete invoices')
    
    args = parser.parse_args()
    
    app = create_app(os.getenv('FLASK_ENV', 'default'))
    
    with app.app_context():
        if args.all:
            diagnose_all_incomplete()
        elif args.invoice_id:
            diagnose_invoice(args.invoice_id)
        else:
            parser.print_help()
