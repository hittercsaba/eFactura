# Routes package
from flask import redirect, url_for
from flask_login import current_user

def init_routes(app):
    """Initialize routes"""
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))
