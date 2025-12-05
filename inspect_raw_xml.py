#!/usr/bin/env python3
"""
Inspect raw XML to understand the actual structure
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Invoice

app = create_app(os.getenv('FLASK_ENV', 'default'))

with app.app_context():
    invoice = Invoice.query.filter(Invoice.total_amount.is_(None)).first()
    
    if not invoice or not invoice.xml_content:
        print("No invoice XML found")
        sys.exit(0)
    
    print(f"Invoice ID: {invoice.id}, ANAF ID: {invoice.anaf_id}")
    print(f"Issuer Name from DB: {invoice.issuer_name}")
    print("="*80)
    
    # Show full XML (it might be small)
    print("\nFULL XML CONTENT:")
    print("="*80)
    if len(invoice.xml_content) < 5000:
        print(invoice.xml_content)
    else:
        print("\nFirst 3000 chars:")
        print(invoice.xml_content[:3000])
        print("\n... (truncated) ...\n")
        print("\nLast 1000 chars:")
        print(invoice.xml_content[-1000:])
    
    print("\n" + "="*80)
    print("XML STRUCTURE ANALYSIS:")
    print("="*80)
    
    # Count lines
    lines = invoice.xml_content.split('\n')
    print(f"Total lines: {len(lines)}")
    print(f"Total characters: {len(invoice.xml_content)}")
    
    # Look for root element
    first_line = lines[0] if lines else ""
    print(f"\nFirst line: {first_line[:200]}")
    
    # Find all unique opening tags in first 100 lines
    import re
    tags = set()
    for line in lines[:100]:
        matches = re.findall(r'<([^/!?\s>]+)', line)
        for match in matches:
            if not match.startswith('?xml') and not match.startswith('!--'):
                tags.add(match)
    
    print(f"\nUnique tags found in first 100 lines ({len(tags)}):")
    for tag in sorted(tags)[:30]:
        print(f"  - {tag}")
