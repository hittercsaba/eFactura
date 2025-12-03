import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from flask import current_app, url_for
from app.models import db, AnafOAuthConfig, AnafToken, User
from app.utils.encryption import encrypt_data, decrypt_data

class OAuthService:
    """Service for handling ANAF OAuth flow
    
    OAuth config is system-wide (managed by admin).
    Each user gets their own token by authenticating with their certificate.
    """
    
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.oauth_config = None
        
        # Get system-wide OAuth configuration (should be only one record)
        self.oauth_config = AnafOAuthConfig.query.first()
        
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
        # Per ANAF documentation: e-Factura service doesn't use OpenID Connect scopes
        # Token is associated with the user's digital certificate, not profile/email
        # Per Postman configuration: token_content_type=jwt must be sent to get JWT tokens
        params = {
            'client_id': self.oauth_config.client_id,
            'redirect_uri': self.oauth_config.redirect_uri,
            'response_type': 'code',
            'state': state or 'default',
            'token_content_type': 'jwt'  # Required to get JWT tokens instead of short tokens
        }
        # Note: Scope is omitted as ANAF e-Factura doesn't require it
        
        auth_url_full = f"{auth_url}?{urlencode(params)}"
        
        # Log detailed authorization request parameters
        current_app.logger.info(f"=== ANAF AUTHORIZATION REQUEST FOR USER {self.user_id} ===")
        current_app.logger.info(f"Authorization URL: {auth_url}")
        current_app.logger.info(f"Client ID: {self.oauth_config.client_id}")
        current_app.logger.info(f"Redirect URI: {self.oauth_config.redirect_uri}")
        current_app.logger.info(f"Response Type: code")
        current_app.logger.info(f"Token Content Type: jwt (required for JWT tokens)")
        current_app.logger.info(f"Scope: (none - not required by ANAF)")
        current_app.logger.info(f"State: {state}")
        current_app.logger.info(f"Full Authorization URL: {auth_url_full}")
        current_app.logger.info("=" * 60)
        
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
        
        # Form data with grant_type, code, redirect_uri, and token_content_type
        # Per Postman configuration: token_content_type=jwt must be sent in request body
        # to get JWT tokens instead of short 64-character tokens
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.oauth_config.redirect_uri,
            'token_content_type': 'jwt'  # Required to get JWT tokens
        }
        
        # Headers for form-encoded request
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        # Log detailed token exchange request
        current_app.logger.info(f"=== ANAF TOKEN EXCHANGE REQUEST FOR USER {self.user_id} ===")
        current_app.logger.info(f"Token URL: {token_url}")
        current_app.logger.info(f"Grant Type: authorization_code")
        current_app.logger.info(f"Authorization Code: {code[:20]}...{code[-20:] if len(code) > 40 else ''}")
        current_app.logger.info(f"Redirect URI: {self.oauth_config.redirect_uri}")
        current_app.logger.info(f"Token Content Type: jwt (required for JWT tokens)")
        current_app.logger.info(f"Client ID: {self.oauth_config.client_id}")
        current_app.logger.info(f"Client Secret: {'*' * 20} (length: {len(self.oauth_config.client_secret)})")
        current_app.logger.info(f"Authentication Method: HTTP Basic Auth")
        current_app.logger.info(f"Content-Type: {headers['Content-Type']}")
        current_app.logger.info(f"Request Data: grant_type=authorization_code&code=...&redirect_uri=...&token_content_type=jwt")
        current_app.logger.info("=" * 60)
        
        try:
            response = requests.post(token_url, data=data, headers=headers, auth=auth, timeout=30)
            
            # Log response details for debugging
            current_app.logger.debug(f"Token exchange response status: {response.status_code}")
            current_app.logger.debug(f"Token exchange response headers: {dict(response.headers)}")
            
            # Check if response is JSON
            try:
                # Log raw response text FIRST (before JSON parsing) to see full content
                current_app.logger.info(f"=== RAW RESPONSE FROM ANAF TOKEN ENDPOINT ===")
                current_app.logger.info(f"Response status: {response.status_code}")
                current_app.logger.info(f"Content-Length header: {response.headers.get('Content-Length', 'N/A')}")
                current_app.logger.info(f"Raw response text length: {len(response.text)}")
                # SECURITY: Do not log full response text if it contains tokens
                # Only log length and structure for debugging
                current_app.logger.info(f"Raw response text length: {len(response.text)} chars (content not logged for security)")
                current_app.logger.info("=" * 60)
                
                # Parse JSON response
                response_data = response.json()
                
                # Log parsed response structure
                current_app.logger.info(f"=== PARSED RESPONSE DATA ===")
                current_app.logger.info(f"Response keys: {list(response_data.keys())}")
                
                # Check access_token in detail
                if 'access_token' in response_data:
                    access_token_value = response_data['access_token']
                    current_app.logger.info(f"Access token - Type: {type(access_token_value)}")
                    current_app.logger.info(f"Access token - Length: {len(str(access_token_value))}")
                    # SECURITY: Do not log full token value - only log length and structure
                    # Logging full tokens would be a security risk
                    current_app.logger.info(f"Access token - Full value length: {len(str(access_token_value))} chars (value not logged for security)")
                    
                    # Check if it's a JWT (should have 3 parts separated by dots)
                    if isinstance(access_token_value, str):
                        parts = access_token_value.split('.')
                        current_app.logger.info(f"Token parts count: {len(parts)} (JWT should have exactly 3 parts)")
                        if len(parts) == 3:
                            current_app.logger.info(f"✅ JWT structure detected!")
                            current_app.logger.info(f"   Header length: {len(parts[0])} chars")
                            current_app.logger.info(f"   Payload length: {len(parts[1])} chars")
                            current_app.logger.info(f"   Signature length: {len(parts[2])} chars")
                            current_app.logger.info(f"   Total JWT length: {len(access_token_value)} chars")
                        else:
                            current_app.logger.error(f"❌ Token does NOT appear to be a JWT!")
                            current_app.logger.error(f"   Expected 3 parts (header.payload.signature)")
                            current_app.logger.error(f"   Got {len(parts)} parts")
                            current_app.logger.error(f"   This might indicate:")
                            current_app.logger.error(f"     1. ANAF returned a non-JWT token")
                            current_app.logger.error(f"     2. Response was truncated")
                            current_app.logger.error(f"     3. JSON parsing issue")
                
                if 'refresh_token' in response_data:
                    refresh_token_value = response_data['refresh_token']
                    current_app.logger.info(f"Refresh token - Type: {type(refresh_token_value)}, Length: {len(str(refresh_token_value))}")
                
                current_app.logger.info(f"Full response_data: {response_data}")
                current_app.logger.info("=" * 60)
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
            
            # Get tokens from response
            access_token = response_data.get('access_token')
            refresh_token = response_data.get('refresh_token')
            
            # Log token lengths for debugging
            current_app.logger.info(f"Token lengths - Access: {len(access_token) if access_token else 0}, Refresh: {len(refresh_token) if refresh_token else 0}")
            
            # Validate token length (JWT tokens should be much longer than 64 chars)
            if access_token and len(access_token) < 100:
                current_app.logger.warning(f"WARNING: Access token seems too short ({len(access_token)} chars). Expected 1500+ for JWT tokens.")
            
            # Save or update token
            anaf_token = AnafToken.query.filter_by(user_id=self.user_id).first()
            
            if anaf_token:
                anaf_token.access_token = access_token
                anaf_token.refresh_token = refresh_token
                anaf_token.token_expiry = token_expiry
                anaf_token.updated_at = datetime.now(timezone.utc)
            else:
                anaf_token = AnafToken(
                    user_id=self.user_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expiry=token_expiry
                )
                db.session.add(anaf_token)
            
            db.session.commit()
            
            # Verify token was stored correctly
            db.session.refresh(anaf_token)
            stored_length = len(anaf_token.access_token) if anaf_token.access_token else 0
            current_app.logger.info(f"Successfully exchanged code for token for user {self.user_id}. Stored token length: {stored_length}")
            
            if stored_length != len(access_token):
                current_app.logger.error(f"ERROR: Token length mismatch! Received: {len(access_token)}, Stored: {stored_length}")
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
        
        # Headers for form-encoded request
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        try:
            # Use session with TLSAdapter for consistent SSL/TLS handling
            response = self.session.post(token_url, data=data, headers=headers, auth=auth, timeout=30)
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
        token_expiry = anaf_token.token_expiry
        if token_expiry and token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=timezone.utc)
        
        if anaf_token.is_expired() or \
           (token_expiry and (token_expiry - datetime.now(timezone.utc)).total_seconds() < 300):
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

