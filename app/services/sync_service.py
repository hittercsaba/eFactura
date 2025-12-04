from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta, timezone
from flask import current_app
import zipfile
import io
import re
from app.models import db, Company, Invoice, AnafToken
from app.services.anaf_service import ANAFService
from app.services.invoice_service import InvoiceService

scheduler = None
app_instance = None  # Store app instance for scheduler context

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
        
        print(f"[SYNC_IMPL] Step 10: Services initialized, fetching invoice list for CIF {company.cif}", file=sys.stderr)
        sys.stderr.flush()
        
        current_app.logger.info(f"Fetching invoice list for CIF {company.cif} (zile=60)...")
        
        # Get invoice list (using 60 days - using paginated endpoint which supports 1-90 days)
        # The paginated endpoint (listaMesajePaginatieFactura) uses startTime/endTime timestamps
        try:
            print(f"[SYNC_IMPL] Step 11: About to call lista_mesaje_factura(cif={company.cif}, zile=60)", file=sys.stderr)
            sys.stderr.flush()
            invoice_list = anaf_service.lista_mesaje_factura(company.cif, zile=60)
            print(f"[SYNC_IMPL] Step 12: lista_mesaje_factura returned successfully", file=sys.stderr)
            sys.stderr.flush()
            current_app.logger.info(f"Successfully fetched invoice list from ANAF API")
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
                                    # Find invoice XML file (exclude signature files)
                                    all_xml_files = [f for f in zip_file.namelist() if f.endswith('.xml')]
                                    invoice_xml_files = [f for f in all_xml_files if not f.startswith('semnatura_')]
                                    
                                    if invoice_xml_files:
                                        xml_content = zip_file.read(invoice_xml_files[0]).decode('utf-8')
                                    elif all_xml_files:
                                        xml_content = zip_file.read(all_xml_files[0]).decode('utf-8')
                                    else:
                                        xml_content = None
                            elif file_content.startswith(b'<?xml') or file_content.startswith(b'<'):
                                xml_content = file_content.decode('utf-8')
                            else:
                                xml_content = None
                            
                            if xml_content:
                                parsed_data = invoice_service.parse_xml_to_json(xml_content)
                                supplier_name, supplier_cif, invoice_date_from_xml, total_amount, issuer_name, receiver_name = \
                                    invoice_service.extract_invoice_fields(parsed_data)
                                
                                # Update issuer and receiver names if missing
                                if not existing.issuer_name and issuer_name:
                                    existing.issuer_name = issuer_name
                                    needs_update = True
                                if not existing.receiver_name and receiver_name:
                                    existing.receiver_name = receiver_name
                                    needs_update = True
                                
                                # Update invoice date - prefer data_creare from response, fallback to XML
                                if invoice_date_from_response:
                                    if not existing.invoice_date or existing.invoice_date != invoice_date_from_response:
                                        existing.invoice_date = invoice_date_from_response
                                        needs_update = True
                                elif invoice_date_from_xml and not existing.invoice_date:
                                    existing.invoice_date = invoice_date_from_xml
                                    needs_update = True
                        except Exception as e:
                            current_app.logger.warning(f"Error updating invoice {invoice_id} with XML data: {str(e)}")
                        
                        if needs_update:
                            db.session.commit()
                    continue  # Skip re-processing existing invoices
                
                # Download invoice file (binary - ZIP or XML)
                try:
                    file_content = anaf_service.descarcare_factura(invoice_id)
                
                    # Handle binary content - could be ZIP or XML
                    # Try to detect if it's ZIP (starts with PK\x03\x04) or XML
                    if file_content.startswith(b'PK\x03\x04'):
                        # It's a ZIP file - extract XML from it
                        try:
                            with zipfile.ZipFile(io.BytesIO(file_content)) as zip_file:
                                # Find invoice XML file in ZIP (exclude signature files)
                                # Signature files are named like "semnatura_*.xml"
                                # Invoice files are named like "{id_solicitare}.xml"
                                all_xml_files = [f for f in zip_file.namelist() if f.endswith('.xml')]
                                # Filter out signature files
                                invoice_xml_files = [f for f in all_xml_files if not f.startswith('semnatura_')]
                                
                                if invoice_xml_files:
                                    # Use the first non-signature XML file (should be the invoice)
                                    xml_content = zip_file.read(invoice_xml_files[0]).decode('utf-8')
                                    current_app.logger.debug(f"Extracted invoice XML from {invoice_xml_files[0]} (ZIP contained {len(all_xml_files)} XML files)")
                                elif all_xml_files:
                                    # Fallback: use first XML file if no non-signature files found
                                    xml_content = zip_file.read(all_xml_files[0]).decode('utf-8')
                                    current_app.logger.warning(f"Using signature XML file {all_xml_files[0]} as fallback for invoice {invoice_id}")
                                else:
                                    current_app.logger.warning(f"No XML file found in ZIP for invoice {invoice_id}")
                                    continue
                        except Exception as e:
                            current_app.logger.error(f"Error extracting ZIP for invoice {invoice_id}: {str(e)}")
                            continue
                    elif file_content.startswith(b'<?xml') or file_content.startswith(b'<'):
                        # It's XML directly
                        xml_content = file_content.decode('utf-8')
                    else:
                        current_app.logger.warning(f"Unknown file format for invoice {invoice_id}")
                        continue
                        
                except Exception as e:
                    current_app.logger.warning(f"Error downloading invoice {invoice_id}: {str(e)}")
                    continue
                
                # Parse XML to JSON to extract issuer and receiver names
                parsed_data = invoice_service.parse_xml_to_json(xml_content)
                supplier_name, supplier_cif, invoice_date_from_xml, total_amount, issuer_name, receiver_name = \
                    invoice_service.extract_invoice_fields(parsed_data)
                
                # Use invoice_date from response (data_creare) if available, otherwise from XML
                final_invoice_date = invoice_date_from_response or invoice_date_from_xml
                
                current_app.logger.info(f"Extracted from XML - Issuer: {issuer_name}, Receiver: {receiver_name}, Date: {final_invoice_date}")
                
                # Create invoice record
                invoice = Invoice(
                    company_id=company.id,
                    anaf_id=str(invoice_id),
                    invoice_type=invoice_type,  # "FACTURA PRIMITA" or "FACTURA TRIMISA"
                    supplier_name=supplier_name,
                    supplier_cif=supplier_cif,
                    cif_emitent=cif_emitent,  # Extracted from detalii
                    cif_beneficiar=cif_beneficiar,  # Extracted from detalii
                    issuer_name=issuer_name,  # Extracted from XML
                    receiver_name=receiver_name,  # Extracted from XML
                    invoice_date=final_invoice_date,  # From data_creare or XML
                    total_amount=total_amount,
                    xml_content=xml_content,
                    json_content=parsed_data,
                    synced_at=datetime.now(timezone.utc)
                )
                
                db.session.add(invoice)
                synced_count += 1
                
            except Exception as e:
                current_app.logger.error(f"Error processing invoice item: {str(e)}")
                continue
        
        db.session.commit()
        current_app.logger.info(f"=== SYNC COMPLETE FOR COMPANY {company_id} ===")
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
    
    scheduler.start()
    app.logger.info("Background scheduler started")

