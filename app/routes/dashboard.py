from flask import Blueprint, render_template, session, redirect, url_for, request, flash, send_file, Response, current_app
from flask_login import login_required, current_user
from app.models import Company, Invoice, User, ApiKey, db
from app.utils.decorators import approved_required
from app.services.anaf_service import ANAFService
from sqlalchemy import desc, asc, func
from datetime import datetime, timezone
import zipfile
import io

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
@approved_required
def index():
    """Dashboard with invoice listing"""
    # Calculate statistics
    stats = {}
    today = datetime.now(timezone.utc).date()
    
    if current_user.is_admin:
        # Admin statistics - system-wide
        stats['active_users'] = User.query.filter_by(is_approved=True).count()
        stats['inactive_users'] = User.query.filter_by(is_approved=False).count()
        stats['total_companies'] = Company.query.count()
        stats['total_invoices'] = Invoice.query.count()
        
        # Last sync datetime (max synced_at across all invoices)
        last_sync = db.session.query(func.max(Invoice.synced_at)).scalar()
        stats['last_sync_datetime'] = last_sync
        
        # Invoices synced today
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
        stats['invoices_synced_today'] = Invoice.query.filter(
            Invoice.synced_at >= today_start,
            Invoice.synced_at <= today_end
        ).count()
        
        # API key statistics
        stats['total_api_keys'] = ApiKey.query.count()
        stats['api_keys_used'] = ApiKey.query.filter(ApiKey.last_used_at.isnot(None)).count()
        stats['api_keys_used_today'] = ApiKey.query.filter(
            ApiKey.last_used_at >= today_start,
            ApiKey.last_used_at <= today_end
        ).count()
    else:
        # Normal user statistics - only their companies
        user_company_ids = [c.id for c in Company.query.filter_by(user_id=current_user.id).all()]
        
        if user_company_ids:
            stats['total_invoices'] = Invoice.query.filter(Invoice.company_id.in_(user_company_ids)).count()
            
            # Last sync datetime (max synced_at from user's invoices)
            last_sync = db.session.query(func.max(Invoice.synced_at)).filter(
                Invoice.company_id.in_(user_company_ids)
            ).scalar()
            stats['last_sync_datetime'] = last_sync
            
            # Invoices synced today
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
            today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
            stats['invoices_synced_today'] = Invoice.query.filter(
                Invoice.company_id.in_(user_company_ids),
                Invoice.synced_at >= today_start,
                Invoice.synced_at <= today_end
            ).count()
        else:
            stats['total_invoices'] = 0
            stats['last_sync_datetime'] = None
            stats['invoices_synced_today'] = 0
    
    # Get user's companies
    companies = Company.query.filter_by(user_id=current_user.id).all()
    
    # If no companies, show empty state (don't auto-redirect)
    if not companies:
        return render_template(
            'dashboard.html',
            companies=[],
            selected_company=None,
            invoices=None,
            active_tab='all',
            sort_by='invoice_date',
            sort_order='desc',
            stats=stats
        )
    
    # Get selected company from session or default to first
    selected_company_id = session.get('selected_company_id')
    if not selected_company_id:
        selected_company_id = companies[0].id
        session['selected_company_id'] = selected_company_id
    
    # Verify selected company belongs to user
    selected_company = Company.query.filter_by(
        id=selected_company_id,
        user_id=current_user.id
    ).first()
    
    if not selected_company:
        selected_company = companies[0]
        session['selected_company_id'] = selected_company.id
    
    # Get invoices for selected company
    # Validate and sanitize input parameters
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    
    invoice_type_filter = request.args.get('type', 'all').strip().lower()
    # Validate filter value to prevent injection
    if invoice_type_filter not in ('all', 'received', 'sent'):
        invoice_type_filter = 'all'
    
    # Get sorting parameters
    sort_by = request.args.get('sort_by', 'invoice_date').strip().lower()
    sort_order = request.args.get('sort_order', 'desc').strip().lower()
    
    # Validate sort_by against allowed columns
    allowed_sort_columns = {
        'invoice_date': Invoice.invoice_date,
        'total_amount': Invoice.total_amount,
        'synced_at': Invoice.synced_at,
        'anaf_id': Invoice.anaf_id
    }
    
    if sort_by not in allowed_sort_columns:
        sort_by = 'invoice_date'
    
    # Validate sort_order
    if sort_order not in ('asc', 'desc'):
        sort_order = 'desc'
    
    per_page = 50
    
    # Build query with optional type filter
    query = Invoice.query.filter_by(company_id=selected_company.id)
    
    if invoice_type_filter == 'received':
        query = query.filter_by(invoice_type='FACTURA PRIMITA')
    elif invoice_type_filter == 'sent':
        query = query.filter_by(invoice_type='FACTURA TRIMISA')
    # else 'all' - no filter
    
    # Apply sorting
    sort_column = allowed_sort_columns[sort_by]
    if sort_order == 'asc':
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))
    
    invoices = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template(
        'dashboard.html',
        companies=companies,
        selected_company=selected_company,
        invoices=invoices,
        active_tab=invoice_type_filter,
        sort_by=sort_by,
        sort_order=sort_order,
        stats=stats
    )

@dashboard_bp.route('/switch-company', methods=['POST'])
@login_required
@approved_required
def switch_company():
    """Switch active company"""
    # Input validation
    try:
        company_id = int(request.form.get('company_id', 0))
        if company_id <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid company selected.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Verify company belongs to user
    company = Company.query.filter_by(
        id=company_id,
        user_id=current_user.id
    ).first()
    
    if company:
        session['selected_company_id'] = company_id
        flash(f'Switched to {company.name}', 'success')
    else:
        flash('Invalid company selected.', 'error')
    
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/invoice/<int:invoice_id>/download')
@login_required
@approved_required
def download_invoice(invoice_id):
    """Download invoice as ZIP file"""
    # Get invoice and verify it belongs to user's company
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Verify invoice belongs to user's company
    if invoice.company.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))
    
    safe_filename = f"invoice_{invoice.anaf_id}.zip".replace('/', '_').replace('\\', '_')
    
    # Tier 1: Try to re-download from ANAF API (fresh data)
    try:
        anaf_service = ANAFService(current_user.id)
        zip_content = anaf_service.descarcare_factura(invoice.anaf_id)
        
        # Return ZIP file
        return Response(
            zip_content,
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename={safe_filename}',
                'X-Content-Type-Options': 'nosniff'
            }
        )
    except Exception as e:
        current_app.logger.debug(f"ANAF API download failed for invoice {invoice.anaf_id}: {str(e)}")
        pass
    
    # Tier 2: Try to serve from saved ZIP file on disk
    if invoice.zip_file_path:
        try:
            from app.services.storage_service import InvoiceStorageService
            zip_content = InvoiceStorageService.read_zip_file(invoice.zip_file_path)
            if zip_content:
                current_app.logger.debug(f"Serving invoice {invoice.anaf_id} from saved ZIP file")
                return Response(
                    zip_content,
                    mimetype='application/zip',
                    headers={
                        'Content-Disposition': f'attachment; filename={safe_filename}',
                        'X-Content-Type-Options': 'nosniff'
                    }
                )
        except Exception as e:
            current_app.logger.warning(f"Error reading saved ZIP file for invoice {invoice.anaf_id}: {str(e)}")
            pass
    
    # Tier 3: Final fallback - create ZIP from stored XML
    if invoice.xml_content:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(f'invoice_{invoice.anaf_id}.xml', invoice.xml_content)
        
        zip_buffer.seek(0)
        current_app.logger.debug(f"Creating ZIP from stored XML for invoice {invoice.anaf_id}")
        
        return Response(
            zip_buffer.read(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename={safe_filename}',
                'X-Content-Type-Options': 'nosniff'
            }
        )
    
    # If all else fails, return error
    flash('Invoice file not available.', 'error')
    return redirect(url_for('dashboard.index'))

