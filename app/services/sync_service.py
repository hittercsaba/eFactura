from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta, timezone, date
from flask import current_app
import zipfile
import io
import re
from app.models import db, Company, Invoice, AnafToken
from app.services.anaf_service import ANAFService
from app.services.invoice_service import InvoiceService
from app.services.storage_service import InvoiceStorageService

scheduler = None
app_instance = None  # Store app instance for scheduler context

def _calculate_sync_days(company_id):
    """
    Calculate the number of days to sync based on the last sync date.
    
    - First sync (no invoices): Returns 60 days
    - Subsequent syncs: Returns days from last sync to now (min 1, max 60)
    
    Args:
        company_id: ID of the company to check
    
    Returns:
        Number of days to sync (1-60)
    """
    # Check if this is the first sync (no invoices exist)
    invoice_count = Invoice.query.filter_by(company_id=company_id).count()
    
    if invoice_count == 0:
        # First sync - fetch last 60 days
        return 60
    
    # Find the most recent synced invoice
    last_invoice = Invoice.query.filter_by(company_id=company_id)\
        .order_by(Invoice.synced_at.desc())\
        .first()
    
    if not last_invoice or not last_invoice.synced_at:
        # No synced_at date found - treat as first sync
        return 60
    
    # Get last sync date (ensure timezone-aware)
    last_sync_date = last_invoice.synced_at
    if last_sync_date.tzinfo is None:
        last_sync_date = last_sync_date.replace(tzinfo=timezone.utc)
    
    # Calculate days between last sync and now
    now = datetime.now(timezone.utc)
    days_diff = (now - last_sync_date).days
    
    # Add 1 to include today, ensure minimum of 1 day
    sync_days = max(1, days_diff + 1)
    
    # Cap at 60 days maximum (ANAF API limit and reasonable initial sync window)
    sync_days = min(60, sync_days)
    
    return sync_days

def sync_company_invoices(company_id, force=False):
    """
    Sync invoices for a specific company
    
    Args:
        company_id: ID of the company to sync
        force: If True, sync even if auto_sync_enabled is False (for manual syncs)
    """
    import sys
    print(f"[SYNC] FUNCTION CALLED: sync_company_invoices(company_id={company_id}, force={force})", file=sys.stderr)
    sys.stderr.flush()
    
    global app_instance
    
    # Check if we're in an app context (e.g., called from a route)
    try:
        # Try to access current_app - if successful, we're in an app context
        _ = current_app._get_current_object()
        # We're in an app context - call implementation directly
        print(f"[SYNC] In app context - calling implementation directly...", file=sys.stderr)
        sys.stderr.flush()
        try:
            _sync_company_invoices_impl(company_id, force=force)
            print(f"[SYNC] Implementation completed successfully", file=sys.stderr)
            sys.stderr.flush()
        except Exception as e:
            print(f"[SYNC] Exception in implementation: {type(e).__name__}: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            raise
        return
    except RuntimeError:
        # Not in an app context - need to create one (for background jobs)
        print(f"[SYNC] Not in app context - creating one...", file=sys.stderr)
        sys.stderr.flush()
        pass
    
    # Not in an app context, create one
    # This happens when called from background jobs
    if app_instance:
        # Use stored app instance (for scheduled jobs)
        with app_instance.app_context():
            app_instance.logger.info(f"sync_company_invoices called with company_id={company_id}, force={force} - Using app_instance")
            _sync_company_invoices_impl(company_id, force=force)
    else:
        # Last resort: try current_app again (might work in some cases)
        try:
            _ = current_app._get_current_object()
            with current_app.app_context():
                current_app.logger.info(f"sync_company_invoices called with company_id={company_id}, force={force} - Created new app context")
                _sync_company_invoices_impl(company_id, force=force)
        except RuntimeError as e:
            # No application context available
            import logging
            logging.error(f"Cannot sync company {company_id} - no Flask app context available: {str(e)}")
            return

def _sync_company_invoices_impl(company_id, force=False):
    """
    Internal implementation of sync_company_invoices
    
    Args:
        company_id: ID of the company to sync
        force: If True, sync even if auto_sync_enabled is False (for manual syncs)
    """
    # Use print as backup to ensure we always see this
    import sys
    print(f"[SYNC_IMPL] START: _sync_company_invoices_impl(company_id={company_id}, force={force})", file=sys.stderr)
    sys.stderr.flush()
    
    try:
        print(f"[SYNC_IMPL] Step 1: Entered try block", file=sys.stderr)
        sys.stderr.flush()
        
        try:
            current_app.logger.info(f"=== STARTING SYNC FOR COMPANY {company_id} ===")
            current_app.logger.info(f"Force mode: {force}")
            print(f"[SYNC_IMPL] Step 2: Logged to Flask logger", file=sys.stderr)
            sys.stderr.flush()
        except Exception as log_err:
            print(f"[SYNC_IMPL] === STARTING SYNC FOR COMPANY {company_id} ===", file=sys.stderr)
            print(f"[SYNC_IMPL] Force mode: {force}", file=sys.stderr)
            print(f"[SYNC_IMPL] Logger error: {log_err}", file=sys.stderr)
            sys.stderr.flush()
        
        print(f"[SYNC_IMPL] Step 3: About to query company {company_id}", file=sys.stderr)
        sys.stderr.flush()
        
        company = Company.query.get(company_id)
        print(f"[SYNC_IMPL] Step 4: Company query returned: {company}", file=sys.stderr)
        sys.stderr.flush()
        
        if not company:
            print(f"[SYNC_IMPL] ERROR: Company {company_id} not found", file=sys.stderr)
            sys.stderr.flush()
            current_app.logger.error(f"Company {company_id} not found")
            return
        
        print(f"[SYNC_IMPL] Step 5: Company found: {company.name} (CIF: {company.cif})", file=sys.stderr)
        sys.stderr.flush()
        
        current_app.logger.info(f"Company found: {company.name} (CIF: {company.cif})")
        current_app.logger.info(f"Auto sync enabled: {company.auto_sync_enabled}")
        
        print(f"[SYNC_IMPL] Step 6: Checking auto_sync_enabled. force={force}, auto_sync_enabled={company.auto_sync_enabled}", file=sys.stderr)
        sys.stderr.flush()
        
        # Check auto_sync_enabled unless forced (for manual syncs)
        if not force and not company.auto_sync_enabled:
            print(f"[SYNC_IMPL] EARLY RETURN: Skipping sync - auto_sync not enabled and force=False", file=sys.stderr)
            sys.stderr.flush()
            current_app.logger.info(f"Skipping sync for company {company_id} - auto_sync_enabled is False (use force=True for manual sync)")
            return
        
        print(f"[SYNC_IMPL] Step 7: Auto sync check passed, checking for ANAF token (user_id={company.user_id})", file=sys.stderr)
        sys.stderr.flush()
        
        # Check if user has valid token
        print(f"[SYNC_IMPL] Step 8: Querying token for company.user_id={company.user_id}", file=sys.stderr)
        sys.stderr.flush()
        
        anaf_token = AnafToken.query.filter_by(user_id=company.user_id).first()
        print(f"[SYNC_IMPL] Step 8: Token query returned: {anaf_token}", file=sys.stderr)
        sys.stderr.flush()
        
        if not anaf_token:
            print(f"[SYNC_IMPL] EARLY RETURN: No ANAF token found for user {company.user_id}", file=sys.stderr)
            sys.stderr.flush()
            current_app.logger.error(f"No ANAF token found for company {company_id} (user_id: {company.user_id})")
            return
        
        # CRITICAL VERIFICATION: Ensure token belongs to the company's user
        if anaf_token.user_id != company.user_id:
            print(f"[SYNC_IMPL] ERROR: Token user_id mismatch! Token.user_id={anaf_token.user_id}, Company.user_id={company.user_id}", file=sys.stderr)
            sys.stderr.flush()
            current_app.logger.error(f"Token user_id mismatch for company {company_id}: token.user_id={anaf_token.user_id}, company.user_id={company.user_id}")
            return
        
        print(f"[SYNC_IMPL] Token verification passed: token.user_id={anaf_token.user_id} matches company.user_id={company.user_id}", file=sys.stderr)
        sys.stderr.flush()
        
        print(f"[SYNC_IMPL] Step 9: ANAF token found, initializing services", file=sys.stderr)
        sys.stderr.flush()
        
        current_app.logger.info(f"ANAF token found for user {company.user_id}")
        
        # CRITICAL: Verify we're using the correct user_id for the company
        print(f"[SYNC_IMPL] CRITICAL CHECK: Company ID={company.id}, Company CIF={company.cif}, Company user_id={company.user_id}", file=sys.stderr)
        sys.stderr.flush()
        
        # Verify token belongs to company's user
        token_check = AnafToken.query.filter_by(user_id=company.user_id).first()
        if token_check:
            print(f"[SYNC_IMPL] Token verification: Found token for user_id={company.user_id}, token.user_id={token_check.user_id}", file=sys.stderr)
            sys.stderr.flush()
        else:
            print(f"[SYNC_IMPL] ERROR: No token found for company.user_id={company.user_id}", file=sys.stderr)
            sys.stderr.flush()
        
        # Initialize services with company's user_id
        print(f"[SYNC_IMPL] Initializing ANAFService with user_id={company.user_id}", file=sys.stderr)
        sys.stderr.flush()
        anaf_service = ANAFService(company.user_id)
        invoice_service = InvoiceService()
        
        print(f"[SYNC_IMPL] Step 10: Services initialized, calculating sync days for CIF {company.cif}", file=sys.stderr)
        sys.stderr.flush()
        
        # Calculate number of days to sync based on last sync date
        sync_days = _calculate_sync_days(company_id)
        
        # Determine sync type for logging
        invoice_count = Invoice.query.filter_by(company_id=company_id).count()
        sync_type = "first sync" if invoice_count == 0 else "incremental sync"
        
        current_app.logger.info(f"Sync type: {sync_type}, Fetching invoice list for CIF {company.cif} (zile={sync_days})...")
        print(f"[SYNC_IMPL] Sync type: {sync_type}, sync_days={sync_days}", file=sys.stderr)
        sys.stderr.flush()
        
        # Get invoice list using calculated days
        # The paginated endpoint (listaMesajePaginatieFactura) uses startTime/endTime timestamps
        try:
            print(f"[SYNC_IMPL] Step 11: About to call lista_mesaje_factura(cif={company.cif}, zile={sync_days})", file=sys.stderr)
            sys.stderr.flush()
            invoice_list = anaf_service.lista_mesaje_factura(company.cif, zile=sync_days)
            print(f"[SYNC_IMPL] Step 12: lista_mesaje_factura returned successfully", file=sys.stderr)
            sys.stderr.flush()
            current_app.logger.info(f"Successfully fetched invoice list from ANAF API ({sync_type}, {sync_days} days)")
        except Exception as e:
            print(f"[SYNC_IMPL] EXCEPTION in lista_mesaje_factura: {type(e).__name__}: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            current_app.logger.error(f"Error fetching invoice list for company {company_id} (CIF: {company.cif}): {str(e)}", exc_info=True)
            return
        
        print(f"[SYNC_IMPL] Step 13: Processing invoice list", file=sys.stderr)
        sys.stderr.flush()
        
        # Log raw response for debugging
        current_app.logger.info(f"=== PROCESSING INVOICE LIST FOR COMPANY {company_id} ===")
        current_app.logger.info(f"Invoice list type: {type(invoice_list)}")
        print(f"[SYNC_IMPL] Step 14: Invoice list type: {type(invoice_list)}", file=sys.stderr)
        sys.stderr.flush()
        
        if isinstance(invoice_list, dict):
            current_app.logger.info(f"Invoice list keys: {invoice_list.keys()}")
            current_app.logger.info(f"Invoice list (first 300 chars): {str(invoice_list)[:300]}")
            print(f"[SYNC_IMPL] Invoice list keys: {list(invoice_list.keys())}", file=sys.stderr)
            print(f"[SYNC_IMPL] Full API response: {invoice_list}", file=sys.stderr)
            sys.stderr.flush()
        else:
            current_app.logger.info(f"Invoice list length: {len(invoice_list) if isinstance(invoice_list, list) else 'N/A'}")
            print(f"[SYNC_IMPL] Invoice list length: {len(invoice_list) if isinstance(invoice_list, list) else 'N/A'}", file=sys.stderr)
            sys.stderr.flush()
        
        # Process invoice list according to ANAF documentation
        # Response structure: {"mesaje": [...], "serial": "", "cui": "", "titlu": ""}
        invoices_data = []
        if isinstance(invoice_list, dict):
            # Per ANAF documentation, messages are in 'mesaje' key
            invoices_data = invoice_list.get('mesaje', [])
            
            # Log metadata
            serial = invoice_list.get('serial', 'N/A')
            cui = invoice_list.get('cui', 'N/A')
            titlu = invoice_list.get('titlu', 'N/A')
            current_app.logger.info(f"Response metadata - Serial: {serial}, CUI: {cui}, Title: {titlu[:100]}")
        elif isinstance(invoice_list, list):
            # Fallback: if response is directly a list
            invoices_data = invoice_list
        
        print(f"[SYNC_IMPL] Step 15: Extracted {len(invoices_data)} messages from response", file=sys.stderr)
        sys.stderr.flush()
        
        # Check if response indicates token access issues
        if isinstance(invoice_list, dict):
            cui_field = invoice_list.get('cui', '')
            if cui_field and ',' in str(cui_field):
                # CUI field contains comma-separated list of accessible CIFs
                accessible_cifs = [c.strip() for c in str(cui_field).split(',')]
                print(f"[SYNC_IMPL] Token has access to CIFs: {accessible_cifs}", file=sys.stderr)
                sys.stderr.flush()
                
                if company.cif not in accessible_cifs:
                    error_msg = f"Token does not have access to CIF {company.cif}. Token has access to: {accessible_cifs}"
                    print(f"[SYNC_IMPL] WARNING: {error_msg}", file=sys.stderr)
                    sys.stderr.flush()
                    current_app.logger.warning(error_msg)
                    current_app.logger.warning(f"User {company.user_id} needs to re-authenticate with ANAF to get access to CIF {company.cif}")
            elif len(invoices_data) == 0 and cui_field == company.cif:
                # Empty response but CUI matches - might be legitimate (no invoices)
                print(f"[SYNC_IMPL] Empty response for CIF {company.cif} - token has access but no invoices found", file=sys.stderr)
                sys.stderr.flush()
            elif len(invoices_data) == 0:
                # Empty response - might indicate access issue
                print(f"[SYNC_IMPL] WARNING: Empty invoice list. Response CUI field: '{cui_field}', Requested CIF: {company.cif}", file=sys.stderr)
                sys.stderr.flush()
                if cui_field and cui_field != company.cif:
                    current_app.logger.warning(f"Token may not have access to CIF {company.cif}. Response CUI: {cui_field}")
        
        current_app.logger.info(f"Extracted {len(invoices_data)} messages from response")
        current_app.logger.info("=" * 60)
        
        print(f"[SYNC_IMPL] Step 16: About to process {len(invoices_data)} invoices", file=sys.stderr)
        sys.stderr.flush()
        
        synced_count = 0
        for invoice_item in invoices_data:
            print(f"[SYNC_IMPL] Processing invoice item: {invoice_item}", file=sys.stderr)
            sys.stderr.flush()
            try:
                # Extract message data per ANAF documentation structure
                # Message structure: {"data_creare": "...", "cif": "", "id_solicitare": "", 
                #                     "detalii": "", "tip": "FACTURA PRIMITA | FACTURA TRIMISA", "id": ""}
                invoice_id = None
                invoice_type = None
                data_creare = None
                detalii = None
                cif_emitent = None
                cif_beneficiar = None
                
                invoice_date_from_response = None
                
                if isinstance(invoice_item, dict):
                    # Per documentation, message ID is in 'id' field
                    invoice_id = invoice_item.get('id') or invoice_item.get('ID')
                    invoice_type = invoice_item.get('tip', '')
                    data_creare = invoice_item.get('data_creare', '')
                    detalii = invoice_item.get('detalii', '')
                    
                    # Parse data_creare from format "YYYYMMDDHHmm" to date
                    if data_creare and len(data_creare) >= 8:
                        try:
                            # Format: "202511280924" -> YYYYMMDDHHmm
                            # Extract date part (first 8 characters: YYYYMMDD)
                            date_str = data_creare[:8]
                            invoice_date_from_response = datetime.strptime(date_str, '%Y%m%d').date()
                            current_app.logger.debug(f"Parsed invoice date from data_creare '{data_creare}': {invoice_date_from_response}")
                        except ValueError as e:
                            current_app.logger.warning(f"Could not parse data_creare '{data_creare}': {str(e)}")
                    
                    # Extract CIF emitent and CIF beneficiar from detalii field
                    # Pattern: "Factura cu id_incarcare=5638821927 emisa de cif_emitent=32640679 pentru cif_beneficiar=51331025"
                    if detalii:
                        emitent_match = re.search(r'cif_emitent=(\d+)', detalii)
                        beneficiar_match = re.search(r'cif_beneficiar=(\d+)', detalii)
                        
                        if emitent_match:
                            cif_emitent = emitent_match.group(1)
                        if beneficiar_match:
                            cif_beneficiar = beneficiar_match.group(1)
                        
                    current_app.logger.info(f"Extracted CIFs from detalii - Emitent: {cif_emitent}, Beneficiar: {cif_beneficiar}")
                    if not cif_emitent or not cif_beneficiar:
                        current_app.logger.warning(f"Could not extract CIFs from detalii: {detalii}")
                elif isinstance(invoice_item, str):
                    invoice_id = invoice_item
                
                if not invoice_id:
                    current_app.logger.warning(f"Skipping invoice item without ID: {invoice_item}")
                    continue
                
                current_app.logger.info(f"Processing message ID: {invoice_id}, Type: {invoice_type}, Date: {data_creare}, CIF Emitent: {cif_emitent}, CIF Beneficiar: {cif_beneficiar}")
                
                # Check if invoice already exists
                existing = Invoice.query.filter_by(
                    company_id=company.id,
                    anaf_id=str(invoice_id)
                ).first()
                
                if existing:
                    # Update existing invoice with new fields if they're missing
                    needs_update = False
                    if not existing.invoice_type and invoice_type:
                        existing.invoice_type = invoice_type
                        needs_update = True
                    if not existing.cif_emitent and cif_emitent:
                        existing.cif_emitent = cif_emitent
                        needs_update = True
                    if not existing.cif_beneficiar and cif_beneficiar:
                        existing.cif_beneficiar = cif_beneficiar
                        needs_update = True
                    
                    if needs_update:
                        current_app.logger.info(f"Updating existing invoice {invoice_id} with missing fields")
                        
                        # Always download and parse XML to get issuer/receiver names and update date
                        # This ensures we have the most complete data
                        try:
                            file_content = anaf_service.descarcare_factura(invoice_id)
                            
                            if file_content.startswith(b'PK\x03\x04'):
                                with zipfile.ZipFile(io.BytesIO(file_content)) as zip_file:
                                    # Extract unsigned Invoice XML (not semnatura_*.xml)
                                    xml_content, xml_filename = InvoiceService.extract_unsigned_xml_from_zip(zip_file)
                                    
                                    if xml_content and xml_filename:
                                        current_app.logger.debug(f"Extracted unsigned XML from {xml_filename} for invoice {invoice_id}")
                                    elif xml_content:
                                        current_app.logger.warning(f"Extracted XML without filename for invoice {invoice_id}")
                                    else:
                                        current_app.logger.warning(f"No unsigned XML file found in ZIP for invoice {invoice_id}")
                                        xml_content = None
                            elif file_content.startswith(b'<?xml') or file_content.startswith(b'<'):
                                xml_content = file_content.decode('utf-8')
                            else:
                                xml_content = None
                            
                            if xml_content:
                                parsed_data = invoice_service.parse_xml_to_json(xml_content)
                                supplier_name, supplier_cif, invoice_date_from_xml, total_amount, currency, \
                                issuer_name, receiver_name, issuer_vat_id, receiver_vat_id = \
                                    invoice_service.extract_invoice_fields(parsed_data)
                                
                                # Update issuer and receiver names if missing or "-"
                                # Use helper function to treat "-" as missing
                                if InvoiceService._is_empty_or_dash(existing.issuer_name) and issuer_name:
                                    existing.issuer_name = issuer_name
                                    needs_update = True
                                if InvoiceService._is_empty_or_dash(existing.receiver_name) and receiver_name:
                                    existing.receiver_name = receiver_name
                                    needs_update = True
                                
                                # Update VAT IDs if missing or "-"
                                if InvoiceService._is_empty_or_dash(existing.cif_emitent) and issuer_vat_id:
                                    existing.cif_emitent = issuer_vat_id
                                    needs_update = True
                                if InvoiceService._is_empty_or_dash(existing.cif_beneficiar) and receiver_vat_id:
                                    existing.cif_beneficiar = receiver_vat_id
                                    needs_update = True
                                
                                # Update total amount if missing
                                if existing.total_amount is None and total_amount is not None:
                                    existing.total_amount = total_amount
                                    needs_update = True
                                
                                # Update currency if missing or "-"
                                if InvoiceService._is_empty_or_dash(existing.currency) and currency:
                                    existing.currency = currency
                                    needs_update = True
                                
                                # Update invoice date - prefer data_creare from response, fallback to XML
                                if invoice_date_from_response:
                                    if not existing.invoice_date or existing.invoice_date != invoice_date_from_response:
                                        existing.invoice_date = invoice_date_from_response
                                        needs_update = True
                                elif invoice_date_from_xml and not existing.invoice_date:
                                    existing.invoice_date = invoice_date_from_xml
                                    needs_update = True
                                
                                # Try to save ZIP file if we have it and it's not saved yet
                                if not existing.zip_file_path and file_content:
                                    try:
                                        zip_path = InvoiceStorageService.save_zip_file(
                                            company_id=existing.company_id,
                                            invoice_id=existing.anaf_id,
                                            zip_content=file_content,
                                            invoice_date=existing.invoice_date or invoice_date_from_response
                                        )
                                        existing.zip_file_path = zip_path
                                        needs_update = True
                                    except Exception as zip_error:
                                        current_app.logger.warning(f"Error saving ZIP file for invoice {invoice_id}: {str(zip_error)}")
                        except Exception as e:
                            current_app.logger.warning(f"Error updating invoice {invoice_id} with XML data: {str(e)}")
                        
                        if needs_update:
                            db.session.commit()
                    continue  # Skip re-processing existing invoices
                
                # Download invoice file (binary - ZIP or XML)
                try:
                    file_content = anaf_service.descarcare_factura(invoice_id)
                
                    # Handle binary content - could be ZIP or XML
                    # Check if file_content is empty
                    if not file_content:
                        current_app.logger.warning(f"Empty file content for invoice {invoice_id}")
                        continue
                    
                    # Try to detect if it's ZIP (starts with PK\x03\x04) or XML
                    if file_content.startswith(b'PK\x03\x04'):
                        # It's a ZIP file - extract unsigned Invoice XML from it
                        # ZIP contains: {id}.xml (unsigned) and semnatura_{id}.xml (signed - skip)
                        try:
                            with zipfile.ZipFile(io.BytesIO(file_content)) as zip_file:
                                # Extract unsigned Invoice XML (not semnatura_*.xml)
                                xml_content, xml_filename = InvoiceService.extract_unsigned_xml_from_zip(zip_file)
                                
                                if not xml_content:
                                    current_app.logger.error(f"No unsigned XML file found in ZIP for invoice {invoice_id}")
                                    continue
                                
                                current_app.logger.debug(f"Extracted unsigned XML from {xml_filename} for invoice {invoice_id}")
                                
                                # Verify it's unsigned Invoice XML (not signed)
                                if xml_content.strip().startswith('<Signature') or '<Signature' in xml_content[:200]:
                                    current_app.logger.error(f"ERROR: Extracted signed XML instead of unsigned for invoice {invoice_id}")
                                    continue
                                
                        except Exception as e:
                            current_app.logger.error(f"Error extracting ZIP for invoice {invoice_id}: {str(e)}", exc_info=True)
                            continue
                    elif file_content.startswith(b'<?xml') or file_content.startswith(b'<'):
                        # It's XML directly
                        xml_content = file_content.decode('utf-8')
                    else:
                        # Log more details about the unknown format
                        file_start = file_content[:50] if len(file_content) >= 50 else file_content
                        file_start_hex = file_content[:20].hex() if len(file_content) >= 20 else file_content.hex()
                        current_app.logger.warning(
                            f"Unknown file format for invoice {invoice_id}. "
                            f"File size: {len(file_content)} bytes, "
                            f"First 50 bytes (ascii): {file_start}, "
                            f"First 20 bytes (hex): {file_start_hex}"
                        )
                        continue
                        
                except Exception as e:
                    current_app.logger.warning(f"Error downloading invoice {invoice_id}: {str(e)}")
                    continue
                
                # Parse XML to JSON to extract issuer and receiver names
                parsed_data = invoice_service.parse_xml_to_json(xml_content)
                supplier_name, supplier_cif, invoice_date_from_xml, total_amount, currency, \
                issuer_name, receiver_name, issuer_vat_id, receiver_vat_id = \
                    invoice_service.extract_invoice_fields(parsed_data)
                
                # Convert Decimal values to float for JSON serialization
                # json_content field requires JSON-serializable values
                def convert_decimals_to_float(obj):
                    """Recursively convert Decimal objects to float for JSON serialization"""
                    from decimal import Decimal
                    if isinstance(obj, Decimal):
                        return float(obj)
                    elif isinstance(obj, dict):
                        return {key: convert_decimals_to_float(value) for key, value in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_decimals_to_float(item) for item in obj]
                    elif isinstance(obj, date):
                        # Convert date objects to ISO format strings
                        return obj.isoformat() if hasattr(obj, 'isoformat') else str(obj)
                    else:
                        return obj
                
                # Convert parsed_data to JSON-serializable format
                json_serializable_data = convert_decimals_to_float(parsed_data)
                
                # Use VAT IDs from XML if available, otherwise from detalii field
                final_cif_emitent = issuer_vat_id or cif_emitent
                final_cif_beneficiar = receiver_vat_id or cif_beneficiar
                
                # Use invoice_date from response (data_creare) if available, otherwise from XML
                final_invoice_date = invoice_date_from_response or invoice_date_from_xml
                
                current_app.logger.info(f"Extracted from XML - Issuer: {issuer_name}, Receiver: {receiver_name}, Date: {final_invoice_date}, Amount: {total_amount}, Currency: {currency}")
                
                # Save ZIP file to disk
                zip_file_path = None
                try:
                    if file_content.startswith(b'PK\x03\x04'):
                        # It's a ZIP file - save it
                        zip_file_path = InvoiceStorageService.save_zip_file(
                            company_id=company.id,
                            invoice_id=str(invoice_id),
                            zip_content=file_content,
                            invoice_date=final_invoice_date
                        )
                        current_app.logger.debug(f"Saved ZIP file for invoice {invoice_id} to {zip_file_path}")
                except Exception as zip_error:
                    current_app.logger.warning(f"Error saving ZIP file for invoice {invoice_id}: {str(zip_error)}")
                
                # Create invoice record
                invoice = Invoice(
                    company_id=company.id,
                    anaf_id=str(invoice_id),
                    invoice_type=invoice_type,  # "FACTURA PRIMITA" or "FACTURA TRIMISA"
                    supplier_name=supplier_name,
                    supplier_cif=supplier_cif,
                    cif_emitent=final_cif_emitent,  # From XML or detalii
                    cif_beneficiar=final_cif_beneficiar,  # From XML or detalii
                    issuer_name=issuer_name,  # Extracted from XML
                    receiver_name=receiver_name,  # Extracted from XML
                    invoice_date=final_invoice_date,  # From data_creare or XML
                    total_amount=total_amount,
                    currency=currency,  # Extracted from XML
                    xml_content=xml_content,
                    json_content=json_serializable_data,  # JSON-serializable version of parsed_data
                    zip_file_path=zip_file_path,  # Path to saved ZIP file
                    synced_at=datetime.now(timezone.utc)
                )
                
                db.session.add(invoice)
                synced_count += 1
                
            except Exception as e:
                current_app.logger.error(f"Error processing invoice item: {str(e)}", exc_info=True)
                # Rollback on error to allow processing of remaining invoices
                try:
                    db.session.rollback()
                except Exception as rollback_error:
                    current_app.logger.error(f"Error during rollback: {str(rollback_error)}")
                continue
        
        try:
            db.session.commit()
        except Exception as commit_error:
            current_app.logger.error(f"Error committing invoice batch: {str(commit_error)}", exc_info=True)
            db.session.rollback()
            raise
        current_app.logger.info(f"=== SYNC COMPLETE FOR COMPANY {company_id} ===")
        current_app.logger.info(f"Sync type: {sync_type}, Days synced: {sync_days}")
        current_app.logger.info(f"Successfully synced {synced_count} new invoices for company {company_id} ({company.name})")
        current_app.logger.info("=" * 60)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"=== SYNC FAILED FOR COMPANY {company_id} ===")
        current_app.logger.error(f"Error syncing company {company_id}: {str(e)}", exc_info=True)
        current_app.logger.error("=" * 60)
        # Don't re-raise - let the route handle error messaging to user

def sync_all_companies():
    """Sync invoices for all companies with auto_sync enabled"""
    global app_instance
    if not app_instance:
        # Fallback: try to use current_app if available
        try:
            with current_app.app_context():
                _sync_all_companies_impl()
        except RuntimeError:
            # No application context available
            return
    else:
        # Use stored app instance
        with app_instance.app_context():
            _sync_all_companies_impl()

def _sync_all_companies_impl():
    """Internal implementation of sync_all_companies"""
    companies = Company.query.filter_by(auto_sync_enabled=True).all()
    
    for company in companies:
        # Check sync interval
        last_sync = db.session.query(db.func.max(Invoice.synced_at))\
            .filter_by(company_id=company.id)\
            .scalar()
        
        if last_sync:
            # Ensure last_sync is timezone-aware
            if last_sync.tzinfo is None:
                last_sync = last_sync.replace(tzinfo=timezone.utc)
            
            hours_since_sync = (datetime.now(timezone.utc) - last_sync).total_seconds() / 3600
            if hours_since_sync < company.sync_interval_hours:
                continue  # Skip if within sync interval
        
        sync_company_invoices(company.id)

def reparse_all_invoices():
    """
    Reparse all invoices with missing critical fields
    Runs as a background job to fill in missing data
    """
    global app_instance
    
    if not app_instance:
        try:
            with current_app.app_context():
                _reparse_all_invoices_impl()
        except RuntimeError:
            return
    else:
        with app_instance.app_context():
            _reparse_all_invoices_impl()

def _reparse_all_invoices_impl():
    """Internal implementation of reparse_all_invoices"""
    try:
        current_app.logger.info("=== STARTING INVOICE REPARSE JOB ===")
        
        # Find invoices missing critical fields
        incomplete_invoices = Invoice.query.filter(
            db.or_(
                Invoice.issuer_name.is_(None),
                Invoice.receiver_name.is_(None),
                Invoice.cif_emitent.is_(None),
                Invoice.cif_beneficiar.is_(None),
                Invoice.total_amount.is_(None),
                Invoice.currency.is_(None)
            )
        ).all()
        
        total_count = len(incomplete_invoices)
        current_app.logger.info(f"Found {total_count} invoices with missing fields to reparse")
        
        updated_count = 0
        error_count = 0
        
        # Process in batches to avoid memory issues
        batch_size = 50
        for i in range(0, total_count, batch_size):
            batch = incomplete_invoices[i:i + batch_size]
            
            for invoice in batch:
                try:
                    # Check if invoice still needs reparsing (might have been updated by another process)
                    if not InvoiceService.is_invoice_incomplete(invoice):
                        continue
                    
                    # Reparse invoice XML
                    updated = InvoiceService.reparse_invoice(invoice)
                    
                    if updated:
                        updated_count += 1
                        db.session.commit()
                        current_app.logger.debug(f"Updated invoice {invoice.id} (ANAF ID: {invoice.anaf_id})")
                    else:
                        # Refresh from database to check current state
                        db.session.refresh(invoice)
                        if InvoiceService.is_invoice_incomplete(invoice):
                            current_app.logger.warning(f"Could not update invoice {invoice.id} (ANAF ID: {invoice.anaf_id}) - XML may be incomplete or corrupted")
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    current_app.logger.error(f"Error reparsing invoice {invoice.id}: {str(e)}", exc_info=True)
                    db.session.rollback()
                    continue
            
            # Commit batch
            try:
                db.session.commit()
            except Exception as commit_error:
                current_app.logger.error(f"Error committing reparse batch: {str(commit_error)}")
                db.session.rollback()
        
        current_app.logger.info(f"=== REPARSE JOB COMPLETE ===")
        current_app.logger.info(f"Total processed: {total_count}, Updated: {updated_count}, Errors: {error_count}")
        current_app.logger.info("=" * 60)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"=== REPARSE JOB FAILED ===")
        current_app.logger.error(f"Error in reparse job: {str(e)}", exc_info=True)
        current_app.logger.error("=" * 60)

def init_scheduler(app):
    """Initialize APScheduler for background sync jobs"""
    global scheduler, app_instance
    
    if scheduler is not None:
        return  # Already initialized
    
    # Store app instance for use in scheduled jobs
    app_instance = app
    
    scheduler = BackgroundScheduler(daemon=True)
    
    # Schedule sync job to run every hour
    scheduler.add_job(
        func=sync_all_companies,
        trigger=IntervalTrigger(hours=1),
        id='sync_all_companies',
        name='Sync invoices for all companies',
        replace_existing=True
    )
    
    # Schedule reparse job to run once per day at 2 AM
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(
        func=reparse_all_invoices,
        trigger=CronTrigger(hour=2, minute=0),
        id='reparse_all_invoices',
        name='Reparse invoices with missing fields',
        replace_existing=True
    )
    
    scheduler.start()
    app.logger.info("Background scheduler started with sync and reparse jobs")

def schedule_sync_job(company_id, force=False):
    """
    Schedule a one-time sync job to run in the background immediately.
    
    Args:
        company_id: ID of the company to sync
        force: If True, sync even if auto_sync_enabled is False (for manual syncs)
    
    Returns:
        True if job was scheduled successfully, False otherwise
    """
    global scheduler
    
    if scheduler is None:
        # Scheduler not initialized
        try:
            from flask import current_app
            current_app.logger.error("Scheduler not initialized - cannot schedule sync job")
        except RuntimeError:
            import logging
            logging.error("Cannot schedule sync job - scheduler not initialized")
        return False
    
    # Generate unique job ID to avoid conflicts
    job_id = f"sync_company_{company_id}_{datetime.now(timezone.utc).timestamp()}"
    
    try:
        # Schedule job to run immediately (use current time + 1 second to ensure it's in the future)
        run_date = datetime.now(timezone.utc) + timedelta(seconds=1)
        scheduler.add_job(
            func=sync_company_invoices,
            trigger=DateTrigger(run_date=run_date),
            args=[company_id],
            kwargs={'force': force},
            id=job_id,
            name=f'Sync company {company_id}',
            replace_existing=False  # Don't replace - each sync is a separate job
        )
        
        # Log the scheduled job
        try:
            from flask import current_app
            current_app.logger.info(f"Scheduled background sync job for company {company_id} (job_id: {job_id})")
        except RuntimeError:
            import logging
            logging.info(f"Scheduled background sync job for company {company_id} (job_id: {job_id})")
        
        return True
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error scheduling sync job for company {company_id}: {str(e)}", exc_info=True)
        except RuntimeError:
            import logging
            logging.error(f"Error scheduling sync job for company {company_id}: {str(e)}", exc_info=True)
        return False

