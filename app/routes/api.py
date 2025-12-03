"""
API Routes - RESTful API for invoice access
Conforms to standard API best practices
"""
from flask import Blueprint, request, jsonify, current_app
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

def format_invoice_response(invoice, include_details=False):
    """Format invoice data for API response"""
    data = {
        'id': invoice.id,
        'anaf_id': invoice.anaf_id,
        'supplier_name': invoice.supplier_name,
        'supplier_cif': invoice.supplier_cif,
        'invoice_date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        'total_amount': float(invoice.total_amount) if invoice.total_amount else None,
        'synced_at': invoice.synced_at.isoformat() if invoice.synced_at else None
    }
    
    # Include JSON content only if explicitly requested (for detailed view)
    if include_details and invoice.json_content:
        data['details'] = invoice.json_content
    
    return data

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0.0'
    }), 200

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
    
    # Format response
    invoices_data = [format_invoice_response(invoice) for invoice in pagination.items]
    
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
        'data': format_invoice_response(invoice, include_details=True)
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
