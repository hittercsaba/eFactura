import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from flask import current_app, url_for
from app.models import db, AnafOAuthConfig, AnafToken, User
from app.utils.encryption import encrypt_data, decrypt_data

class OAuthService:
    """Service for handling ANAF OAuth flow"""
    
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.oauth_config = None
        if user_id:
            self.oauth_config = AnafOAuthConfig.query.filter_by(user_id=user_id).first()
            # Decrypt client_secret if encrypted
            if self.oauth_config and self.oauth_config.client_secret:
                decrypted = decrypt_data(self.oauth_config.client_secret)
                if decrypted:
                    self.oauth_config.client_secret = decrypted
    
    def get_authorization_url(self, state=None):
        """Generate ANAF OAuth authorization URL"""
        if not self.oauth_config:
            raise ValueError("OAuth configuration not found for user")
        
        auth_url = "https://logincert.anaf.ro/anaf-oauth2/v1/authorize"
        
        # ANAF OAuth2 parameters
        # Note: ANAF may require specific scopes - adjust based on their documentation
        params = {
            'client_id': self.oauth_config.client_id,
            'redirect_uri': self.oauth_config.redirect_uri,
            'response_type': 'code',
            'scope': 'openid profile email',  # May need to be adjusted per ANAF requirements
            'state': state or 'default'
        }
        
        auth_url_full = f"{auth_url}?{urlencode(params)}"
        current_app.logger.info(f"Generated ANAF authorization URL for user {self.user_id}")
        current_app.logger.debug(f"Authorization URL: {auth_url_full}")
        
        return auth_url_full
    
    def exchange_code_for_token(self, code):
        """Exchange authorization code for access token"""
        if not self.oauth_config:
            raise ValueError("OAuth configuration not found for user")
        
        token_url = "https://logincert.anaf.ro/anaf-oauth2/v1/token"
        
        # Per ANAF documentation: Use Basic Authentication with client credentials
        # and form-encoded data for grant type and code
        from requests.auth import HTTPBasicAuth
        
        # Basic Auth with client_id and client_secret
        auth = HTTPBasicAuth(self.oauth_config.client_id, self.oauth_config.client_secret)
        
        # Form data with grant_type, code, and redirect_uri
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.oauth_config.redirect_uri
        }
        
        # Headers for form-encoded request
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        current_app.logger.info(f"Exchanging authorization code for token for user {self.user_id}")
        current_app.logger.debug(f"Token URL: {token_url}")
        current_app.logger.debug(f"Redirect URI: {self.oauth_config.redirect_uri}")
        current_app.logger.debug(f"Client ID: {self.oauth_config.client_id}")
        current_app.logger.debug(f"Using Basic Auth: Yes")
        
        try:
            response = requests.post(token_url, data=data, headers=headers, auth=auth, timeout=30)
            
            # Log response details for debugging
            current_app.logger.debug(f"Token exchange response status: {response.status_code}")
            current_app.logger.debug(f"Token exchange response headers: {dict(response.headers)}")
            
            # Check if response is JSON
            try:
                response_data = response.json()
                current_app.logger.debug(f"Token exchange response data: {response_data}")
            except ValueError:
                current_app.logger.error(f"Token exchange response is not JSON: {response.text[:500]}")
                raise ValueError(f"Invalid response from token endpoint: {response.text[:500]}")
            
            # Check for OAuth errors in response
            if 'error' in response_data:
                error_description = response_data.get('error_description', 'No description provided')
                error_code = response_data.get('error', 'unknown_error')
                current_app.logger.error(f"OAuth error from token endpoint: {error_code} - {error_description}")
                raise ValueError(f"OAuth error: {error_code} - {error_description}")
            
            if response.status_code != 200:
                current_app.logger.error(f"Token exchange failed with status {response.status_code}: {response_data}")
                response.raise_for_status()
            
            # Calculate token expiry (assuming expires_in is in seconds)
            expires_in = response_data.get('expires_in', 3600)
            token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Save or update token
            anaf_token = AnafToken.query.filter_by(user_id=self.user_id).first()
            
            if anaf_token:
                anaf_token.access_token = response_data.get('access_token')
                anaf_token.refresh_token = response_data.get('refresh_token')
                anaf_token.token_expiry = token_expiry
                anaf_token.updated_at = datetime.now(timezone.utc)
            else:
                anaf_token = AnafToken(
                    user_id=self.user_id,
                    access_token=response_data.get('access_token'),
                    refresh_token=response_data.get('refresh_token'),
                    token_expiry=token_expiry
                )
                db.session.add(anaf_token)
            
            db.session.commit()
            current_app.logger.info(f"Successfully exchanged code for token for user {self.user_id}")
            return response_data
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Token exchange request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    current_app.logger.error(f"Error response: {error_data}")
                except:
                    current_app.logger.error(f"Error response text: {e.response.text[:500]}")
            raise
    
    def refresh_access_token(self):
        """Refresh access token using refresh token"""
        if not self.oauth_config:
            raise ValueError("OAuth configuration not found for user")
        
        anaf_token = AnafToken.query.filter_by(user_id=self.user_id).first()
        if not anaf_token or not anaf_token.refresh_token:
            raise ValueError("No refresh token available")
        
        token_url = "https://logincert.anaf.ro/anaf-oauth2/v1/token"
        
        # Per ANAF documentation: Use Basic Authentication
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(self.oauth_config.client_id, self.oauth_config.client_secret)
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': anaf_token.refresh_token
        }
        
        try:
            response = requests.post(token_url, data=data, auth=auth, timeout=30)
            response.raise_for_status()
            token_data = response.json()
            
            # Update token
            expires_in = token_data.get('expires_in', 3600)
            token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            anaf_token.access_token = token_data.get('access_token')
            if token_data.get('refresh_token'):
                anaf_token.refresh_token = token_data.get('refresh_token')
            anaf_token.token_expiry = token_expiry
            anaf_token.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            return token_data
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Token refresh failed: {str(e)}")
            raise
    
    def get_valid_token(self):
        """Get valid access token, refreshing if necessary"""
        anaf_token = AnafToken.query.filter_by(user_id=self.user_id).first()
        
        if not anaf_token:
            raise ValueError("No ANAF token found for user")
        
        # Check if token is expired or about to expire (within 5 minutes)
        if anaf_token.is_expired() or \
           (anaf_token.token_expiry and 
            (anaf_token.token_expiry - datetime.now(timezone.utc)).total_seconds() < 300):
            try:
                self.refresh_access_token()
                # Reload token from DB
                db.session.refresh(anaf_token)
            except Exception as e:
                current_app.logger.error(f"Failed to refresh token: {str(e)}")
                raise
        
        return anaf_token.access_token
    
    def revoke_token(self):
        """Revoke access token"""
        if not self.oauth_config:
            raise ValueError("OAuth configuration not found for user")
        
        anaf_token = AnafToken.query.filter_by(user_id=self.user_id).first()
        if not anaf_token:
            raise ValueError("No ANAF token found for user")
        
        revoke_url = "https://logincert.anaf.ro/anaf-oauth2/v1/revoke"
        
        data = {
            'token': anaf_token.access_token,
            'client_id': self.oauth_config.client_id,
            'client_secret': self.oauth_config.client_secret
        }
        
        try:
            response = requests.post(revoke_url, data=data, timeout=30)
            response.raise_for_status()
            
            # Delete token from database after successful revocation
            db.session.delete(anaf_token)
            db.session.commit()
            
            return True
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Token revocation failed: {str(e)}")
            raise

