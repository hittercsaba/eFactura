#!/usr/bin/env python3
"""
Script to update OAuth redirect URI for both local and production
"""

import psycopg2
import sys

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,  # As per docker-compose.yml
    'database': 'efactura_db',
    'user': 'efactura_user',
    'password': 'efactura_password'
}

def update_redirect_uri():
    """Update redirect URI to support both domains"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check current config
        cursor.execute("SELECT id, redirect_uri FROM anaf_oauth_configs;")
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ No OAuth config found in database")
            return
        
        print("📋 Current OAuth Config:")
        for row in rows:
            print(f"   ID: {row[0]}, Redirect URI: {row[1]}")
        
        # Ask user which domain to use
        print("\n🔧 Choose redirect URI:")
        print("1. Production: https://anaf.processiq.ro/anaf/callback")
        print("2. Local: https://web.anaf-efactura.orb.local/anaf/callback")
        
        choice = input("\nEnter choice (1 or 2): ").strip()
        
        if choice == '1':
            new_uri = 'https://anaf.processiq.ro/anaf/callback'
        elif choice == '2':
            new_uri = 'https://web.anaf-efactura.orb.local/anaf/callback'
        else:
            print("❌ Invalid choice")
            return
        
        # Update
        cursor.execute(
            "UPDATE anaf_oauth_configs SET redirect_uri = %s WHERE id = %s;",
            (new_uri, rows[0][0])
        )
        conn.commit()
        
        print(f"\n✅ Updated redirect URI to: {new_uri}")
        print("\n⚠️  IMPORTANT:")
        print("   - Restart Docker containers: docker-compose restart web")
        print("   - This redirect URI MUST match what's registered in ANAF portal")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    update_redirect_uri()

