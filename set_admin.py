#!/usr/bin/env python3
"""Script to set a user as admin"""
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User

def set_user_as_admin(email):
    """Set a user as admin and approved"""
    app = create_app(os.getenv('FLASK_ENV', 'default'))
    
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.is_admin = True
            user.is_approved = True
            db.session.commit()
            print(f'✓ User {user.email} has been set as admin and approved.')
            print(f'  - Admin: {user.is_admin}')
            print(f'  - Approved: {user.is_approved}')
            return True
        else:
            print(f'✗ User not found with email: {email}')
            print('  Available users:')
            users = User.query.all()
            if users:
                for u in users:
                    print(f'    - {u.email} (admin: {u.is_admin}, approved: {u.is_approved})')
            else:
                print('    No users found in database.')
            return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        email = sys.argv[1]
    else:
        email = 'csaba.hitter@gmail.com'
    
    print(f'Setting user as admin: {email}')
    print('-' * 50)
    success = set_user_as_admin(email)
    sys.exit(0 if success else 1)

