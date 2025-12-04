import xmltodict
import json
from datetime import datetime
from decimal import Decimal

class InvoiceService:
    """Service for parsing and processing invoices"""
    
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
    def parse_xml_to_json(xml_content):
        """
        Parse UBL XML invoice to JSON
        
        Args:
            xml_content: XML string content
        
        Returns:
            Dictionary with parsed invoice data
        """
        try:
            # Parse XML to ordered dict
            invoice_dict = xmltodict.parse(xml_content)
            
            # Extract key information from UBL structure
            # UBL structure: Invoice -> AccountingSupplierParty -> Party -> PartyName -> Name
            invoice_data = {
                'raw': invoice_dict,
                'supplier_name': None,
                'supplier_cif': None,
                'issuer_name': None,  # Same as supplier_name (extracted from AccountingSupplierParty)
                'receiver_name': None,  # Extracted from AccountingCustomerParty
                'receiver_cif': None,  # Extracted from AccountingCustomerParty
                'invoice_date': None,
                'invoice_number': None,
                'total_amount': None,
                'currency': None
            }
            
            # Navigate UBL structure (this may vary based on actual XML structure)
            invoice_root = invoice_dict.get('Invoice') or invoice_dict.get('invoice') or invoice_dict
            
            # Extract supplier/issuer information
            # Try multiple possible structures (with and without namespace prefixes)
            supplier_party = None
            if 'cac:AccountingSupplierParty' in invoice_root:
                supplier_party = invoice_root.get('cac:AccountingSupplierParty', {}).get('cac:Party', {})
            elif 'AccountingSupplierParty' in invoice_root:
                supplier_party = invoice_root.get('AccountingSupplierParty', {}).get('Party', {})
            elif 'accountingSupplierParty' in invoice_root:
                supplier_party = invoice_root.get('accountingSupplierParty', {}).get('party', {})
            
            if supplier_party:
                # Extract name from PartyLegalEntity -> RegistrationName (UBL 2.1 standard)
                party_legal_entity = None
                if 'cac:PartyLegalEntity' in supplier_party:
                    party_legal_entity = supplier_party.get('cac:PartyLegalEntity', {})
                elif 'PartyLegalEntity' in supplier_party:
                    party_legal_entity = supplier_party.get('PartyLegalEntity', {})
                elif 'partyLegalEntity' in supplier_party:
                    party_legal_entity = supplier_party.get('partyLegalEntity', {})
                
                if party_legal_entity:
                    # Try RegistrationName (UBL 2.1 standard)
                    registration_name_raw = party_legal_entity.get('cbc:RegistrationName') or \
                                          party_legal_entity.get('RegistrationName') or \
                                          party_legal_entity.get('registrationName')
                    registration_name = InvoiceService._extract_text_value(registration_name_raw)
                    if registration_name:
                        invoice_data['supplier_name'] = registration_name
                        invoice_data['issuer_name'] = registration_name  # Issuer is the supplier
                
                # Fallback: try PartyName (older UBL versions)
                if not invoice_data['issuer_name']:
                    party_name_raw = supplier_party.get('cac:PartyName', {}).get('cbc:Name') or \
                                   supplier_party.get('PartyName', {}).get('Name') or \
                                   supplier_party.get('partyName', {}).get('name')
                    party_name = InvoiceService._extract_text_value(party_name_raw)
                    if party_name:
                        invoice_data['supplier_name'] = party_name
                        invoice_data['issuer_name'] = party_name
                
                # Extract CIF from PartyTaxScheme
                tax_scheme = None
                if 'cac:PartyTaxScheme' in supplier_party:
                    tax_scheme = supplier_party.get('cac:PartyTaxScheme', {})
                elif 'PartyTaxScheme' in supplier_party:
                    tax_scheme = supplier_party.get('PartyTaxScheme', {})
                elif 'partyTaxScheme' in supplier_party:
                    tax_scheme = supplier_party.get('partyTaxScheme', {})
                
                if tax_scheme:
                    company_id_raw = tax_scheme.get('cbc:CompanyID') or \
                                   tax_scheme.get('CompanyID') or \
                                   tax_scheme.get('companyID')
                    company_id = InvoiceService._extract_text_value(company_id_raw)
                    if company_id:
                        invoice_data['supplier_cif'] = company_id
            
            # Extract customer/receiver information
            customer_party = None
            if 'cac:AccountingCustomerParty' in invoice_root:
                customer_party = invoice_root.get('cac:AccountingCustomerParty', {}).get('cac:Party', {})
            elif 'AccountingCustomerParty' in invoice_root:
                customer_party = invoice_root.get('AccountingCustomerParty', {}).get('Party', {})
            elif 'accountingCustomerParty' in invoice_root:
                customer_party = invoice_root.get('accountingCustomerParty', {}).get('party', {})
            
            if customer_party:
                # Extract receiver name from PartyLegalEntity -> RegistrationName
                party_legal_entity = None
                if 'cac:PartyLegalEntity' in customer_party:
                    party_legal_entity = customer_party.get('cac:PartyLegalEntity', {})
                elif 'PartyLegalEntity' in customer_party:
                    party_legal_entity = customer_party.get('PartyLegalEntity', {})
                elif 'partyLegalEntity' in customer_party:
                    party_legal_entity = customer_party.get('partyLegalEntity', {})
                
                if party_legal_entity:
                    registration_name_raw = party_legal_entity.get('cbc:RegistrationName') or \
                                          party_legal_entity.get('RegistrationName') or \
                                          party_legal_entity.get('registrationName')
                    registration_name = InvoiceService._extract_text_value(registration_name_raw)
                    if registration_name:
                        invoice_data['receiver_name'] = registration_name
                
                # Fallback: try PartyName
                if not invoice_data['receiver_name']:
                    party_name_raw = customer_party.get('cac:PartyName', {}).get('cbc:Name') or \
                                   customer_party.get('PartyName', {}).get('Name') or \
                                   customer_party.get('partyName', {}).get('name')
                    party_name = InvoiceService._extract_text_value(party_name_raw)
                    if party_name:
                        invoice_data['receiver_name'] = party_name
                
                # Extract receiver CIF from PartyTaxScheme
                tax_scheme = None
                if 'cac:PartyTaxScheme' in customer_party:
                    tax_scheme = customer_party.get('cac:PartyTaxScheme', {})
                elif 'PartyTaxScheme' in customer_party:
                    tax_scheme = customer_party.get('PartyTaxScheme', {})
                elif 'partyTaxScheme' in customer_party:
                    tax_scheme = customer_party.get('partyTaxScheme', {})
                
                if tax_scheme:
                    company_id_raw = tax_scheme.get('cbc:CompanyID') or \
                                   tax_scheme.get('CompanyID') or \
                                   tax_scheme.get('companyID')
                    company_id = InvoiceService._extract_text_value(company_id_raw)
                    if company_id:
                        invoice_data['receiver_cif'] = company_id
            
            # Extract invoice date
            issue_date = invoice_root.get('IssueDate') or invoice_root.get('issueDate')
            if issue_date:
                try:
                    invoice_data['invoice_date'] = datetime.strptime(issue_date, '%Y-%m-%d').date()
                except:
                    pass
            
            # Extract invoice number
            invoice_data['invoice_number'] = invoice_root.get('ID') or \
                                           invoice_root.get('id') or \
                                           invoice_root.get('InvoiceNumber') or \
                                           invoice_root.get('invoiceNumber')
            
            # Extract total amount
            legal_monetary_total = invoice_root.get('LegalMonetaryTotal', {}) or \
                                 invoice_root.get('legalMonetaryTotal', {})
            
            if legal_monetary_total:
                total = legal_monetary_total.get('TaxInclusiveAmount', {}).get('#text') or \
                       legal_monetary_total.get('taxInclusiveAmount', {}).get('#text') or \
                       legal_monetary_total.get('TaxInclusiveAmount') or \
                       legal_monetary_total.get('taxInclusiveAmount')
                
                if total:
                    try:
                        invoice_data['total_amount'] = Decimal(str(total))
                    except:
                        pass
                
                # Extract currency
                currency = legal_monetary_total.get('TaxInclusiveAmount', {}).get('@currencyID') or \
                          legal_monetary_total.get('taxInclusiveAmount', {}).get('@currencyID')
                if currency:
                    invoice_data['currency'] = currency
            
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
            Tuple of (supplier_name, supplier_cif, invoice_date, total_amount, issuer_name, receiver_name)
        """
        supplier_name = parsed_data.get('supplier_name')
        supplier_cif = parsed_data.get('supplier_cif')
        invoice_date = parsed_data.get('invoice_date')
        total_amount = parsed_data.get('total_amount')
        issuer_name = parsed_data.get('issuer_name')
        receiver_name = parsed_data.get('receiver_name')
        
        return supplier_name, supplier_cif, invoice_date, total_amount, issuer_name, receiver_name