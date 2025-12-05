#!/usr/bin/env python3
"""Test parsing with actual XML files from user"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.invoice_service import InvoiceService

# Read the unsigned XML file
unsigned_xml_path = '/Users/csabahitter/Downloads/invoice_6285966885/5748359243.xml'
signed_xml_path = '/Users/csabahitter/Downloads/invoice_6285966885/semnatura_5748359243.xml'

print("="*80)
print("Testing XML File Parsing")
print("="*80)

# Test 1: Parse unsigned XML
print("\n1. Testing UNSIGNED XML (5748359243.xml):")
print("-" * 80)
try:
    with open(unsigned_xml_path, 'r', encoding='utf-8') as f:
        unsigned_xml = f.read()
    
    # Check root element
    if unsigned_xml.strip().startswith('<Invoice') or '<Invoice' in unsigned_xml[:500]:
        print("✓ Root element: <Invoice> (UNSIGNED)")
    else:
        print("✗ Root element check failed")
    
    # Parse it
    parsed = InvoiceService.parse_xml_to_json(unsigned_xml)
    
    print(f"\nExtracted Data:")
    print(f"  Total Amount: {parsed.get('total_amount')}")
    print(f"  Currency: {parsed.get('currency')}")
    print(f"  Issuer Name: {parsed.get('issuer_name')}")
    print(f"  Receiver Name: {parsed.get('receiver_name')}")
    print(f"  Issuer VAT ID: {parsed.get('issuer_vat_id')}")
    print(f"  Receiver VAT ID: {parsed.get('receiver_vat_id')}")
    print(f"  Invoice Number: {parsed.get('invoice_number')}")
    print(f"  Invoice Date: {parsed.get('invoice_date')}")
    
    # Verify expected values
    print(f"\nExpected Values:")
    print(f"  Total Amount: 400.00")
    print(f"  Currency: RON")
    print(f"  Issuer Name: S.C. ANGEL ACCOUNTING SERVICES S.R.L.")
    print(f"  Receiver Name: PROCESSIQ CONSULTING S.R.L.")
    print(f"  Issuer VAT ID: 32640679")
    print(f"  Receiver VAT ID: 51331025")
    
    print(f"\nValidation:")
    all_correct = True
    if parsed.get('total_amount') != 400.00:
        print(f"  ✗ Total Amount: Expected 400.00, got {parsed.get('total_amount')}")
        all_correct = False
    else:
        print(f"  ✓ Total Amount: Correct")
    
    if parsed.get('currency') != 'RON':
        print(f"  ✗ Currency: Expected RON, got {parsed.get('currency')}")
        all_correct = False
    else:
        print(f"  ✓ Currency: Correct")
    
    if parsed.get('issuer_name') != 'S.C. ANGEL ACCOUNTING SERVICES S.R.L.':
        print(f"  ✗ Issuer Name: Expected 'S.C. ANGEL ACCOUNTING SERVICES S.R.L.', got '{parsed.get('issuer_name')}'")
        all_correct = False
    else:
        print(f"  ✓ Issuer Name: Correct")
    
    if parsed.get('receiver_name') != 'PROCESSIQ CONSULTING S.R.L.':
        print(f"  ✗ Receiver Name: Expected 'PROCESSIQ CONSULTING S.R.L.', got '{parsed.get('receiver_name')}'")
        all_correct = False
    else:
        print(f"  ✓ Receiver Name: Correct")
    
    if parsed.get('issuer_vat_id') != '32640679':
        print(f"  ✗ Issuer VAT ID: Expected '32640679', got '{parsed.get('issuer_vat_id')}'")
        all_correct = False
    else:
        print(f"  ✓ Issuer VAT ID: Correct")
    
    if parsed.get('receiver_vat_id') != '51331025':
        print(f"  ✗ Receiver VAT ID: Expected '51331025', got '{parsed.get('receiver_vat_id')}'")
        all_correct = False
    else:
        print(f"  ✓ Receiver VAT ID: Correct")
    
    if all_correct:
        print(f"\n✅ ALL FIELDS CORRECTLY EXTRACTED FROM UNSIGNED XML!")
    else:
        print(f"\n❌ SOME FIELDS ARE INCORRECT")
        
except Exception as e:
    print(f"✗ Error parsing unsigned XML: {str(e)}")
    import traceback
    traceback.print_exc()

# Test 2: Check signed XML
print("\n" + "="*80)
print("2. Testing SIGNED XML (semnatura_5748359243.xml):")
print("-" * 80)
try:
    with open(signed_xml_path, 'r', encoding='utf-8') as f:
        signed_xml = f.read()
    
    # Check root element
    if signed_xml.strip().startswith('<Signature'):
        print("✓ Root element: <Signature> (SIGNED)")
        print("  This file should be SKIPPED by our extraction logic")
    else:
        print("✗ Root element check failed")
    
    # Try to parse it (should fail or not find data)
    parsed_signed = InvoiceService.parse_xml_to_json(signed_xml)
    
    print(f"\nExtracted Data from SIGNED XML:")
    print(f"  Total Amount: {parsed_signed.get('total_amount')}")
    print(f"  Currency: {parsed_signed.get('currency')}")
    print(f"  Issuer Name: {parsed_signed.get('issuer_name')}")
    print(f"  Receiver Name: {parsed_signed.get('receiver_name')}")
    
    if parsed_signed.get('total_amount') is None:
        print(f"\n✓ Correctly identified that signed XML does not contain invoice data")
    else:
        print(f"\n⚠️  WARNING: Extracted data from signed XML (unexpected)")
        
except Exception as e:
    print(f"✗ Error parsing signed XML: {str(e)}")

# Test 3: Test ZIP extraction logic
print("\n" + "="*80)
print("3. Testing ZIP Extraction Logic (simulated):")
print("-" * 80)

import zipfile
import io

# Create a test ZIP with both files
test_zip_data = io.BytesIO()
with zipfile.ZipFile(test_zip_data, 'w') as zip_file:
    with open(unsigned_xml_path, 'r', encoding='utf-8') as f:
        zip_file.writestr('5748359243.xml', f.read().encode('utf-8'))
    with open(signed_xml_path, 'r', encoding='utf-8') as f:
        zip_file.writestr('semnatura_5748359243.xml', f.read().encode('utf-8'))

test_zip_data.seek(0)

# Test extraction
with zipfile.ZipFile(test_zip_data) as zip_file:
    xml_content, xml_filename = InvoiceService.extract_unsigned_xml_from_zip(zip_file)
    
    if xml_content and xml_filename:
        print(f"✓ Extracted XML file: {xml_filename}")
        
        # Verify it's the unsigned one
        if xml_filename == '5748359243.xml':
            print(f"✓ Correctly extracted UNSIGNED file (not semnatura_*.xml)")
        else:
            print(f"✗ Wrong file extracted: {xml_filename}")
        
        # Verify content
        if xml_content.strip().startswith('<Invoice') or '<Invoice' in xml_content[:500]:
            print(f"✓ Extracted XML has Invoice root element (UNSIGNED)")
        else:
            print(f"✗ Extracted XML does not have Invoice root element")
        
        # Test parsing the extracted content
        parsed_extracted = InvoiceService.parse_xml_to_json(xml_content)
        print(f"\nExtracted Data from ZIP-extracted XML:")
        print(f"  Total Amount: {parsed_extracted.get('total_amount')}")
        print(f"  Currency: {parsed_extracted.get('currency')}")
        print(f"  Issuer Name: {parsed_extracted.get('issuer_name')}")
        print(f"  Receiver Name: {parsed_extracted.get('receiver_name')}")
        
        if parsed_extracted.get('total_amount') == 400.00:
            print(f"\n✅ ZIP EXTRACTION AND PARSING WORK CORRECTLY!")
        else:
            print(f"\n❌ ZIP extraction or parsing failed")
    else:
        print(f"✗ Failed to extract unsigned XML from ZIP")

print("\n" + "="*80)
