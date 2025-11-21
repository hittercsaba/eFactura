from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user
from app.models import db, AnafOAuthConfig, Company
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

@anaf_bp.route('/connect', methods=['GET', 'POST'])
@login_required
@approved_required
def connect():
    """Connect ANAF account - OAuth configuration and initiation"""
    if request.method == 'POST':
        client_id = request.form.get('client_id', '').strip()
        client_secret = request.form.get('client_secret', '').strip()
        redirect_uri = request.form.get('redirect_uri', '').strip()
        
        # Input validation
        if not all([client_id, client_secret, redirect_uri]):
            flash('All OAuth fields are required.', 'error')
            return render_template('anaf/connect.html')
        
        # Validate lengths
        if len(client_id) > 255:
            flash('Client ID is too long.', 'error')
            return render_template('anaf/connect.html')
        
        if len(client_secret) > 255:
            flash('Client secret is too long.', 'error')
            return render_template('anaf/connect.html')
        
        if len(redirect_uri) > 500:
            flash('Redirect URI is too long.', 'error')
            return render_template('anaf/connect.html')
        
        # Validate redirect_uri format
        try:
            parsed = urlparse(redirect_uri)
            if not parsed.scheme or not parsed.netloc:
                flash('Invalid redirect URI format.', 'error')
                return render_template('anaf/connect.html', oauth_config=oauth_config)
            if parsed.scheme not in ('http', 'https'):
                flash('Redirect URI must use http or https.', 'error')
                return render_template('anaf/connect.html', oauth_config=oauth_config)
            
            # Warn if using HTTP in production
            if parsed.scheme == 'http' and current_app.config.get('FLASK_ENV') == 'production':
                flash('Warning: Using HTTP in production is not recommended. Consider using HTTPS.', 'warning')
        except Exception:
            flash('Invalid redirect URI format.', 'error')
            return render_template('anaf/connect.html', oauth_config=oauth_config)
        
        # Encrypt client_secret before storing
        from app.utils.encryption import encrypt_data
        encrypted_secret = encrypt_data(client_secret)
        
        # Save or update OAuth config
        oauth_config = AnafOAuthConfig.query.filter_by(user_id=current_user.id).first()
        
        if oauth_config:
            oauth_config.client_id = client_id
            oauth_config.client_secret = encrypted_secret
            oauth_config.redirect_uri = redirect_uri
        else:
            oauth_config = AnafOAuthConfig(
                user_id=current_user.id,
                client_id=client_id,
                client_secret=encrypted_secret,
                redirect_uri=redirect_uri
            )
            db.session.add(oauth_config)
        
        try:
            db.session.commit()
            
            # Generate state for OAuth flow
            state = secrets.token_urlsafe(32)
            session['oauth_state'] = state
            
            # Get authorization URL
            oauth_service = OAuthService(current_user.id)
            auth_url = oauth_service.get_authorization_url(state=state)
            
            # Log the authorization URL for debugging (without sensitive data)
            current_app.logger.info(
                f"Redirecting user {current_user.id} to ANAF authorization. "
                f"Redirect URI: {redirect_uri}, State: {state[:8]}..."
            )
            
            flash('OAuth configuration saved. Redirecting to ANAF...', 'success')
            return redirect(auth_url)
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving OAuth config: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            return render_template('anaf/connect.html')
    
    # Check if user already has OAuth config
    oauth_config = AnafOAuthConfig.query.filter_by(user_id=current_user.id).first()
    return render_template('anaf/connect.html', oauth_config=oauth_config)

@anaf_bp.route('/callback')
@login_required
@approved_required
def callback():
    """OAuth callback handler"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    # Verify state
    if state != session.get('oauth_state'):
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('anaf.connect'))
    
    if error:
        error_description = request.args.get('error_description', '')
        error_uri = request.args.get('error_uri', '')
        
        # Log detailed error information
        current_app.logger.error(
            f"OAuth authorization error for user {current_user.id}: "
            f"error={error}, description={error_description}, uri={error_uri}"
        )
        
        # Provide more helpful error messages
        if error == 'access_denied':
            error_msg = (
                'Access was denied. This could be due to:\n'
                '1. The user declined authorization\n'
                '2. The redirect URI does not match what is registered with ANAF\n'
                '3. The requested scopes are not authorized for your application\n'
                '4. The client credentials are incorrect\n'
                '5. The user does not have the required permissions in ANAF'
            )
            if error_description:
                error_msg += f'\n\nANAF Error: {error_description}'
        else:
            error_msg = f'OAuth error: {error}'
            if error_description:
                error_msg += f' - {error_description}'
        
        flash(error_msg, 'error')
        return redirect(url_for('anaf.connect'))
    
    if not code:
        flash('No authorization code received.', 'error')
        return redirect(url_for('anaf.connect'))
    
    try:
        # Exchange code for token
        oauth_service = OAuthService(current_user.id)
        token_data = oauth_service.exchange_code_for_token(code)
        
        flash('ANAF account connected successfully!', 'success')
        
        # Clear OAuth state
        session.pop('oauth_state', None)
        
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
        flash(f'Error connecting ANAF account: {str(e)}', 'error')
        return redirect(url_for('anaf.connect'))

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

