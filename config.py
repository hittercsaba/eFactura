import os
from urllib.parse import urlparse

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database configuration
    database_url = os.environ.get('DATABASE_URL') or 'postgresql://efactura_user:efactura_pass@localhost:5432/efactura_db'
    SQLALCHEMY_DATABASE_URI = database_url
    
    # ANAF API configuration
    # Use api.anaf.ro for OAuth2 authentication (Bearer token)
    # webserviceapl.anaf.ro is for direct certificate authentication (mTLS)
    # Documentation: https://mfinante.gov.ro/static/10/eFactura/prezentare%20api%20efactura.pdf
    ANAF_API_BASE_URL = os.environ.get('ANAF_API_BASE_URL') or 'https://api.anaf.ro'
    
    # Session configuration
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'
    
    def __init__(self):
        """Validate required environment variables in production"""
        import os
        if not os.environ.get('SECRET_KEY'):
            raise ValueError(
                "SECRET_KEY must be set as an environment variable in production. "
                "Generate a strong random key: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        if not os.environ.get('DATABASE_URL'):
            raise ValueError(
                "DATABASE_URL must be set as an environment variable in production. "
                "Format: postgresql://user:password@host:port/database"
            )
        
        # Database connection pooling for production
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 10,
            'max_overflow': 20,
            'pool_pre_ping': True,  # Verify connections before using
            'pool_recycle': 3600,   # Recycle connections after 1 hour
        }

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

