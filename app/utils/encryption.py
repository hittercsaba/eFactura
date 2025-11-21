"""Encryption utilities for sensitive data"""
from cryptography.fernet import Fernet
from flask import current_app
import base64
import hashlib

def get_encryption_key():
    """Get or generate encryption key from Flask secret key"""
    secret_key = current_app.config.get('SECRET_KEY', '')
    if not secret_key:
        raise ValueError("SECRET_KEY not configured")
    
    # Derive a 32-byte key from the secret key
    key = hashlib.sha256(secret_key.encode()).digest()
    return base64.urlsafe_b64encode(key)

def encrypt_data(data):
    """Encrypt sensitive data"""
    if not data:
        return None
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return encrypted.decode()

def decrypt_data(encrypted_data):
    """Decrypt sensitive data"""
    if not encrypted_data:
        return None
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception:
        # If decryption fails, return None (might be unencrypted legacy data)
        return None

