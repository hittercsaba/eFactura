from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import Company, Invoice, db
from app.utils.decorators import approved_required
from sqlalchemy import desc

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
@approved_required
def index():
    """Dashboard with invoice listing"""
    # Get user's companies
    companies = Company.query.filter_by(user_id=current_user.id).all()
    
    if not companies:
        return redirect(url_for('anaf.connect'))
    
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
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    invoices = Invoice.query.filter_by(company_id=selected_company.id)\
        .order_by(desc(Invoice.synced_at))\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template(
        'dashboard.html',
        companies=companies,
        selected_company=selected_company,
        invoices=invoices
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

