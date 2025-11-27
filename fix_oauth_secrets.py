#!/usr/bin/env python3
"""
Utility script to clear and re-enter OAuth secrets
Use this if OAuth secrets got corrupted due to double-encryption
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manage import app
from app.models import db, AnafOAuthConfig

def clear_oauth_secrets():
    """Clear all OAuth client secrets to allow re-entry"""
    with app.app_context():
        configs = AnafOAuthConfig.query.all()
        
        if not configs:
            print("No OAuth configurations found.")
            return
        
        print(f"Found {len(configs)} OAuth configuration(s)")
        print("\nCurrent configurations:")
        for config in configs:
            print(f"  User ID: {config.user_id}")
            print(f"  Client ID: {config.client_id}")
            print(f"  Redirect URI: {config.redirect_uri}")
            print(f"  Client Secret: {'[encrypted]' if config.client_secret else '[empty]'}")
            print()
        
        confirm = input("Do you want to clear all client secrets? This will require re-entering them. (yes/no): ")
        
        if confirm.lower() in ['yes', 'y']:
            for config in configs:
                # Delete the entire config to force re-entry
                db.session.delete(config)
            
            db.session.commit()
            print("\n✓ All OAuth configurations cleared.")
            print("Please go to the Connect ANAF page and re-enter your OAuth credentials.")
        else:
            print("Operation cancelled.")

if __name__ == "__main__":
    try:
        clear_oauth_secrets()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

