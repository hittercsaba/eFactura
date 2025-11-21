from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, User
from app.utils.decorators import admin_required
from datetime import datetime

users_bp = Blueprint('users', __name__)

@users_bp.route('/users')
@login_required
@admin_required
def index():
    """User management page for admins"""
    # Get all users
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Count pending approvals
    pending_count = User.query.filter_by(is_approved=False).count()
    
    return render_template(
        'users/index.html',
        users=users,
        pending_count=pending_count
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

