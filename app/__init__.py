from flask import Flask, redirect, url_for, request
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import config
from app.models import db

# Initialize extensions
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

def create_app(config_name='default'):
    """Application factory"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Handle reverse proxy (for correct URL generation behind nginx/apache)
    # This ensures request.url_root uses https when behind a proxy
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,  # Number of proxies
        x_proto=1,  # Trust X-Forwarded-Proto header
        x_host=1,  # Trust X-Forwarded-Host header
        x_port=1,  # Trust X-Forwarded-Port header
        x_prefix=1  # Trust X-Forwarded-Prefix header
    )
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Make CSRF token available in all templates
    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)
    
    # Helper function to get correct base URL (handles proxy)
    @app.context_processor
    def inject_base_url():
        def get_base_url():
            """Get base URL with correct protocol when behind proxy"""
            if request.headers.get('X-Forwarded-Proto') == 'https':
                scheme = 'https'
            elif request.is_secure:
                scheme = 'https'
            else:
                scheme = request.scheme
            
            host = request.headers.get('X-Forwarded-Host', request.host)
            # Remove standard ports
            if ':' in host:
                hostname, port = host.split(':', 1)
                if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
                    host = hostname
            
            return f"{scheme}://{host}"
        
        return dict(get_base_url=get_base_url)
    
    # Security headers
    @app.after_request
    def set_security_headers(response):
        """Add security headers to all responses"""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        # Content Security Policy
        # Allow Bootstrap and Bootstrap Icons from cdn.jsdelivr.net
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none';"
        )
        response.headers['Content-Security-Policy'] = csp
        return response
    
    # User loader for Flask-Login
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            # Handle case where database migration hasn't been run yet
            return None
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.companies import companies_bp
    from app.routes.anaf import anaf_bp
    from app.routes.api import api_bp
    from app.routes.api_settings import api_settings_bp
    from app.routes.users import users_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(companies_bp, url_prefix='/companies')
    app.register_blueprint(anaf_bp, url_prefix='/anaf')
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(api_settings_bp, url_prefix='/api-settings')
    app.register_blueprint(users_bp)
    
    # Apply rate limiting to specific routes after blueprint registration
    from app.routes.api import get_invoices, get_invoice, health_check
    from app.routes.auth import register, login
    limiter.limit("100 per hour")(get_invoices)
    limiter.limit("100 per hour")(get_invoice)
    limiter.limit("200 per hour")(health_check)  # Health check can be called more frequently
    limiter.limit("5 per hour")(register)
    limiter.limit("10 per hour")(login)
    
    # Root route
    @app.route('/')
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        # User is authenticated - check approval status
        try:
            # Use getattr with default True to handle case where migration hasn't been run
            is_approved = getattr(current_user, 'is_approved', True)
            if not is_approved:
                from flask import render_template
                email = getattr(current_user, 'email', '')
                return render_template('auth/pending_approval.html', email=email)
        except Exception as e:
            # If there's an error (e.g., migration not run), just redirect to dashboard
            app.logger.warning(f"Error checking user approval status: {str(e)}")
        
        # User is authenticated and approved (or check failed) - redirect to dashboard
        return redirect(url_for('dashboard.index'))
    
    # Initialize scheduler (only when not running migrations)
    # Skip scheduler initialization if we're in a migration context
    import sys
    import inspect
    is_migration_context = False
    
    # Check if we're being called from alembic/migrations
    for frame_info in inspect.stack():
        if 'alembic' in frame_info.filename or 'migrations' in frame_info.filename:
            is_migration_context = True
            break
    
    # Also check command line arguments
    if not is_migration_context:
        is_migration_context = any('migrate' in arg or 'db' in arg for arg in sys.argv)
    
    if not is_migration_context:
        try:
            from app.services.sync_service import init_scheduler
            init_scheduler(app)
        except Exception as e:
            app.logger.warning(f"Could not initialize scheduler: {str(e)}")
    
    return app

