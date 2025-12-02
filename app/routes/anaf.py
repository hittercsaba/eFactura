from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user
from app.models import db, AnafOAuthConfig, Company, AnafToken
from app.services.oauth_service import OAuthService
from app.services.anaf_service import ANAFService
from app.utils.decorators import approved_required
from urllib.parse import urlparse
import secrets

def get_base_url():
    """Get the base URL, ensuring HTTPS when behind a proxy"""
    # Check if we're behind a proxy with X-Forwarded-Proto
    if request.headers.get('X-Forwarded-Proto') == 'https':
        scheme = 'https'
    elif request.is_secure:
        scheme = 'https'
    else:
        scheme = request.scheme
    
    # Get host from X-Forwarded-Host or request
    host = request.headers.get('X-Forwarded-Host', request.host)
    
    # Remove port if it's standard (80 for http, 443 for https)
    if ':' in host:
        hostname, port = host.split(':', 1)
        if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
            host = hostname
    
    return f"{scheme}://{host}"

anaf_bp = Blueprint('anaf', __name__)

@anaf_bp.route('/test')
@login_required
def test_connection():
    """Test page for diagnosing ANAF OAuth connection issues"""
    oauth_config = AnafOAuthConfig.query.first()
    return render_template('anaf/test_connection.html', oauth_config=oauth_config)

@anaf_bp.route('/admin/config', methods=['GET', 'POST'])
@login_required
@approved_required
def admin_config():
    """Admin-only: Configure system-wide ANAF OAuth settings"""
    if not current_user.is_admin:
        flash('Only administrators can configure ANAF OAuth settings.', 'error')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        client_id = request.form.get('client_id', '').strip()
        client_secret = request.form.get('client_secret', '').strip()
        redirect_uri = request.form.get('redirect_uri', '').strip()
        
        # Get system-wide OAuth config (should be only one)
        oauth_config = AnafOAuthConfig.query.first()
        is_update = oauth_config is not None
        
        # Input validation
        if not client_id or not redirect_uri:
            flash('Client ID and Redirect URI are required.', 'error')
            return render_template('anaf/admin_config.html', oauth_config=oauth_config)
        
        # For new config, client_secret is required
        # For update, it's optional (only update if provided)
        if not is_update and not client_secret:
            flash('Client Secret is required for new OAuth configuration.', 'error')
            return render_template('anaf/admin_config.html', oauth_config=oauth_config)
        
        # Validate lengths
        if len(client_id) > 255:
            flash('Client ID is too long.', 'error')
            return render_template('anaf/admin_config.html', oauth_config=oauth_config)
        
        if client_secret and len(client_secret) > 255:
            flash('Client secret is too long.', 'error')
            return render_template('anaf/admin_config.html', oauth_config=oauth_config)
        
        if len(redirect_uri) > 500:
            flash('Redirect URI is too long.', 'error')
            return render_template('anaf/admin_config.html', oauth_config=oauth_config)
        
        # Validate redirect_uri format
        try:
            parsed = urlparse(redirect_uri)
            if not parsed.scheme or not parsed.netloc:
                flash('Invalid redirect URI format.', 'error')
                return render_template('anaf/admin_config.html', oauth_config=oauth_config)
            if parsed.scheme not in ('http', 'https'):
                flash('Redirect URI must use http or https.', 'error')
                return render_template('anaf/admin_config.html', oauth_config=oauth_config)
        except Exception:
            flash('Invalid redirect URI format.', 'error')
            return render_template('anaf/admin_config.html', oauth_config=oauth_config)
        
        # Encrypt client_secret before storing (only if provided)
        from app.utils.encryption import encrypt_data
        
        if oauth_config:
            # Update existing config
            oauth_config.client_id = client_id
            # Only update client_secret if a new one is provided
            if client_secret:
                encrypted_secret = encrypt_data(client_secret)
                if not encrypted_secret:
                    flash('Error encrypting client secret.', 'error')
                    return render_template('anaf/admin_config.html', oauth_config=oauth_config)
                oauth_config.client_secret = encrypted_secret
            oauth_config.redirect_uri = redirect_uri
        else:
            # Create new config (client_secret required)
            encrypted_secret = encrypt_data(client_secret)
            if not encrypted_secret:
                flash('Error encrypting client secret.', 'error')
                return render_template('anaf/admin_config.html')
            oauth_config = AnafOAuthConfig(
                client_id=client_id,
                client_secret=encrypted_secret,
                redirect_uri=redirect_uri,
                created_by=current_user.id
            )
            db.session.add(oauth_config)
        
        try:
            db.session.commit()
            current_app.logger.info(f"OAuth config {'updated' if is_update else 'created'} by admin user {current_user.id}")
            flash('ANAF OAuth configuration saved successfully.', 'success')
            return redirect(url_for('anaf.admin_config'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving OAuth config: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            return render_template('anaf/admin_config.html', oauth_config=oauth_config)
    
    # GET request - show the config form
    oauth_config = AnafOAuthConfig.query.first()
    return render_template('anaf/admin_config.html', oauth_config=oauth_config)

@anaf_bp.route('/connect')
@login_required
@approved_required
def connect():
    """User: Connect to ANAF using their certificate"""
    # Check if system OAuth config exists
    oauth_config = AnafOAuthConfig.query.first()
    
    if not oauth_config:
        flash('ANAF OAuth is not configured. Please contact your administrator.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Generate state for OAuth flow
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_user_id'] = current_user.id
    
    # Get authorization URL
    oauth_service = OAuthService(current_user.id)
    auth_url = oauth_service.get_authorization_url(state=state)
    
    # Log user authentication attempt
    current_app.logger.info(f"User {current_user.id} ({current_user.email}) initiating ANAF authentication")
    current_app.logger.info(f"Redirecting browser to: {auth_url}")
    
    # Direct redirect to ANAF (no template to avoid HTML encoding issues)
    return redirect(auth_url)

@anaf_bp.route('/callback')
@login_required
@approved_required
def callback():
    """OAuth callback handler - receives authorization code from ANAF"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    # Get user_id from session (set during connect)
    user_id = session.get('oauth_user_id', current_user.id)
    
    # Log callback details
    current_app.logger.info(f"=== ANAF OAUTH CALLBACK FOR USER {user_id} ===")
    current_app.logger.info(f"Callback URL: {request.url}")
    current_app.logger.info(f"Has Authorization Code: {bool(code)}")
    if code:
        current_app.logger.info(f"Authorization Code: {code[:20]}...{code[-20:] if len(code) > 40 else ''}")
    current_app.logger.info(f"State from ANAF: {state}")
    current_app.logger.info(f"State in Session: {session.get('oauth_state')}")
    current_app.logger.info(f"Error from ANAF: {error}")
    current_app.logger.info(f"Error Description: {request.args.get('error_description', 'N/A')}")
    current_app.logger.info("=" * 60)
    
    # Verify state
    if state != session.get('oauth_state'):
        current_app.logger.error(f"OAuth state mismatch! Expected: {session.get('oauth_state')}, Got: {state}")
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))
    
    if error:
        error_description = request.args.get('error_description', '')
        error_uri = request.args.get('error_uri', '')
        
        # Log detailed error information
        current_app.logger.error(
            f"OAuth authorization error for user {current_user.id}: "
            f"error={error}, description={error_description}, uri={error_uri}"
        )
        
        # Clear OAuth state to prevent loops
        session.pop('oauth_state', None)
        session.pop('oauth_user_id', None)
        
        # Provide more helpful error messages
        if error == 'access_denied':
            error_msg = (
                'ANAF access was denied. This could be due to:\n'
                '1. You cancelled the certificate selection or declined authorization\n'
                '2. The digital certificate is not registered in ANAF\'s SPV system\n'
                '3. The redirect URI does not match what is registered with ANAF\n'
                '4. You do not have access to e-Factura services\n'
                '5. The OAuth configuration is incorrect'
            )
            if error_description:
                error_msg += f'\n\nANAF Error: {error_description}'
        else:
            error_msg = f'OAuth error: {error}'
            if error_description:
                error_msg += f' - {error_description}'
        
        flash(error_msg, 'error')
        return redirect(url_for('dashboard.index'))
    
    if not code:
        flash('No authorization code received from ANAF.', 'error')
        session.pop('oauth_state', None)
        session.pop('oauth_user_id', None)
        return redirect(url_for('dashboard.index'))
    
    try:
        # Exchange code for token (using user_id from session)
        oauth_service = OAuthService(user_id)
        token_data = oauth_service.exchange_code_for_token(code)
        
        flash('ANAF account connected successfully!', 'success')
        
        # Clear OAuth state and user_id from session
        session.pop('oauth_state', None)
        session.pop('oauth_user_id', None)
        
        # Try to discover companies
        try:
            anaf_service = ANAFService(current_user.id)
            companies_data = anaf_service.get_user_companies()
            
            if companies_data and isinstance(companies_data, list):
                # Create company records
                for company_data in companies_data:
                    cif = company_data.get('cif') or company_data.get('CIF') or company_data.get('taxId')
                    name = company_data.get('name') or company_data.get('Name') or company_data.get('companyName')
                    
                    if cif:
                        # Check if company already exists
                        existing = Company.query.filter_by(
                            user_id=current_user.id,
                            cif=str(cif)
                        ).first()
                        
                        if not existing:
                            company = Company(
                                user_id=current_user.id,
                                cif=str(cif),
                                name=name or f'Company {cif}',
                                auto_sync_enabled=True,
                                sync_interval_hours=24
                            )
                            db.session.add(company)
                
                db.session.commit()
                flash('Companies discovered and added automatically.', 'success')
            else:
                flash('No companies found automatically. You can add them manually.', 'info')
                
        except Exception as e:
            current_app.logger.warning(f"Company discovery failed: {str(e)}")
            flash('Could not automatically discover companies. You can add them manually.', 'info')
        
        return redirect(url_for('dashboard.index'))
        
    except Exception as e:
        current_app.logger.error(f"OAuth callback error: {str(e)}")
        session.pop('oauth_state', None)
        session.pop('oauth_user_id', None)
        flash(f'Error connecting ANAF account: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))

@anaf_bp.route('/sync/<int:company_id>', methods=['POST'])
@login_required
@approved_required
def sync_company(company_id):
    """Manually trigger sync for a company"""
    company = Company.query.filter_by(
        id=company_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        from app.services.sync_service import sync_company_invoices
        sync_company_invoices(company_id)
        flash(f'Invoice sync started for {company.name}.', 'success')
    except Exception as e:
        current_app.logger.error(f"Manual sync error: {str(e)}")
        flash('Error starting sync. Please try again.', 'error')
    
    return redirect(url_for('dashboard.index'))


@anaf_bp.route('/disconnect', methods=['POST'])
@login_required
@approved_required
def disconnect():
    """Delete the OAuth token and force re-authentication"""
    try:
        # Find and delete the token for current user
        token = AnafToken.query.filter_by(user_id=current_user.id).first()
        
        if token:
            db.session.delete(token)
            db.session.commit()
            current_app.logger.info(f"User {current_user.id} disconnected ANAF account (token deleted)")
            flash('ANAF account disconnected. You will need to re-authenticate to sync invoices.', 'success')
        else:
            flash('No ANAF connection found to disconnect.', 'info')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error disconnecting ANAF: {str(e)}")
        flash('Error disconnecting ANAF account. Please try again.', 'error')
    
    return redirect(url_for('dashboard.index'))


@anaf_bp.route('/status')
@login_required
@approved_required
def status():
    """Show ANAF connection status and token info"""
    token = AnafToken.query.filter_by(user_id=current_user.id).first()
    oauth_config = AnafOAuthConfig.query.first()
    
    token_info = None
    if token:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        # Ensure token_expiry is timezone-aware
        token_expiry = token.token_expiry
        if token_expiry and token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=timezone.utc)
        
        is_expired = token_expiry and token_expiry < now if token_expiry else True
        
        token_info = {
            'has_access_token': bool(token.access_token),
            'has_refresh_token': bool(token.refresh_token),
            'token_expiry': token_expiry,
            'is_expired': is_expired,
            'updated_at': token.updated_at
        }
    
    return render_template('anaf/status.html', 
                           token_info=token_info, 
                           oauth_config=oauth_config)

