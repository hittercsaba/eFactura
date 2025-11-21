from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import db, Company, ApiKey
from app.utils.decorators import approved_required
from werkzeug.security import generate_password_hash
import secrets

api_settings_bp = Blueprint('api_settings', __name__)

@api_settings_bp.route('/')
@login_required
@approved_required
def index():
    """API key management page"""
    companies = Company.query.filter_by(user_id=current_user.id).all()
    
    # Get API keys for each company
    companies_with_keys = []
    for company in companies:
        api_keys = ApiKey.query.filter_by(company_id=company.id).all()
        companies_with_keys.append({
            'company': company,
            'api_keys': api_keys
        })
    
    return render_template('api_settings.html', companies_with_keys=companies_with_keys)

@api_settings_bp.route('/generate', methods=['POST'])
@login_required
@approved_required
def generate_key():
    """Generate a new API key for a company"""
    # Input validation
    try:
        company_id = int(request.form.get('company_id', 0))
        if company_id <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid company ID.', 'error')
        return redirect(url_for('api_settings.index'))
    
    # Verify company belongs to user
    company = Company.query.filter_by(
        id=company_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Generate API key (32 bytes = 256 bits, base64 encoded)
    api_key = secrets.token_urlsafe(32)
    
    # Generate hash (now supports up to 255 characters to match User.password_hash)
    key_hash = generate_password_hash(api_key)
    
    # Create API key record
    api_key_obj = ApiKey(
        company_id=company.id,
        key_hash=key_hash,
        is_active=True
    )
    
    try:
        db.session.add(api_key_obj)
        db.session.commit()
        
        current_app.logger.info(f"API key generated successfully for company {company.id} (user {current_user.id})")
        
        # Show the key to user (only time it will be visible)
        flash(f'API Key generated for {company.name}. Save it now - you won\'t be able to see it again!', 'success')
        companies_with_keys = _get_companies_with_keys()
        return render_template('api_settings.html', 
                             new_api_key=api_key,
                             new_api_key_company=company.name,
                             companies_with_keys=companies_with_keys)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error generating API key: {str(e)}", exc_info=True)
        flash(f'Error generating API key: {str(e)}. Please try again.', 'error')
        return redirect(url_for('api_settings.index'))

@api_settings_bp.route('/revoke/<int:key_id>', methods=['POST'])
@login_required
@approved_required
def revoke_key(key_id):
    """Revoke (deactivate) an API key"""
    api_key = ApiKey.query.get_or_404(key_id)
    
    # Verify key belongs to user's company
    if api_key.company.user_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('api_settings.index'))
    
    api_key.is_active = False
    
    try:
        db.session.commit()
        flash('API key revoked successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error revoking API key. Please try again.', 'error')
    
    return redirect(url_for('api_settings.index'))

def _get_companies_with_keys():
    """Helper to get companies with their API keys"""
    companies = Company.query.filter_by(user_id=current_user.id).all()
    companies_with_keys = []
    for company in companies:
        api_keys = ApiKey.query.filter_by(company_id=company.id).all()
        companies_with_keys.append({
            'company': company,
            'api_keys': api_keys
        })
    return companies_with_keys

