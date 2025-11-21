from flask import Blueprint, request, jsonify, current_app
from app.models import db, Invoice, ApiKey
from werkzeug.security import check_password_hash
from sqlalchemy import desc
from datetime import datetime, timezone

api_bp = Blueprint('api', __name__)

@api_bp.route('/invoices', methods=['GET'])
def get_invoices():
    """Get invoices for the company associated with the API key"""
    api_key = request.headers.get('X-API-KEY')
    
    if not api_key:
        return jsonify({'error': 'Missing X-API-KEY header'}), 401
    
    # Find API key by checking all active keys
    # SECURITY: This is still O(n) but necessary since keys are hashed
    # Consider adding a key_prefix column for faster lookups in future
    api_key_obj = None
    active_keys = ApiKey.query.filter_by(is_active=True).all()
    
    # Limit brute force attempts by limiting number of keys checked
    if len(active_keys) > 1000:
        return jsonify({'error': 'Service temporarily unavailable'}), 503
    
    for key_obj in active_keys:
        try:
            if check_password_hash(key_obj.key_hash, api_key):
                api_key_obj = key_obj
                break
        except Exception:
            # Log error but continue checking other keys
            continue
    
    if not api_key_obj:
        return jsonify({'error': 'Invalid API key'}), 401
    
    # Update last used timestamp
    api_key_obj.last_used_at = datetime.now(timezone.utc)
    db.session.commit()
    
    # Get pagination parameters with validation
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    
    try:
        per_page = min(max(1, int(request.args.get('per_page', 50))), 100)  # Max 100 per page
    except (ValueError, TypeError):
        per_page = 50
    
    # Get invoices for the company
    invoices_query = Invoice.query.filter_by(company_id=api_key_obj.company_id)\
        .order_by(desc(Invoice.synced_at))
    
    pagination = invoices_query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format response (exclude sensitive json_content to prevent data leakage)
    invoices_data = []
    for invoice in pagination.items:
        invoices_data.append({
            'id': invoice.id,
            'anaf_id': invoice.anaf_id,
            'supplier_name': invoice.supplier_name,
            'supplier_cif': invoice.supplier_cif,
            'invoice_date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
            'total_amount': float(invoice.total_amount) if invoice.total_amount else None,
            'synced_at': invoice.synced_at.isoformat() if invoice.synced_at else None
            # json_content excluded for security - contains full invoice data
        })
    
    return jsonify({
        'invoices': invoices_data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })

