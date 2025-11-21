from functools import wraps
from flask import redirect, url_for, flash, render_template
from flask_login import current_user

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def approved_required(f):
    """Decorator to require approved user account"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        if not current_user.is_approved:
            flash('Your account is pending admin approval. Please wait for an administrator to approve your registration.', 'warning')
            return render_template('auth/pending_approval.html', email=current_user.email)
        return f(*args, **kwargs)
    return decorated_function

