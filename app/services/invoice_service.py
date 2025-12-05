import xmltodict
import json
import zipfile
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

class InvoiceService:
    """Service for parsing and processing invoices"""
    
    @staticmethod
    def extract_unsigned_xml_from_zip(zip_file):
        """
        Extract unsigned Invoice XML from ZIP file.
        
        ANAF ZIP files contain two XML files:
        - {id}.xml - Unsigned Invoice XML (contains all data, Peppol UBL 3.0 format)
        - semnatura_{id}.xml - Signed XML (with Signature wrapper, skip this)
        
        Args:
            zip_file: zipfile.ZipFile instance
            
        Returns:
            tuple: (xml_content: str, filename: str) or (None, None) if not found
        """
        try:
            # Get all XML files in ZIP
            all_xml_files = [f for f in zip_file.namelist() if f.endswith('.xml')]
            
            if not all_xml_files:
                return None, None
            
            # Filter out signed files (semnatura_*.xml)
            # Files starting with "semnatura_" are signed XML files
            unsigned_xml_files = [f for f in all_xml_files if not f.startswith('semnatura_')]
            
            if not unsigned_xml_files:
                # No file without "semnatura_" prefix - check all files by content
                for xml_file in all_xml_files:
                    try:
                        content = zip_file.read(xml_file).decode('utf-8')
                        stripped = content.strip()
                        # Check if it's unsigned Invoice XML (has Invoice root, not Signature)
                        if (stripped.startswith('<Invoice') or 
                            (stripped.startswith('<?xml') and '<Invoice' in content[:500] and 
                             '<Signature' not in content[:500])):
                            return content, xml_file
                    except Exception:
                        continue
                return None, None
            
            # Use the file without "semnatura_" prefix (should be {id}.xml)
            unsigned_file = unsigned_xml_files[0]
            xml_content = zip_file.read(unsigned_file).decode('utf-8')
            
            # Verify it's actually unsigned Invoice XML (not signed)
            stripped = xml_content.strip()
            
            # Check if it's signed (has Signature wrapper)
            if stripped.startswith('<Signature') or '<Signature' in stripped[:500]:
                # Wrong file - this is signed XML
                # Try other files
                for xml_file in all_xml_files:
                    if xml_file != unsigned_file:
                        try:
                            content = zip_file.read(xml_file).decode('utf-8')
                            stripped_check = content.strip()
                            if (stripped_check.startswith('<Invoice') or 
                                (stripped_check.startswith('<?xml') and '<Invoice' in content[:500] and 
                                 '<Signature' not in content[:500])):
                                return content, xml_file
                        except Exception:
                            continue
                return None, None
            
            # Verify it has Invoice root element
            if not (stripped.startswith('<Invoice') or 
                    (stripped.startswith('<?xml') and '<Invoice' in xml_content[:500])):
                return None, None
            
            return xml_content, unsigned_file
            
        except Exception as e:
            return None, None
    
    @staticmethod
    def _extract_text_value(value):
        """
        Extract text value from xmltodict result.
        Handles both string values and dictionary structures with #text key.
        
        Args:
            value: Can be a string, dict with #text key, or None
            
        Returns:
            String value or None
        """
        if value is None:
            return None
        if isinstance(value, dict):
            # xmltodict returns dicts with #text key for text content
            return value.get('#text') or value.get('text') or None
        if isinstance(value, str):
            return value
        # Fallback: convert to string
        return str(value) if value else None
    
    @staticmethod
    def _safe_get(data, *keys, default=None):
        """
        Safely navigate nested dictionary structure with multiple possible keys
        
        Args:
            data: Dictionary to navigate
            *keys: Sequence of keys to try (can be strings or lists for nested access)
            default: Default value if not found
            
        Returns:
            Value or default
        """
        if not isinstance(data, dict):
            return default
        
        for key_path in keys:
            if isinstance(key_path, str):
                # Single key
                if key_path in data:
                    return data[key_path]
            else:
                # List of keys for nested access
                current = data
                try:
                    for key in key_path:
                        if isinstance(current, dict) and key in current:
                            current = current[key]
                        else:
                            current = None
                            break
                    if current is not None:
                        return current
                except (TypeError, AttributeError):
                    continue
        
        return default
    
    @staticmethod
    def parse_xml_to_json(xml_content):
        """
        Parse UBL XML invoice to JSON following Peppol UBL 3.0 structure
        Documentation: https://docs.peppol.eu/poacc/billing/3.0/syntax/ubl-invoice/tree/
        
        This expects unsigned Invoice XML (not wrapped in Signature).
        The unsigned XML has Invoice as root element in Peppol UBL 3.0 format.
        
        Args:
            xml_content: XML string content (unsigned Invoice XML)
        
        Returns:
            Dictionary with parsed invoice data
        """
        try:
            # Parse XML to ordered dict
            # Try with namespace processing first
            try:
                invoice_dict = xmltodict.parse(xml_content, process_namespaces=True, namespaces={})
            except:
                # Fallback to default parsing
                invoice_dict = xmltodict.parse(xml_content)
            
            # Extract key information from UBL structure
            invoice_data = {
                'raw': invoice_dict,
                'supplier_name': None,
                'supplier_cif': None,
                'issuer_name': None,  # Extracted from AccountingSupplierParty (BT-27)
                'receiver_name': None,  # Extracted from AccountingCustomerParty (BT-44)
                'receiver_cif': None,  # Extracted from AccountingCustomerParty
                'issuer_vat_id': None,  # BT-31
                'receiver_vat_id': None,  # BT-48
                'invoice_date': None,
                'invoice_number': None,
                'total_amount': None,
                'currency': None
            }
            
            # Navigate UBL structure - unsigned XML should have Invoice as root
            # Handle both namespace-prefixed and non-prefixed Invoice elements
            invoice_root = None
            
            # Try various top-level keys for Invoice element
            for possible_key in ['Invoice', 'invoice', 'ubl:Invoice']:
                if possible_key in invoice_dict:
                    invoice_root = invoice_dict[possible_key]
                    break
            
            # If not found by exact key, check all root keys
            if not invoice_root:
                root_keys = list(invoice_dict.keys())
                # Look for key containing "Invoice" but not "Signature"
                for key in root_keys:
                    if 'Invoice' in str(key) and 'Signature' not in str(key):
                        invoice_root = invoice_dict[key]
                        break
                
                # If still not found, check if root dict has invoice-like keys directly
                if not invoice_root:
                    if any('AccountingSupplierParty' in str(k) or 'LegalMonetaryTotal' in str(k) for k in root_keys):
                        # Root dict itself is the invoice
                        invoice_root = invoice_dict
                    else:
                        # Fallback: use entire dict
                        invoice_root = invoice_dict
            
            # Final fallback
            if not invoice_root:
                invoice_root = invoice_dict
            
            # Extract supplier/issuer information (SELLER)
            # Path: cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName (BT-27)
            supplier_party = InvoiceService._safe_get(
                invoice_root,
                ['cac:AccountingSupplierParty', 'cac:Party'],
                ['AccountingSupplierParty', 'Party'],
                ['accountingSupplierParty', 'party'],
                default={}
            )
            
            if supplier_party:
                # Extract issuer name from PartyLegalEntity -> RegistrationName (BT-27)
                # Also try PartyName as fallback (BT-28)
                party_legal_entity = InvoiceService._safe_get(
                    supplier_party,
                    'cac:PartyLegalEntity',
                    'PartyLegalEntity',
                    'partyLegalEntity',
                    default={}
                )
                
                if party_legal_entity:
                    registration_name_raw = InvoiceService._safe_get(
                        party_legal_entity,
                        'cbc:RegistrationName',
                        'RegistrationName',
                        'registrationName'
                    )
                    registration_name = InvoiceService._extract_text_value(registration_name_raw)
                    if registration_name:
                        invoice_data['supplier_name'] = registration_name
                        invoice_data['issuer_name'] = registration_name
                
                # Fallback: try PartyName -> Name (BT-28)
                if not invoice_data['issuer_name']:
                    party_name_obj = InvoiceService._safe_get(
                        supplier_party,
                        'cac:PartyName',
                        'PartyName',
                        'partyName',
                        default={}
                    )
                    party_name_raw = InvoiceService._safe_get(
                        party_name_obj,
                        'cbc:Name',
                        'Name',
                        'name'
                    )
                    party_name = InvoiceService._extract_text_value(party_name_raw)
                    if party_name:
                        invoice_data['supplier_name'] = party_name
                        invoice_data['issuer_name'] = party_name
                
                # Extract issuer VAT ID from PartyTaxScheme -> CompanyID (BT-31)
                # Note: PartyTaxScheme can appear 0..2 times, look for one with VAT scheme
                tax_schemes = InvoiceService._safe_get(
                    supplier_party,
                    'cac:PartyTaxScheme',
                    'PartyTaxScheme',
                    'partyTaxScheme',
                    default=None
                )
                
                # Handle both single item and list
                if tax_schemes:
                    if not isinstance(tax_schemes, list):
                        tax_schemes = [tax_schemes]
                    
                    for tax_scheme in tax_schemes:
                        if not isinstance(tax_scheme, dict):
                            continue
                        
                        # Check if this is VAT scheme
                        tax_scheme_id = InvoiceService._safe_get(
                            tax_scheme,
                            ['cac:TaxScheme', 'cbc:ID'],
                            ['TaxScheme', 'ID'],
                            ['taxScheme', 'id'],
                            'cbc:ID',
                            'ID',
                            'id'
                        )
                        
                        # If VAT scheme or no scheme specified, extract CompanyID
                        if not tax_scheme_id or InvoiceService._extract_text_value(tax_scheme_id) == 'VAT':
                            company_id_raw = InvoiceService._safe_get(
                                tax_scheme,
                                'cbc:CompanyID',
                                'CompanyID',
                                'companyID'
                            )
                            company_id = InvoiceService._extract_text_value(company_id_raw)
                            if company_id:
                                invoice_data['supplier_cif'] = company_id
                                invoice_data['issuer_vat_id'] = company_id
                                break
            
            # Extract customer/receiver information (BUYER)
            # Path: cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName (BT-44)
            customer_party = InvoiceService._safe_get(
                invoice_root,
                ['cac:AccountingCustomerParty', 'cac:Party'],
                ['AccountingCustomerParty', 'Party'],
                ['accountingCustomerParty', 'party'],
                default={}
            )
            
            if customer_party:
                # Extract receiver name from PartyLegalEntity -> RegistrationName (BT-44)
                party_legal_entity = InvoiceService._safe_get(
                    customer_party,
                    'cac:PartyLegalEntity',
                    'PartyLegalEntity',
                    'partyLegalEntity',
                    default={}
                )
                
                if party_legal_entity:
                    registration_name_raw = InvoiceService._safe_get(
                        party_legal_entity,
                        'cbc:RegistrationName',
                        'RegistrationName',
                        'registrationName'
                    )
                    registration_name = InvoiceService._extract_text_value(registration_name_raw)
                    if registration_name:
                        invoice_data['receiver_name'] = registration_name
                
                # Fallback: try PartyName -> Name (BT-45)
                if not invoice_data['receiver_name']:
                    party_name_obj = InvoiceService._safe_get(
                        customer_party,
                        'cac:PartyName',
                        'PartyName',
                        'partyName',
                        default={}
                    )
                    party_name_raw = InvoiceService._safe_get(
                        party_name_obj,
                        'cbc:Name',
                        'Name',
                        'name'
                    )
                    party_name = InvoiceService._extract_text_value(party_name_raw)
                    if party_name:
                        invoice_data['receiver_name'] = party_name
                
                # Extract receiver VAT ID from PartyTaxScheme -> CompanyID (BT-48)
                tax_schemes = InvoiceService._safe_get(
                    customer_party,
                    'cac:PartyTaxScheme',
                    'PartyTaxScheme',
                    'partyTaxScheme',
                    default=None
                )
                
                if tax_schemes:
                    if not isinstance(tax_schemes, list):
                        tax_schemes = [tax_schemes]
                    
                    for tax_scheme in tax_schemes:
                        if not isinstance(tax_scheme, dict):
                            continue
                        
                        # Check if this is VAT scheme
                        tax_scheme_id = InvoiceService._safe_get(
                            tax_scheme,
                            ['cac:TaxScheme', 'cbc:ID'],
                            ['TaxScheme', 'ID'],
                            ['taxScheme', 'id'],
                            'cbc:ID',
                            'ID',
                            'id'
                        )
                        
                        # If VAT scheme or no scheme specified, extract CompanyID
                        if not tax_scheme_id or InvoiceService._extract_text_value(tax_scheme_id) == 'VAT':
                            company_id_raw = InvoiceService._safe_get(
                                tax_scheme,
                                'cbc:CompanyID',
                                'CompanyID',
                                'companyID'
                            )
                            company_id = InvoiceService._extract_text_value(company_id_raw)
                            if company_id:
                                invoice_data['receiver_cif'] = company_id
                                invoice_data['receiver_vat_id'] = company_id
                                break
            
            # Extract invoice date (BT-2)
            issue_date_raw = InvoiceService._safe_get(
                invoice_root,
                'cbc:IssueDate',
                'IssueDate',
                'issueDate'
            )
            issue_date = InvoiceService._extract_text_value(issue_date_raw)
            if issue_date:
                try:
                    # Format: YYYY-MM-DD
                    invoice_data['invoice_date'] = datetime.strptime(str(issue_date), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
            
            # Extract invoice number (BT-1)
            invoice_data['invoice_number'] = InvoiceService._extract_text_value(
                InvoiceService._safe_get(
                    invoice_root,
                    'cbc:ID',
                    'ID',
                    'id',
                    'InvoiceNumber',
                    'invoiceNumber'
                )
            )
            
            # Extract currency code (BT-5)
            currency_raw = InvoiceService._safe_get(
                invoice_root,
                'cbc:DocumentCurrencyCode',
                'DocumentCurrencyCode',
                'documentCurrencyCode'
            )
            currency = InvoiceService._extract_text_value(currency_raw)
            if currency:
                invoice_data['currency'] = currency
            
            # Extract total amount from LegalMonetaryTotal
            # Try PayableAmount (BT-115) first, then TaxInclusiveAmount (BT-112), then TaxExclusiveAmount (BT-109)
            # Search more broadly for LegalMonetaryTotal with various namespace combinations
            legal_monetary_total = None
            
            # Try multiple namespace variations
            possible_keys = [
                'cac:LegalMonetaryTotal',
                'LegalMonetaryTotal',
                'legalMonetaryTotal',
                '@LegalMonetaryTotal',
                'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2:LegalMonetaryTotal'
            ]
            
            for key in possible_keys:
                legal_monetary_total = InvoiceService._safe_get(invoice_root, key, default=None)
                if legal_monetary_total:
                    break
            
            # If not found, search recursively through the structure
            if not legal_monetary_total:
                def find_legal_monetary_total(obj, depth=0, max_depth=5):
                    """Recursively search for LegalMonetaryTotal"""
                    if depth > max_depth or not isinstance(obj, dict):
                        return None
                    
                    # Check current level
                    for key in obj.keys():
                        if isinstance(key, str) and 'LegalMonetaryTotal' in key or 'legalMonetaryTotal' in key.lower():
                            return obj[key]
                    
                    # Recurse into nested dicts
                    for value in obj.values():
                        if isinstance(value, dict):
                            result = find_legal_monetary_total(value, depth + 1, max_depth)
                            if result:
                                return result
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict):
                                    result = find_legal_monetary_total(item, depth + 1, max_depth)
                                    if result:
                                        return result
                    return None
                
                legal_monetary_total = find_legal_monetary_total(invoice_root)
            
            if not legal_monetary_total:
                legal_monetary_total = {}
            
            # Helper function to extract amount and currency from amount field
            def extract_amount_and_currency(amount_obj, field_name):
                """Extract amount value and currency from amount field object"""
                amount_value = None
                currency_value = None
                
                if amount_obj:
                    # Extract currency from attributes first
                    if isinstance(amount_obj, dict):
                        currency_value = amount_obj.get('@currencyID') or amount_obj.get('currencyID')
                    
                    # Extract amount value
                    amount_text = InvoiceService._extract_text_value(amount_obj)
                    if amount_text:
                        try:
                            amount_value = Decimal(str(amount_text))
                        except (ValueError, TypeError, InvalidOperation):
                            pass
                
                return amount_value, currency_value
            
            if legal_monetary_total:
                
                # Try PayableAmount (BT-115) - Amount due for payment
                payable_amount_obj = InvoiceService._safe_get(
                    legal_monetary_total,
                    'cbc:PayableAmount',
                    'PayableAmount',
                    'payableAmount'
                )
                
                if payable_amount_obj:
                    amount_val, curr_val = extract_amount_and_currency(payable_amount_obj, 'PayableAmount')
                    if amount_val is not None:
                        invoice_data['total_amount'] = amount_val
                    if curr_val and not invoice_data['currency']:
                        invoice_data['currency'] = curr_val
                
                # Fallback: TaxInclusiveAmount (BT-112)
                if not invoice_data['total_amount']:
                    tax_inclusive_obj = InvoiceService._safe_get(
                        legal_monetary_total,
                        'cbc:TaxInclusiveAmount',
                        'TaxInclusiveAmount',
                        'taxInclusiveAmount'
                    )
                    
                    if tax_inclusive_obj:
                        amount_val, curr_val = extract_amount_and_currency(tax_inclusive_obj, 'TaxInclusiveAmount')
                        if amount_val is not None:
                            invoice_data['total_amount'] = amount_val
                        if curr_val and not invoice_data['currency']:
                            invoice_data['currency'] = curr_val
                
                # Final fallback: TaxExclusiveAmount (BT-109)
                if not invoice_data['total_amount']:
                    tax_exclusive_obj = InvoiceService._safe_get(
                        legal_monetary_total,
                        'cbc:TaxExclusiveAmount',
                        'TaxExclusiveAmount',
                        'taxExclusiveAmount'
                    )
                    
                    if tax_exclusive_obj:
                        amount_val, curr_val = extract_amount_and_currency(tax_exclusive_obj, 'TaxExclusiveAmount')
                        if amount_val is not None:
                            invoice_data['total_amount'] = amount_val
                        if curr_val and not invoice_data['currency']:
                            invoice_data['currency'] = curr_val
                
                # Also try LineExtensionAmount as fallback
                if not invoice_data['total_amount']:
                    line_ext_obj = InvoiceService._safe_get(
                        legal_monetary_total,
                        'cbc:LineExtensionAmount',
                        'LineExtensionAmount',
                        'lineExtensionAmount'
                    )
                    
                    if line_ext_obj:
                        amount_val, curr_val = extract_amount_and_currency(line_ext_obj, 'LineExtensionAmount')
                        if amount_val is not None:
                            invoice_data['total_amount'] = amount_val
                        if curr_val and not invoice_data['currency']:
                            invoice_data['currency'] = curr_val
            
            # If we still haven't found the amount, search recursively through the ENTIRE XML structure
            # (not just invoice_root, in case the structure is different)
            if not invoice_data['total_amount']:
                def find_amount_recursive(obj, depth=0, max_depth=8, path=""):
                    """Recursively search for amount fields with broader patterns"""
                    if depth > max_depth or not isinstance(obj, dict):
                        return None, None
                    
                    # Check current level for amount-like fields - expanded patterns
                    for key, value in obj.items():
                        if isinstance(key, str):
                            key_lower = key.lower()
                            current_path = f"{path}.{key}" if path else key
                            
                            # Look for amount fields - more patterns
                            amount_patterns = [
                                'payableamount', 'taxinclusiveamount', 'taxexclusiveamount',
                                'totalamount', 'invoiceamount', 'amountdue', 'total',
                                'suma', 'totalgeneral', 'valoare', 'amount', 'sum'
                            ]
                            
                            if any(pattern in key_lower for pattern in amount_patterns):
                                # Try to extract amount
                                amount_val, curr_val = extract_amount_and_currency(value, key)
                                if amount_val is not None and amount_val > 0:
                                    return amount_val, curr_val
                    
                    # Recurse into nested structures
                    for key, value in obj.items():
                        if isinstance(value, dict):
                            amount, curr = find_amount_recursive(value, depth + 1, max_depth, f"{path}.{key}" if path else key)
                            if amount is not None:
                                return amount, curr
                        elif isinstance(value, list):
                            for i, item in enumerate(value):
                                if isinstance(item, dict):
                                    amount, curr = find_amount_recursive(item, depth + 1, max_depth, f"{path}.{key}[{i}]" if path else f"{key}[{i}]")
                                    if amount is not None:
                                        return amount, curr
                    
                    return None, None
                
                # Search from the entire invoice_dict, not just invoice_root
                amount_val, curr_val = find_amount_recursive(invoice_dict)
                if amount_val is not None:
                    invoice_data['total_amount'] = amount_val
                if curr_val and not invoice_data['currency']:
                    invoice_data['currency'] = curr_val
            
            return invoice_data
            
        except Exception as e:
            # Return minimal structure if parsing fails
            return {
                'raw': {},
                'error': str(e),
                'supplier_name': None,
                'supplier_cif': None,
                'issuer_name': None,
                'receiver_name': None,
                'receiver_cif': None,
                'issuer_vat_id': None,
                'receiver_vat_id': None,
                'invoice_date': None,
                'invoice_number': None,
                'total_amount': None,
                'currency': None
            }
    
    @staticmethod
    def extract_invoice_fields(parsed_data):
        """
        Extract standardized fields from parsed invoice data
        
        Returns:
            Tuple of (supplier_name, supplier_cif, invoice_date, total_amount, currency, issuer_name, receiver_name, issuer_vat_id, receiver_vat_id)
        """
        supplier_name = parsed_data.get('supplier_name')
        supplier_cif = parsed_data.get('supplier_cif')
        invoice_date = parsed_data.get('invoice_date')
        total_amount = parsed_data.get('total_amount')
        currency = parsed_data.get('currency')
        issuer_name = parsed_data.get('issuer_name')
        receiver_name = parsed_data.get('receiver_name')
        issuer_vat_id = parsed_data.get('issuer_vat_id')
        receiver_vat_id = parsed_data.get('receiver_vat_id')
        
        return supplier_name, supplier_cif, invoice_date, total_amount, currency, issuer_name, receiver_name, issuer_vat_id, receiver_vat_id
    
    @staticmethod
    def _is_empty_or_dash(value):
        """
        Check if a value is considered empty (None, empty string, or "-").
        
        Args:
            value: Value to check
            
        Returns:
            bool: True if value is None, empty string, or "-"
        """
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == '' or value.strip() == '-'
        return False
    
    @staticmethod
    def is_invoice_incomplete(invoice):
        """
        Check if invoice is missing critical fields that should be extracted from XML.
        Treats "-" as missing/incomplete data.
        
        Args:
            invoice: Invoice model instance
            
        Returns:
            bool: True if invoice is missing critical fields
        """
        return (
            InvoiceService._is_empty_or_dash(invoice.issuer_name) or
            InvoiceService._is_empty_or_dash(invoice.receiver_name) or
            InvoiceService._is_empty_or_dash(invoice.cif_emitent) or  # Issuer VAT ID
            InvoiceService._is_empty_or_dash(invoice.cif_beneficiar) or  # Receiver VAT ID
            invoice.total_amount is None or
            InvoiceService._is_empty_or_dash(invoice.currency)
        )
    
    @staticmethod
    def reparse_invoice(invoice):
        """
        Reparse invoice XML to update missing fields
        
        If invoice has a stored ZIP file, extracts unsigned XML from it first.
        Otherwise, uses the stored xml_content.
        
        Args:
            invoice: Invoice model instance
            
        Returns:
            bool: True if any fields were updated, False otherwise
        """
        xml_content_to_parse = None
        
        # Try to get unsigned XML from stored ZIP file first
        if invoice.zip_file_path:
            try:
                from app.services.storage_service import InvoiceStorageService
                from flask import current_app
                
                zip_content = InvoiceStorageService.read_zip_file(invoice.zip_file_path)
                if zip_content and zip_content.startswith(b'PK\x03\x04'):
                    # Extract unsigned XML from ZIP
                    with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                        xml_content_to_parse, xml_filename = InvoiceService.extract_unsigned_xml_from_zip(zip_file)
                        if xml_content_to_parse:
                            try:
                                current_app.logger.debug(f"Extracted unsigned XML from stored ZIP for invoice {invoice.id}: {xml_filename}")
                            except RuntimeError:
                                pass
            except Exception as e:
                try:
                    from flask import current_app
                    current_app.logger.warning(f"Could not extract XML from stored ZIP for invoice {invoice.id}: {str(e)}")
                except RuntimeError:
                    pass
        
        # Fallback to stored xml_content
        if not xml_content_to_parse:
            xml_content_to_parse = invoice.xml_content
        
        if not xml_content_to_parse:
            return False
        
        # If we extracted unsigned XML from ZIP and it's different from stored xml_content,
        # update the stored xml_content to the unsigned version
        xml_content_updated = False
        if xml_content_to_parse != invoice.xml_content:
            invoice.xml_content = xml_content_to_parse
            xml_content_updated = True
        
        try:
            # Parse XML content (should now be unsigned XML)
            parsed_data = InvoiceService.parse_xml_to_json(xml_content_to_parse)
            
            # Extract all fields
            supplier_name, supplier_cif, invoice_date, total_amount, currency, \
            issuer_name, receiver_name, issuer_vat_id, receiver_vat_id = \
                InvoiceService.extract_invoice_fields(parsed_data)
            
            updated = xml_content_updated  # Start with xml_content update status
            
            # Update missing fields (treat "-" as missing)
            if InvoiceService._is_empty_or_dash(invoice.issuer_name) and issuer_name:
                invoice.issuer_name = issuer_name
                updated = True
            
            if InvoiceService._is_empty_or_dash(invoice.receiver_name) and receiver_name:
                invoice.receiver_name = receiver_name
                updated = True
            
            # Update VAT IDs (cif_emitent and cif_beneficiar) - treat "-" as missing
            if InvoiceService._is_empty_or_dash(invoice.cif_emitent) and issuer_vat_id:
                invoice.cif_emitent = issuer_vat_id
                updated = True
            
            if InvoiceService._is_empty_or_dash(invoice.cif_beneficiar) and receiver_vat_id:
                invoice.cif_beneficiar = receiver_vat_id
                updated = True
            
            # Update total amount
            if invoice.total_amount is None and total_amount is not None:
                invoice.total_amount = total_amount
                updated = True
            
            # Update currency - treat "-" as missing
            if InvoiceService._is_empty_or_dash(invoice.currency) and currency:
                invoice.currency = currency
                updated = True
            
            # Also update supplier_name if missing or "-" and we have issuer_name
            if InvoiceService._is_empty_or_dash(invoice.supplier_name) and issuer_name:
                invoice.supplier_name = issuer_name
                updated = True
            
            # Also update supplier_cif if missing or "-" and we have issuer VAT ID
            if InvoiceService._is_empty_or_dash(invoice.supplier_cif) and issuer_vat_id:
                invoice.supplier_cif = issuer_vat_id
                updated = True
            
            return updated
            
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.error(f"Error reparsing invoice {invoice.id}: {str(e)}", exc_info=True)
            except RuntimeError:
                pass
            return False