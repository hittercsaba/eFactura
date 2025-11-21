#!/usr/bin/env python
"""Flask CLI management script"""
import os
from flask_migrate import Migrate
from app import create_app, db
from app.models import User, AnafOAuthConfig, AnafToken, Company, ApiKey, Invoice

app = create_app(os.getenv('FLASK_ENV', 'default'))
migrate = Migrate(app, db)

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'AnafOAuthConfig': AnafOAuthConfig,
        'AnafToken': AnafToken,
        'Company': Company,
        'ApiKey': ApiKey,
        'Invoice': Invoice
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)

