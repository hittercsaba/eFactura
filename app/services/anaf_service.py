import requests
import ssl
import json
from datetime import datetime, timedelta, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from flask import current_app
from app.services.oauth_service import OAuthService

class TLSAdapter(HTTPAdapter):
    """Custom TLS adapter for ANAF api.anaf.ro compatibility"""
    
    def init_poolmanager(self, *args, **kwargs):
        # Create SSL context with standard settings for api.anaf.ro (OAuth2 endpoint)
        context = create_urllib3_context()
        
        # SECLEVEL=1 for compatibility with government servers
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        
        # TLS 1.2+ is standard and secure
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)


class ANAFService:
    """Service for interacting with ANAF API"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.oauth_service = OAuthService(user_id)
        # Use api.anaf.ro for OAuth2 authentication (Bearer token)
        # webserviceapl.anaf.ro is for direct certificate authentication (mTLS)
        # Documentation: https://mfinante.gov.ro/static/10/eFactura/prezentare%20api%20efactura.pdf
        self.base_url = current_app.config.get('ANAF_API_BASE_URL', 'https://api.anaf.ro')
        
        # Create session with custom TLS adapter for ANAF compatibility
        self.session = requests.Session()
        self.session.mount('https://', TLSAdapter())
    
    def _get_headers(self):
        """Get headers with authorization token"""
        import sys
        print(f"[ANAF_SERVICE] _get_headers called for user_id={self.user_id}", file=sys.stderr)
        sys.stderr.flush()
        
        access_token = self.oauth_service.get_valid_token()
        
        # Log token info for debugging
        print(f"[ANAF_SERVICE] Got access token (length: {len(access_token) if access_token else 0}) for user_id={self.user_id}", file=sys.stderr)
        sys.stderr.flush()
        
        current_app.logger.info(f"Using access token for API request (user_id={self.user_id}, length: {len(access_token) if access_token else 0})")
        if access_token:
            current_app.logger.info(f"Token preview: {access_token[:20]}...{access_token[-20:]}")
        else:
            current_app.logger.error("No access token available!")
        
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def lista_mesaje_factura(self, cif, zile=60):
        """
        List e-Factura message notifications for a specific CIF
        
        This method uses the paginated endpoint (listaMesajePaginatieFactura) to ensure
        all messages are retrieved, even when there are more than 500 invoices.
        
        Per ANAF documentation:
        - Endpoint: GET https://api.anaf.ro/prod/FCTEL/rest/listaMesajePaginatieFactura
        - Parameters: startTime, endTime (unix timestamp milliseconds), cif, pagina
        - Response: {"mesaje": [...], "serial": "", "cui": "", "titlu": ""}
        
        Args:
            cif: Company CIF/CUI (string, digits only)
            zile: Number of days to look back (integer, 1-90, default 60)
        
        Returns:
            Dictionary with structure: {"mesaje": [...], "serial": "", "cui": "", "titlu": ""}
        """
        # Validate zile parameter (1-90 per ANAF limits for paginated endpoint)
        if not isinstance(zile, int) or zile < 1 or zile > 90:
            raise ValueError(f"zile must be an integer between 1 and 90, got {zile}")
        
        # Validate cif parameter (should be string with digits only)
        if not isinstance(cif, str) or not cif.isdigit():
            raise ValueError(f"cif must be a string containing only digits, got {cif}")
        
        # Log request details with user_id for verification
        import sys
        print(f"[ANAF_API] REQUEST: lista_mesaje_factura - user_id={self.user_id}, cif={cif}, zile={zile}", file=sys.stderr)
        sys.stderr.flush()
        
        current_app.logger.info(f"=== ANAF API REQUEST: Lista Mesaje Factura (using paginated endpoint) ===")
        current_app.logger.info(f"User ID: {self.user_id}")
        current_app.logger.info(f"CIF: {cif}")
        current_app.logger.info(f"Zile: {zile}")
        
        # Use the paginated endpoint directly to handle all cases (including > 500 invoices)
        return self.lista_mesaje_factura_paginated(cif, zile)
    
    def lista_mesaje_factura_paginated(self, cif, zile=60, filter_type=None):
        """
        List e-Factura message notifications for a specific CIF with pagination support.
        Automatically fetches all pages and combines results.
        
        Per ANAF documentation:
        - Endpoint: GET https://api.anaf.ro/prod/FCTEL/rest/listaMesajePaginatieFactura
        - Parameters: startTime, endTime (unix timestamp milliseconds), cif, pagina
        - Optional filter: E (ERORI FACTURA), T (FACTURA TRIMISA), P (FACTURA PRIMITA), R (MESAJ CUMPARATOR)
        
        Args:
            cif: Company CIF/CUI (string, digits only)
            zile: Number of days to look back (integer, 1-90, default 60)
            filter_type: Optional filter for message type (E, T, P, R)
        
        Returns:
            Dictionary with structure: {"mesaje": [...], "serial": "", "cui": "", "titlu": ""}
            with all messages from all pages combined
        """
        # Validate parameters
        if not isinstance(zile, int) or zile < 1 or zile > 90:
            raise ValueError(f"zile must be an integer between 1 and 90, got {zile}")
        
        if not isinstance(cif, str) or not cif.isdigit():
            raise ValueError(f"cif must be a string containing only digits, got {cif}")
        
        if filter_type and filter_type not in ['E', 'T', 'P', 'R']:
            raise ValueError(f"filter_type must be one of: E, T, P, R, got {filter_type}")
        
        # Calculate timestamps in milliseconds (unix timestamp)
        # endTime = now, startTime = now - zile days
        now = datetime.now(timezone.utc)
        end_time_ms = int(now.timestamp() * 1000)
        start_time_ms = int((now - timedelta(days=zile)).timestamp() * 1000)
        
        url = f"{self.base_url}/prod/FCTEL/rest/listaMesajePaginatieFactura"
        headers = self._get_headers()
        
        all_mesaje = []
        combined_serial = ''
        combined_cui = ''
        combined_titlu = ''
        pagina = 1  # Start from page 1
        pages_fetched = 0  # Track number of pages successfully fetched
        
        current_app.logger.info(f"=== ANAF API REQUEST: Lista Mesaje Factura (Paginated) ===")
        current_app.logger.info(f"CIF: {cif}, Zile: {zile}, StartTime: {start_time_ms}, EndTime: {end_time_ms}")
        if filter_type:
            current_app.logger.info(f"Filter: {filter_type}")
        
        try:
            while True:
                # Prepare paginated request parameters
                params = {
                    'startTime': start_time_ms,
                    'endTime': end_time_ms,
                    'cif': cif,
                    'pagina': pagina
                }
                
                # Add optional filter parameter
                if filter_type:
                    params['filter'] = filter_type
                
                current_app.logger.info(f"Fetching page {pagina}...")
                
                # Log full request URL for debugging
                param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
                full_url = f"{url}?{param_str}"
                current_app.logger.info(f"Paginated request URL: {full_url}")
                
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=30
                )
                
                current_app.logger.info(f"Paginated response status: {response.status_code}")
                
                response.raise_for_status()
                response_data = response.json()
                
                # Log response structure for debugging
                if isinstance(response_data, dict):
                    current_app.logger.info(f"Paginated response keys: {list(response_data.keys())}")
                
                # Handle response wrapping
                if isinstance(response_data, dict):
                    if 'data' in response_data and isinstance(response_data['data'], dict):
                        response_data = response_data['data']
                    elif 'result' in response_data and isinstance(response_data['result'], dict):
                        response_data = response_data['result']
                    elif 'response' in response_data and isinstance(response_data['response'], dict):
                        response_data = response_data['response']
                
                # Check for errors
                if 'eroare' in response_data:
                    error_msg = response_data['eroare']
                    # Check if error indicates we've exceeded the total number of pages
                    # Error message: "Pagina solicitata X este mai mare decat numarul toatal de pagini Y"
                    if 'mai mare decat numarul toatal de pagini' in error_msg.lower() or 'mai mare decat numarul total de pagini' in error_msg.lower():
                        # This is a normal end-of-pagination condition, not a real error
                        current_app.logger.info(f"Reached end of pagination: {error_msg}")
                        break
                    else:
                        # This is a real error, raise it
                        current_app.logger.error(f"ANAF API error on page {pagina}: {error_msg}")
                        raise ValueError(f"ANAF API error: {error_msg}")
                
                # Extract messages from current page
                page_mesaje = response_data.get('mesaje', [])
                
                # Increment pages_fetched since we successfully fetched this page
                pages_fetched += 1
                
                if not page_mesaje:
                    # No more messages, stop pagination
                    current_app.logger.info(f"No more messages on page {pagina}, stopping pagination")
                    break
                
                # Combine messages
                all_mesaje.extend(page_mesaje)
                
                # Store metadata from first page (they should be consistent)
                if pagina == 1:
                    combined_serial = response_data.get('serial', '')
                    combined_cui = response_data.get('cui', cif)
                    combined_titlu = response_data.get('titlu', '')
                
                current_app.logger.info(f"Page {pagina}: Found {len(page_mesaje)} messages (total so far: {len(all_mesaje)})")
                
                # Move to next page
                pagina += 1
                
                # Safety limit to prevent infinite loops
                if pagina > 1000:  # Max pages
                    current_app.logger.warning(f"Reached maximum page limit (1000), stopping pagination")
                    break
            
            current_app.logger.info(f"Pagination complete: Total messages fetched: {len(all_mesaje)} from {pages_fetched} page(s)")
            current_app.logger.info("=" * 60)
            
            # Return combined result in same format as non-paginated version
            return {
                'mesaje': all_mesaje,
                'serial': combined_serial,
                'cui': combined_cui or cif,
                'titlu': combined_titlu
            }
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error listing invoices with pagination for CIF {cif}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                current_app.logger.error(f"Error Response Status: {e.response.status_code}")
                current_app.logger.error(f"Error Response Body: {e.response.text[:500]}")
            raise
    
    def descarcare_factura(self, message_id):
        """
        Download e-Factura file (ZIP or XML) by ANAF message ID
        
        Per ANAF documentation:
        - Endpoint: GET https://api.anaf.ro/prod/FCTEL/rest/descarcare
        - Parameter: id (required, string/integer) - ANAF message identifier
        - Response: Binary content (ZIP or XML)
        
        Args:
            message_id: ANAF message identifier (from listaMesajeFactura response)
        
        Returns:
            Binary content (bytes) - typically ZIP archive containing invoice XML
        """
        if not message_id:
            raise ValueError("message_id is required")
        
        url = f"{self.base_url}/prod/FCTEL/rest/descarcare"
        params = {
            'id': str(message_id)  # Ensure it's a string
        }
        
        # Get headers but override Accept for binary content
        headers = self._get_headers()
        headers['Accept'] = 'application/octet-stream'
        
        current_app.logger.info(f"=== ANAF API REQUEST: Descarcare Factura ===")
        current_app.logger.info(f"URL: {url}")
        current_app.logger.info(f"Message ID: {message_id}")
        current_app.logger.info(f"Full URL: {url}?id={message_id}")
        
        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=60  # Longer timeout for file downloads
            )
            
            current_app.logger.info(f"Response Status: {response.status_code}")
            current_app.logger.info(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            current_app.logger.info(f"Content-Length: {response.headers.get('Content-Length', 'N/A')} bytes")
            
            response.raise_for_status()
            
            # Return binary content (not text)
            return response.content
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error downloading invoice {message_id}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                current_app.logger.error(f"Error Response Status: {e.response.status_code}")
                # Try to parse error message if JSON
                try:
                    error_data = e.response.json()
                    current_app.logger.error(f"Error Response Body: {error_data}")
                except:
                    current_app.logger.error(f"Error Response Text: {e.response.text[:500]}")
            raise
    
    def get_user_companies(self):
        """
        Discover companies (CUIs) accessible by the user's token
        
        Note: This endpoint may vary based on ANAF API documentation.
        If no direct endpoint exists, we may need to query per known CIF
        or use a different discovery method.
        
        Returns:
            List of company information (CIF, name, etc.)
        """
        # This is a placeholder - actual endpoint needs to be determined
        # from ANAF documentation. Common patterns:
        # - /api/user/companies
        # - /api/companies
        # - Query listaMesajeFactura with different CUIs to discover access
        
        # For now, return empty list - will be implemented based on actual API
        # The company discovery will happen during OAuth callback or manual entry
        # Note: Company discovery endpoint doesn't exist in ANAF API - companies must be added manually
        url = f"{self.base_url}/api/user/companies"
        
        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            current_app.logger.warning(f"Company discovery endpoint not available: {str(e)}")
            # Return empty list if endpoint doesn't exist
            return []

