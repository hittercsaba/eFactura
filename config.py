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
    # Use SPV webservices endpoint for e-Factura API
    ANAF_API_BASE_URL = os.environ.get('ANAF_API_BASE_URL') or 'https://webservicesp.anaf.ro'
    
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

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

