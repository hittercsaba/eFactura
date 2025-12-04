"""Helper functions for user impersonation feature"""
from flask import session
from flask_login import current_user
from app.models import User


def is_impersonating():
    """Check if current session is impersonating another user"""
    return '_impersonating_user_id' in session and '_impersonating_from_user_id' in session


def get_original_admin():
    """Get the original admin user object who initiated impersonation"""
    if not is_impersonating():
        return None
    
    admin_id = session.get('_impersonating_from_user_id')
    if admin_id:
        try:
            return User.query.get(int(admin_id))
        except (ValueError, TypeError):
            return None
    return None


def get_impersonated_user():
    """Get the currently impersonated user object"""
    if not is_impersonating():
        return None
    
    user_id = session.get('_impersonating_user_id')
    if user_id:
        try:
            return User.query.get(int(user_id))
        except (ValueError, TypeError):
            return None
    return None

