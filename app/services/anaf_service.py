import requests
import ssl
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
        List invoices for a specific CIF
        
        Args:
            cif: Company CIF (Tax ID)
            zile: Number of days to look back (default 60)
        
        Returns:
            List of invoice messages
        """
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
            
            # Parse and log response
            response_data = response.json()
            current_app.logger.info(f"Response Data Type: {type(response_data)}")
            current_app.logger.info(f"Response Keys: {response_data.keys() if isinstance(response_data, dict) else 'N/A (list)'}")
            current_app.logger.info(f"Response Data (first 500 chars): {str(response_data)[:500]}")
            current_app.logger.info("=" * 60)
            
            return response_data
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error listing invoices for CIF {cif}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                current_app.logger.error(f"Error Response Status: {e.response.status_code}")
                current_app.logger.error(f"Error Response Body: {e.response.text[:500]}")
            raise
    
    def descarcare_factura(self, invoice_id):
        """
        Download invoice XML by ID
        
        Args:
            invoice_id: ANAF invoice ID
        
        Returns:
            XML content as string
        """
        url = f"{self.base_url}/prod/FCTEL/rest/descarcare"
        params = {
            'id': invoice_id
        }
        
        try:
            response = self.session.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error downloading invoice {invoice_id}: {str(e)}")
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

