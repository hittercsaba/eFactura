"""
API Routes - RESTful API for invoice access
Conforms to standard API best practices
"""
from flask import Blueprint, request, jsonify, current_app, url_for
from app.models import db, Invoice, ApiKey, Company
from werkzeug.security import check_password_hash
from sqlalchemy import desc, or_
from datetime import datetime, timezone
import re

api_bp = Blueprint('api', __name__)

def get_api_key_from_request():
    """
    Extract and validate API key from request headers
    Returns: (api_key_obj, error_response) tuple
    """
    api_key = request.headers.get('X-API-KEY')
    
    if not api_key:
        return None, (jsonify({
            'error': 'Unauthorized',
            'message': 'Missing X-API-KEY header',
            'code': 'MISSING_API_KEY'
        }), 401)
    
    # Validate API key format (should be base64url safe string)
    if not re.match(r'^[A-Za-z0-9_-]+$', api_key) or len(api_key) < 32:
        return None, (jsonify({
            'error': 'Unauthorized',
            'message': 'Invalid API key format',
            'code': 'INVALID_API_KEY_FORMAT'
        }), 401)
    
    # Find API key by checking all active keys
    # SECURITY: This is O(n) but necessary since keys are hashed
    api_key_obj = None
    active_keys = ApiKey.query.filter_by(is_active=True).all()
    
    # Limit brute force attempts
    if len(active_keys) > 1000:
        return None, (jsonify({
            'error': 'Service Unavailable',
            'message': 'Service temporarily unavailable',
            'code': 'SERVICE_UNAVAILABLE'
        }), 503)
    
    for key_obj in active_keys:
        try:
            if check_password_hash(key_obj.key_hash, api_key):
                api_key_obj = key_obj
                break
        except Exception as e:
            current_app.logger.warning(f"Error checking API key hash: {str(e)}")
            continue
    
    if not api_key_obj:
        return None, (jsonify({
            'error': 'Unauthorized',
            'message': 'Invalid API key',
            'code': 'INVALID_API_KEY'
        }), 401)
    
    # Update last used timestamp
    try:
        api_key_obj.last_used_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error updating API key last_used_at: {str(e)}")
        db.session.rollback()
    
    return api_key_obj, None

def validate_pagination_params():
    """Validate and return pagination parameters"""
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    
    try:
        per_page = min(max(1, int(request.args.get('per_page', 50))), 100)  # Max 100 per page
    except (ValueError, TypeError):
        per_page = 50
    
    return page, per_page

def format_invoice_response(invoice, include_details=False, api_key=None):
    """Format invoice data for API response"""
    data = {
        'id': invoice.id,
        'anaf_id': invoice.anaf_id,
        'invoice_type': invoice.invoice_type,
        'cif_emitent': invoice.cif_emitent,
        'cif_beneficiar': invoice.cif_beneficiar,
        'issuer_name': invoice.issuer_name,
        'receiver_name': invoice.receiver_name,
        'invoice_date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        'total_amount': float(invoice.total_amount) if invoice.total_amount else None,
        'synced_at': invoice.synced_at.isoformat() if invoice.synced_at else None
    }
    
    # Only include supplier_name and supplier_cif if they are not null
    # These are legacy fields, issuer_name and receiver_name are preferred
    if invoice.supplier_name:
        data['supplier_name'] = invoice.supplier_name
    if invoice.supplier_cif:
        data['supplier_cif'] = invoice.supplier_cif
    
    # Add download URL for invoice XML/ZIP
    # Generate URL to our own server's download endpoint
    # The client will need to use the same X-API-KEY header for authentication
    try:
        # Generate absolute URL to our server's download endpoint
        download_url = url_for('api.download_invoice', invoice_id=invoice.id, _external=True)
        data['download_url'] = download_url
    except RuntimeError:
        # Fallback if no request context: construct URL from request object
        if request:
            base_url = request.url_root.rstrip('/')
            data['download_url'] = f"{base_url}/api/v1/invoices/{invoice.id}/download"
        else:
            # Last resort: relative URL (client must construct full URL)
            data['download_url'] = f"/api/v1/invoices/{invoice.id}/download"
    
    # Include JSON content only if explicitly requested (for detailed view)
    if include_details and invoice.json_content:
        data['details'] = invoice.json_content
    
    return data

@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Enhanced health check endpoint with dependency checks
    
    Returns:
    - 200: All systems healthy
    - 503: One or more systems unhealthy
    """
    from sqlalchemy import text
    
    status = {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0.0',
        'checks': {}
    }
    
    # Database connectivity check
    try:
        db.session.execute(text('SELECT 1'))
        status['checks']['database'] = 'healthy'
    except Exception as e:
        status['status'] = 'unhealthy'
        status['checks']['database'] = f'unhealthy: {str(e)}'
        current_app.logger.error(f"Health check: Database check failed: {str(e)}")
    
    # Determine HTTP status code
    status_code = 200 if status['status'] == 'healthy' else 503
    
    return jsonify(status), status_code

@api_bp.route('/invoices', methods=['GET'])
def get_invoices():
    """
    Get invoices for the company associated with the API key
    
    Query Parameters:
    - page (int): Page number (default: 1)
    - per_page (int): Items per page (default: 50, max: 100)
    - supplier_cif (str): Filter by supplier CIF
    - date_from (str): Filter invoices from date (ISO format: YYYY-MM-DD)
    - date_to (str): Filter invoices to date (ISO format: YYYY-MM-DD)
    
    Headers:
    - X-API-KEY (required): API key for authentication
    
    Returns:
    - 200: Success with paginated invoice list
    - 401: Unauthorized (missing or invalid API key)
    - 503: Service unavailable
    """
    # Authenticate request
    api_key_obj, error_response = get_api_key_from_request()
    if error_response:
        return error_response
    
    # Get pagination parameters
    page, per_page = validate_pagination_params()
    
    # Build query for company's invoices
    invoices_query = Invoice.query.filter_by(company_id=api_key_obj.company_id)
    
    # Apply filters
    supplier_cif = request.args.get('supplier_cif')
    if supplier_cif:
        invoices_query = invoices_query.filter_by(supplier_cif=supplier_cif)
    
    date_from = request.args.get('date_from')
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            invoices_query = invoices_query.filter(Invoice.invoice_date >= date_from_obj)
        except ValueError:
            return jsonify({
                'error': 'Bad Request',
                'message': 'Invalid date_from format. Use YYYY-MM-DD',
                'code': 'INVALID_DATE_FORMAT'
            }), 400
    
    date_to = request.args.get('date_to')
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            invoices_query = invoices_query.filter(Invoice.invoice_date <= date_to_obj)
        except ValueError:
            return jsonify({
                'error': 'Bad Request',
                'message': 'Invalid date_to format. Use YYYY-MM-DD',
                'code': 'INVALID_DATE_FORMAT'
            }), 400
    
    # Order by synced_at descending (newest first)
    invoices_query = invoices_query.order_by(desc(Invoice.synced_at))
    
    # Paginate
    try:
        pagination = invoices_query.paginate(page=page, per_page=per_page, error_out=False)
    except Exception as e:
        current_app.logger.error(f"Error paginating invoices: {str(e)}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An error occurred while fetching invoices',
            'code': 'INTERNAL_ERROR'
        }), 500
    
    # Format response (request context is available here)
    invoices_data = [format_invoice_response(invoice, api_key=api_key_obj) for invoice in pagination.items]
    
    return jsonify({
        'data': invoices_data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        },
        'meta': {
            'company_id': api_key_obj.company_id,
            'company_cif': api_key_obj.company.cif if api_key_obj.company else None
        }
    }), 200

@api_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    """
    Get a single invoice by ID
    
    Path Parameters:
    - invoice_id (int): Invoice ID
    
    Headers:
    - X-API-KEY (required): API key for authentication
    
    Returns:
    - 200: Success with invoice details
    - 401: Unauthorized (missing or invalid API key)
    - 404: Invoice not found or not accessible
    """
    # Authenticate request
    api_key_obj, error_response = get_api_key_from_request()
    if error_response:
        return error_response
    
    # Get invoice and verify it belongs to the company
    invoice = Invoice.query.filter_by(
        id=invoice_id,
        company_id=api_key_obj.company_id
    ).first()
    
    if not invoice:
        return jsonify({
            'error': 'Not Found',
            'message': 'Invoice not found or not accessible',
            'code': 'INVOICE_NOT_FOUND'
        }), 404
    
    # Return invoice with full details
    return jsonify({
        'data': format_invoice_response(invoice, include_details=True, api_key=api_key_obj)
    }), 200

@api_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors for API routes"""
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found',
        'code': 'NOT_FOUND'
    }), 404

@api_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors for API routes"""
    current_app.logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred',
        'code': 'INTERNAL_ERROR'
    }), 500

@api_bp.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit errors"""
    return jsonify({
        'error': 'Too Many Requests',
        'message': 'Rate limit exceeded. Please try again later.',
        'code': 'RATE_LIMIT_EXCEEDED'
    }), 429

@api_bp.route('/invoices/<int:invoice_id>/download', methods=['GET'])
def download_invoice(invoice_id):
    """
    Download invoice as ZIP file (contains XML)
    
    Path Parameters:
    - invoice_id (int): Invoice ID
    
    Headers:
    - X-API-KEY (required): API key for authentication
    
    Returns:
    - 200: ZIP file with invoice XML
    - 401: Unauthorized (missing or invalid API key)
    - 404: Invoice not found or not accessible
    """
    # Authenticate request
    api_key_obj, error_response = get_api_key_from_request()
    if error_response:
        return error_response
    
    # Get invoice and verify it belongs to the company
    invoice = Invoice.query.filter_by(
        id=invoice_id,
        company_id=api_key_obj.company_id
    ).first()
    
    if not invoice:
        return jsonify({
            'error': 'Not Found',
            'message': 'Invoice not found or not accessible',
            'code': 'INVOICE_NOT_FOUND'
        }), 404
    
    safe_filename = f"invoice_{invoice.anaf_id}.zip".replace('/', '_').replace('\\', '_')
    
    # Tier 1: Try to re-download from ANAF API (fresh data)
    try:
        from app.services.anaf_service import ANAFService
        anaf_service = ANAFService(api_key_obj.company.user_id)
        zip_content = anaf_service.descarcare_factura(invoice.anaf_id)
        
        # Return ZIP file
        from flask import Response
        return Response(
            zip_content,
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename={safe_filename}',
                'X-Content-Type-Options': 'nosniff'
            }
        )
    except Exception as e:
        from flask import current_app
        current_app.logger.debug(f"ANAF API download failed for invoice {invoice.anaf_id}: {str(e)}")
        pass
    
    # Tier 2: Try to serve from saved ZIP file on disk
    if invoice.zip_file_path:
        try:
            from app.services.storage_service import InvoiceStorageService
            zip_content = InvoiceStorageService.read_zip_file(invoice.zip_file_path)
            if zip_content:
                from flask import current_app, Response
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
            from flask import current_app
            current_app.logger.warning(f"Error reading saved ZIP file for invoice {invoice.anaf_id}: {str(e)}")
            pass
    
    # Tier 3: Final fallback - create ZIP from stored XML
    if invoice.xml_content:
        import zipfile
        import io
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(f'invoice_{invoice.anaf_id}.xml', invoice.xml_content)
        
        zip_buffer.seek(0)
        from flask import current_app, Response
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
    return jsonify({
        'error': 'Not Available',
        'message': 'Invoice file not available',
        'code': 'INVOICE_FILE_NOT_AVAILABLE'
    }), 404
