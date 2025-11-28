from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta, timezone
from flask import current_app
from app.models import db, Company, Invoice, AnafToken
from app.services.anaf_service import ANAFService
from app.services.invoice_service import InvoiceService

scheduler = None

def sync_company_invoices(company_id):
    """Sync invoices for a specific company"""
    with current_app.app_context():
        try:
            company = Company.query.get(company_id)
            if not company or not company.auto_sync_enabled:
                return
            
            # Check if user has valid token
            anaf_token = AnafToken.query.filter_by(user_id=company.user_id).first()
            if not anaf_token:
                current_app.logger.warning(f"No ANAF token for company {company_id}")
                return
            
            # Initialize services
            anaf_service = ANAFService(company.user_id)
            invoice_service = InvoiceService()
            
            # Get invoice list
            try:
                invoice_list = anaf_service.lista_mesaje_factura(company.cif, zile=60)
            except Exception as e:
                current_app.logger.error(f"Error fetching invoice list for company {company_id}: {str(e)}")
                return
            
            # Log raw response for debugging
            current_app.logger.info(f"=== PROCESSING INVOICE LIST FOR COMPANY {company_id} ===")
            current_app.logger.info(f"Invoice list type: {type(invoice_list)}")
            if isinstance(invoice_list, dict):
                current_app.logger.info(f"Invoice list keys: {invoice_list.keys()}")
                current_app.logger.info(f"Invoice list (first 300 chars): {str(invoice_list)[:300]}")
            else:
                current_app.logger.info(f"Invoice list length: {len(invoice_list) if isinstance(invoice_list, list) else 'N/A'}")
            
            # Process invoice list (structure may vary)
            invoices_data = []
            if isinstance(invoice_list, dict):
                invoices_data = invoice_list.get('listaMesajeFactura', []) or \
                              invoice_list.get('data', []) or \
                              invoice_list.get('invoices', []) or \
                              invoice_list.get('mesaje', [])
            elif isinstance(invoice_list, list):
                invoices_data = invoice_list
            
            current_app.logger.info(f"Extracted {len(invoices_data)} invoices from response")
            current_app.logger.info("=" * 60)
            
            synced_count = 0
            for invoice_item in invoices_data:
                try:
                    # Extract invoice ID (structure may vary)
                    invoice_id = None
                    if isinstance(invoice_item, dict):
                        invoice_id = invoice_item.get('id') or \
                                   invoice_item.get('ID') or \
                                   invoice_item.get('invoiceId') or \
                                   invoice_item.get('invoice_id')
                    elif isinstance(invoice_item, str):
                        invoice_id = invoice_item
                    
                    if not invoice_id:
                        continue
                    
                    # Check if invoice already exists
                    existing = Invoice.query.filter_by(
                        company_id=company.id,
                        anaf_id=str(invoice_id)
                    ).first()
                    
                    if existing:
                        continue  # Skip already synced invoices
                    
                    # Download invoice XML
                    try:
                        xml_content = anaf_service.descarcare_factura(invoice_id)
                    except Exception as e:
                        current_app.logger.warning(f"Error downloading invoice {invoice_id}: {str(e)}")
                        continue
                    
                    # Parse XML to JSON
                    parsed_data = invoice_service.parse_xml_to_json(xml_content)
                    supplier_name, supplier_cif, invoice_date, total_amount = \
                        invoice_service.extract_invoice_fields(parsed_data)
                    
                    # Create invoice record
                    invoice = Invoice(
                        company_id=company.id,
                        anaf_id=str(invoice_id),
                        supplier_name=supplier_name,
                        supplier_cif=supplier_cif,
                        invoice_date=invoice_date,
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
            current_app.logger.info(f"Synced {synced_count} invoices for company {company_id}")
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error syncing company {company_id}: {str(e)}")

def sync_all_companies():
    """Sync invoices for all companies with auto_sync enabled"""
    with current_app.app_context():
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
    global scheduler
    
    if scheduler is not None:
        return  # Already initialized
    
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

