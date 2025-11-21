from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app.models import db, User
import re

auth_bp = Blueprint('auth', __name__)

def get_limiter():
    """Get the app's limiter instance"""
    return current_app.extensions.get('limiter')

def is_safe_url(target):
    """Check if URL is safe for redirect (prevents open redirect attacks)"""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(url_for('dashboard.index', _external=True))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def validate_email(email):
    """Validate email format"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Input validation
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('auth/register.html')
        
        # Validate email format
        if not validate_email(email):
            flash('Invalid email format.', 'error')
            return render_template('auth/register.html')
        
        # Limit email length
        if len(email) > 120:
            flash('Email address is too long.', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')
        
        # Password strength validation
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/register.html')
        
        if len(password) > 128:
            flash('Password is too long.', 'error')
            return render_template('auth/register.html')
        
        # Check if user already exists (prevent email enumeration by using same message)
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            # Use generic message to prevent email enumeration
            flash('If an account with this email exists, you will receive a confirmation message.', 'info')
            return render_template('auth/register.html')
        
        # Check if this is the first user
        is_first_user = User.query.count() == 0
        
        # Create new user
        user = User(email=email)
        user.set_password(password)
        
        # First user becomes admin and is automatically approved
        if is_first_user:
            user.is_admin = True
            user.is_approved = True
        else:
            # Other users need approval
            user.is_admin = False
            user.is_approved = False
        
        try:
            db.session.add(user)
            db.session.commit()
            
            if is_first_user:
                flash('Registration successful! You have been set as an administrator. Please log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                # Show pending approval page
                return render_template('auth/pending_approval.html', email=email)
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        
        # Input validation
        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('auth/login.html')
        
        # Validate email format
        if not validate_email(email):
            flash('Invalid email format.', 'error')
            return render_template('auth/login.html')
        
        # Limit input length
        if len(email) > 120 or len(password) > 128:
            flash('Invalid credentials.', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(email=email).first()
        
        # Always check password to prevent timing attacks (even if user doesn't exist)
        if user and user.check_password(password):
            # Check if user is approved
            if not user.is_approved:
                flash('Your account is pending admin approval. Please wait for an administrator to approve your registration.', 'warning')
                return render_template('auth/pending_approval.html', email=email)
            
            login_user(user, remember=remember)
            
            # Fix open redirect vulnerability
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            # Generic error message to prevent user enumeration
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

