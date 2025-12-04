from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user
from flask import current_app
from app.models import db, User
from app.utils.decorators import admin_required
from app.utils.impersonation import is_impersonating, get_original_admin
from datetime import datetime

users_bp = Blueprint('users', __name__)

@users_bp.route('/users')
@login_required
def index():
    """User management page for admins"""
    # Check if user is admin (either directly or as original admin when impersonating)
    original_admin = get_original_admin() if is_impersonating() else current_user
    if not original_admin or not original_admin.is_admin:
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get all users
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Count pending approvals
    pending_count = User.query.filter_by(is_approved=False).count()
    
    return render_template(
        'users/index.html',
        users=users,
        pending_count=pending_count,
        original_admin=original_admin
    )

@users_bp.route('/users/approve/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    """Approve a user"""
    user = User.query.get_or_404(user_id)
    
    if user.is_approved:
        flash(f'User {user.email} is already approved.', 'info')
    else:
        user.is_approved = True
        db.session.commit()
        flash(f'User {user.email} has been approved successfully.', 'success')
    
    return redirect(url_for('users.index'))

@users_bp.route('/users/reject/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reject_user(user_id):
    """Reject/Delete a user registration"""
    user = User.query.get_or_404(user_id)
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('users.index'))
    
    # Prevent deleting other admins
    if user.is_admin:
        flash('You cannot delete admin accounts.', 'error')
        return redirect(url_for('users.index'))
    
    email = user.email
    db.session.delete(user)
    db.session.commit()
    flash(f'User {email} has been rejected and removed.', 'success')
    
    return redirect(url_for('users.index'))

@users_bp.route('/users/toggle-admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    """Toggle admin status of a user"""
    user = User.query.get_or_404(user_id)
    
    # Prevent removing admin from yourself
    if user.id == current_user.id:
        flash('You cannot remove admin privileges from yourself.', 'error')
        return redirect(url_for('users.index'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = 'granted' if user.is_admin else 'revoked'
    flash(f'Admin privileges {status} for {user.email}.', 'success')
    
    return redirect(url_for('users.index'))


@users_bp.route('/users/impersonate/<int:user_id>', methods=['POST'])
@login_required
def impersonate_user(user_id):
    """Start impersonating a user"""
    # Get the actual admin user (not the impersonated one if already impersonating)
    original_admin = get_original_admin() if is_impersonating() else current_user
    
    # Verify the original admin is actually an admin
    if not original_admin or not original_admin.is_admin:
        flash('You do not have permission to impersonate users.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get target user
    target_user = User.query.get_or_404(user_id)
    
    # Prevent impersonating yourself
    if target_user.id == original_admin.id:
        flash('You cannot impersonate yourself.', 'error')
        return redirect(url_for('users.index'))
    
    # Store impersonation info in session
    session['_impersonating_from_user_id'] = original_admin.id
    session['_impersonating_user_id'] = target_user.id
    
    # Update Flask-Login session to use the impersonated user
    login_user(target_user, remember=False)
    
    # Log the impersonation
    current_app.logger.info(
        f"Admin {original_admin.email} (ID: {original_admin.id}) started impersonating user {target_user.email} (ID: {target_user.id})"
    )
    
    flash(f'You are now viewing as {target_user.email}.', 'info')
    return redirect(url_for('dashboard.index'))


@users_bp.route('/users/stop-impersonate', methods=['POST'])
@login_required
def stop_impersonate():
    """Stop impersonating and return to admin account"""
    if not is_impersonating():
        flash('You are not currently impersonating any user.', 'warning')
        return redirect(url_for('dashboard.index'))
    
    original_admin = get_original_admin()
    impersonated_user = current_user
    
    if not original_admin:
        # Session corrupted, clear impersonation and redirect to login
        session.pop('_impersonating_from_user_id', None)
        session.pop('_impersonating_user_id', None)
        flash('Impersonation session invalid. Please log in again.', 'error')
        return redirect(url_for('auth.login'))
    
    # Clear impersonation session
    session.pop('_impersonating_from_user_id', None)
    session.pop('_impersonating_user_id', None)
    
    # Restore original admin session
    login_user(original_admin, remember=False)
    
    # Log the stop action
    current_app.logger.info(
        f"Admin {original_admin.email} (ID: {original_admin.id}) stopped impersonating user {impersonated_user.email} (ID: {impersonated_user.id})"
    )
    
    flash(f'Stopped impersonating. You are now logged in as {original_admin.email}.', 'success')
    return redirect(url_for('users.index'))

