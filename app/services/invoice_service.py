import xmltodict
import json
from datetime import datetime
from decimal import Decimal

class InvoiceService:
    """Service for parsing and processing invoices"""
    
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
                'invoice_date': None,
                'invoice_number': None,
                'total_amount': None,
                'currency': None
            }
            
            # Navigate UBL structure (this may vary based on actual XML structure)
            invoice_root = invoice_dict.get('Invoice') or invoice_dict.get('invoice') or invoice_dict
            
            # Extract supplier information
            supplier_party = invoice_root.get('AccountingSupplierParty', {}).get('Party', {}) or \
                           invoice_root.get('accountingSupplierParty', {}).get('party', {})
            
            if supplier_party:
                party_name = supplier_party.get('PartyName', {}).get('Name') or \
                           supplier_party.get('partyName', {}).get('name')
                if party_name:
                    invoice_data['supplier_name'] = party_name
                
                # Extract CIF from PartyTaxScheme
                tax_scheme = supplier_party.get('PartyTaxScheme', {}) or \
                           supplier_party.get('partyTaxScheme', {})
                if tax_scheme:
                    company_id = tax_scheme.get('CompanyID') or tax_scheme.get('companyID')
                    if company_id:
                        invoice_data['supplier_cif'] = company_id
            
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
            Tuple of (supplier_name, supplier_cif, invoice_date, total_amount)
        """
        supplier_name = parsed_data.get('supplier_name')
        supplier_cif = parsed_data.get('supplier_cif')
        invoice_date = parsed_data.get('invoice_date')
        total_amount = parsed_data.get('total_amount')
        
        return supplier_name, supplier_cif, invoice_date, total_amount

