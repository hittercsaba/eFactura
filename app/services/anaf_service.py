import requests
from flask import current_app
from app.services.oauth_service import OAuthService

class ANAFService:
    """Service for interacting with ANAF API"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.oauth_service = OAuthService(user_id)
        self.base_url = current_app.config.get('ANAF_API_BASE_URL', 'https://api.anaf.ro')
    
    def _get_headers(self):
        """Get headers with authorization token"""
        access_token = self.oauth_service.get_valid_token()
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
        
        try:
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error listing invoices for CIF {cif}: {str(e)}")
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
            response = requests.get(
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
        url = f"{self.base_url}/api/user/companies"
        
        try:
            response = requests.get(
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

