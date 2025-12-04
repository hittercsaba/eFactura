import requests
import ssl
import json
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
        access_token = self.oauth_service.get_valid_token()
        
        # Log token info for debugging
        current_app.logger.info(f"Using access token for API request (length: {len(access_token) if access_token else 0})")
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
        
        Per ANAF documentation:
        - Endpoint: GET https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura
        - Response: {"mesaje": [...], "serial": "", "cui": "", "titlu": ""}
        
        Args:
            cif: Company CIF/CUI (string, digits only)
            zile: Number of days to look back (integer, 1-90, default 60)
        
        Returns:
            Dictionary with structure: {"mesaje": [...], "serial": "", "cui": "", "titlu": ""}
        """
        # Validate zile parameter (1-60 per ANAF limits)
        # API error: "Numarul de zile trebuie sa fie intre 1 si 60"
        if not isinstance(zile, int) or zile < 1 or zile > 60:
            raise ValueError(f"zile must be an integer between 1 and 60, got {zile}")
        
        # Validate cif parameter (should be string with digits only)
        if not isinstance(cif, str) or not cif.isdigit():
            raise ValueError(f"cif must be a string containing only digits, got {cif}")
        
        url = f"{self.base_url}/prod/FCTEL/rest/listaMesajeFactura"
        params = {
            'zile': zile,
            'cif': cif
        }
        
        # Get headers (includes token)
        headers = self._get_headers()
        
        # Log request details
        current_app.logger.info(f"=== ANAF API REQUEST: Lista Mesaje Factura ===")
        current_app.logger.info(f"URL: {url}")
        current_app.logger.info(f"CIF: {cif}")
        current_app.logger.info(f"Zile: {zile}")
        current_app.logger.info(f"Full URL: {url}?zile={zile}&cif={cif}")
        current_app.logger.info(f"Authorization Header: Bearer {headers['Authorization'][7:27]}...{headers['Authorization'][-20:]}")
        
        try:
            response = self.session.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=30
            )
            
            # Log response details
            current_app.logger.info(f"Response Status: {response.status_code}")
            current_app.logger.info(f"Response Headers: {dict(response.headers)}")
            
            response.raise_for_status()
            
            # Parse and validate response structure
            response_data = response.json()
            
            # Handle potential response wrapping (e.g., {"data": {...}} or {"result": {...}})
            # Check if response is wrapped in a common wrapper structure
            if isinstance(response_data, dict):
                # Check for common wrapper keys
                if 'data' in response_data and isinstance(response_data['data'], dict):
                    current_app.logger.info("Response wrapped in 'data' key - unwrapping")
                    response_data = response_data['data']
                elif 'result' in response_data and isinstance(response_data['result'], dict):
                    current_app.logger.info("Response wrapped in 'result' key - unwrapping")
                    response_data = response_data['result']
                elif 'response' in response_data and isinstance(response_data['response'], dict):
                    current_app.logger.info("Response wrapped in 'response' key - unwrapping")
                    response_data = response_data['response']
            
            # Validate response structure per ANAF documentation
            if not isinstance(response_data, dict):
                current_app.logger.error(f"Unexpected response type: {type(response_data)}")
                current_app.logger.error(f"Response content: {response.text[:500]}")
                raise ValueError("Response is not a dictionary")
            
            # Check for error response first (even if all expected keys are present)
            eroare_msg = response_data.get('eroare', '')
            is_pagination_error = False
            if eroare_msg:
                if 'paginatie' in eroare_msg.lower():
                    is_pagination_error = True
                    current_app.logger.info(f"Detected pagination requirement: {eroare_msg}")
                    # Automatically switch to paginated endpoint
                    current_app.logger.info(f"Switching to paginated endpoint to fetch all messages for CIF {cif}")
                    return self.lista_mesaje_factura_paginated(cif, zile)
            
            # Expected keys: mesaje, serial, cui, titlu
            expected_keys = ['mesaje', 'serial', 'cui', 'titlu']
            missing_keys = [key for key in expected_keys if key not in response_data]
            
            # Check if this might be an error response
            error_indicator_keys = ['error', 'message', 'error_description', 'erori', 'mesaj', 'eroare']
            has_error_indicators = any(key in response_data for key in error_indicator_keys)
            
            if missing_keys:
                # Log full response structure for debugging
                current_app.logger.warning(f"Response missing expected keys: {missing_keys}")
                current_app.logger.warning(f"Response structure: {list(response_data.keys())}")
                
                # Log full response body for debugging (truncated for safety)
                response_str = json.dumps(response_data, indent=2, ensure_ascii=False)
                current_app.logger.warning(f"Full response body (first 1000 chars): {response_str[:1000]}")
                
                # Check if it's an error response (pagination error already handled above)
                if has_error_indicators and not is_pagination_error:
                    error_msg = response_data.get('error') or response_data.get('message') or response_data.get('error_description') or response_data.get('mesaj') or response_data.get('erori') or eroare_msg
                    current_app.logger.error(f"ANAF API returned error response: {error_msg}")
                    raise ValueError(f"ANAF API error: {error_msg or 'Unknown error'}")
                
                # If response is empty or has no mesaje, provide default structure
                # This allows the sync to continue gracefully with empty results
                if 'mesaje' not in response_data:
                    current_app.logger.warning(f"Response missing 'mesaje' key - treating as empty message list")
                    response_data['mesaje'] = []
                
                # Provide defaults for other missing keys
                if 'serial' not in response_data:
                    response_data['serial'] = ''
                if 'cui' not in response_data:
                    response_data['cui'] = cif  # Use provided CIF as fallback
                if 'titlu' not in response_data:
                    response_data['titlu'] = ''
            
            # Log response details
            mesaje_count = len(response_data.get('mesaje', []))
            current_app.logger.info(f"Response Structure: {list(response_data.keys())}")
            current_app.logger.info(f"Messages Count: {mesaje_count}")
            current_app.logger.info(f"Serial: {response_data.get('serial', 'N/A')}")
            current_app.logger.info(f"CUI: {response_data.get('cui', 'N/A')}")
            current_app.logger.info(f"Title: {response_data.get('titlu', 'N/A')[:100] if response_data.get('titlu') else 'N/A'}")
            current_app.logger.info("=" * 60)
            
            return response_data
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error listing invoices for CIF {cif}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                current_app.logger.error(f"Error Response Status: {e.response.status_code}")
                current_app.logger.error(f"Error Response Body: {e.response.text[:500]}")
            raise
    
    def lista_mesaje_factura_paginated(self, cif, zile=60, pagina_size=500):
        """
        List e-Factura message notifications for a specific CIF with pagination support.
        Automatically fetches all pages and combines results.
        
        Per ANAF documentation, when there are more than 500 messages, pagination is required.
        This method fetches all pages automatically.
        
        Args:
            cif: Company CIF/CUI (string, digits only)
            zile: Number of days to look back (integer, 1-90, default 60)
            pagina_size: Number of items per page (default 500, max per ANAF)
        
        Returns:
            Dictionary with structure: {"mesaje": [...], "serial": "", "cui": "", "titlu": ""}
            with all messages from all pages combined
        """
        # Validate parameters
        if not isinstance(zile, int) or zile < 1 or zile > 90:
            raise ValueError(f"zile must be an integer between 1 and 90, got {zile}")
        
        if not isinstance(cif, str) or not cif.isdigit():
            raise ValueError(f"cif must be a string containing only digits, got {cif}")
        
        url = f"{self.base_url}/prod/FCTEL/rest/listaMesajeFactura"
        headers = self._get_headers()
        
        all_mesaje = []
        combined_serial = ''
        combined_cui = ''
        combined_titlu = ''
        pagina = 1  # Start from page 1
        
        current_app.logger.info(f"=== ANAF API REQUEST: Lista Mesaje Factura (Paginated) ===")
        current_app.logger.info(f"CIF: {cif}, Zile: {zile}, Page Size: {pagina_size}")
        
        try:
            while True:
                # Prepare paginated request parameters
                params = {
                    'zile': zile,
                    'cif': cif,
                    'pagina': pagina,
                    'dimensiune_pagina': pagina_size
                }
                
                current_app.logger.info(f"Fetching page {pagina} with {pagina_size} items per page...")
                
                # Log full request URL for debugging
                full_url = f"{url}?zile={zile}&cif={cif}&pagina={pagina}&dimensiune_pagina={pagina_size}"
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
                    # If it's not about pagination, raise it
                    if 'paginatie' not in error_msg.lower():
                        current_app.logger.error(f"ANAF API error on page {pagina}: {error_msg}")
                        raise ValueError(f"ANAF API error: {error_msg}")
                
                # Extract messages from current page
                page_mesaje = response_data.get('mesaje', [])
                
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
                
                # Check if we've reached the last page
                # If the page has fewer items than the page size, it's likely the last page
                if len(page_mesaje) < pagina_size:
                    current_app.logger.info(f"Last page reached (page {pagina} has fewer items than page size)")
                    break
                
                # Move to next page
                pagina += 1
                
                # Safety limit to prevent infinite loops
                if pagina > 1000:  # Max 500,000 messages
                    current_app.logger.warning(f"Reached maximum page limit (1000), stopping pagination")
                    break
            
            current_app.logger.info(f"Pagination complete: Total messages fetched: {len(all_mesaje)} from {pagina} page(s)")
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

