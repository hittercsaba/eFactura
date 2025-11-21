from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Company
from app.utils.decorators import approved_required

companies_bp = Blueprint('companies', __name__)

@companies_bp.route('/')
@login_required
@approved_required
def index():
    """List user's companies"""
    companies = Company.query.filter_by(user_id=current_user.id).all()
    return render_template('companies.html', companies=companies)

@companies_bp.route('/add', methods=['POST'])
@login_required
@approved_required
def add():
    """Add a new company manually"""
    cif = request.form.get('cif', '').strip()
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    auto_sync = request.form.get('auto_sync') == 'on'
    
    # Input validation
    if not cif or not name:
        flash('CIF and name are required.', 'error')
        return redirect(url_for('companies.index'))
    
    # Validate CIF format (Romanian CIF is typically 2-10 digits)
    if len(cif) > 20 or not cif.replace('-', '').replace(' ', '').isalnum():
        flash('Invalid CIF format.', 'error')
        return redirect(url_for('companies.index'))
    
    # Validate name length
    if len(name) > 200:
        flash('Company name is too long.', 'error')
        return redirect(url_for('companies.index'))
    
    # Validate address length
    if address and len(address) > 1000:
        flash('Address is too long.', 'error')
        return redirect(url_for('companies.index'))
    
    # Validate sync interval
    try:
        sync_interval = int(request.form.get('sync_interval_hours', 24))
        if sync_interval < 1 or sync_interval > 8760:  # Max 1 year
            sync_interval = 24
    except (ValueError, TypeError):
        sync_interval = 24
    
    # Check if company already exists for this user
    existing = Company.query.filter_by(
        user_id=current_user.id,
        cif=cif
    ).first()
    
    if existing:
        flash(f'Company with CIF {cif} already exists.', 'error')
        return redirect(url_for('companies.index'))
    
    # Create new company
    company = Company(
        user_id=current_user.id,
        cif=cif,
        name=name,
        address=address,
        auto_sync_enabled=auto_sync,
        sync_interval_hours=sync_interval
    )
    
    try:
        db.session.add(company)
        db.session.commit()
        flash(f'Company {name} added successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')
    
    return redirect(url_for('companies.index'))

@companies_bp.route('/<int:company_id>/edit', methods=['POST'])
@login_required
@approved_required
def edit(company_id):
    """Edit company settings"""
    company = Company.query.filter_by(
        id=company_id,
        user_id=current_user.id
    ).first_or_404()
    
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    auto_sync = request.form.get('auto_sync') == 'on'
    
    # Input validation
    if name and len(name) > 200:
        flash('Company name is too long.', 'error')
        return redirect(url_for('companies.index'))
    
    if address and len(address) > 1000:
        flash('Address is too long.', 'error')
        return redirect(url_for('companies.index'))
    
    # Validate sync interval
    try:
        sync_interval = int(request.form.get('sync_interval_hours', 24))
        if sync_interval < 1 or sync_interval > 8760:  # Max 1 year
            sync_interval = 24
    except (ValueError, TypeError):
        sync_interval = 24
    
    if name:
        company.name = name
    if address:
        company.address = address
    company.auto_sync_enabled = auto_sync
    company.sync_interval_hours = sync_interval
    
    try:
        db.session.commit()
        flash('Company updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')
    
    return redirect(url_for('companies.index'))

@companies_bp.route('/<int:company_id>/delete', methods=['POST'])
@login_required
@approved_required
def delete(company_id):
    """Delete a company"""
    company = Company.query.filter_by(
        id=company_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        db.session.delete(company)
        db.session.commit()
        flash('Company deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')
    
    return redirect(url_for('companies.index'))

