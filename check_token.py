#!/usr/bin/env python3
"""Check ANAF token status in local database"""
import psycopg2
from datetime import datetime

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,  # As per docker-compose.yml
    'database': 'efactura_db',
    'user': 'efactura_user',
    'password': 'efactura_password'
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("📊 ANAF TOKEN STATUS - LOCAL DATABASE")
    print("=" * 80)
    print()
    
    # Check if token exists
    cursor.execute("""
        SELECT 
            user_id, 
            LEFT(access_token, 40) as token_preview,
            LEFT(refresh_token, 40) as refresh_preview,
            token_expiry,
            updated_at,
            token_expiry > NOW() as is_valid,
            EXTRACT(EPOCH FROM (token_expiry - NOW()))/3600 as hours_until_expiry
        FROM anaf_tokens;
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("❌ NO TOKEN FOUND IN DATABASE!")
        print()
        print("🔧 Solution:")
        print("   You need to copy the token from production OR authenticate via OAuth.")
        print()
        print("   Option 1: Copy from production (see SYNC_INVOICES_GUIDE.md)")
        print("   Option 2: Authenticate at https://anaf.processiq.ro/")
    else:
        for row in rows:
            user_id, token_prev, refresh_prev, expiry, updated, is_valid, hours = row
            
            print(f"✅ Token found for user_id: {user_id}")
            print(f"   Access Token (preview):  {token_prev}...")
            print(f"   Refresh Token (preview): {refresh_prev}...")
            print(f"   Token Expiry:            {expiry}")
            print(f"   Last Updated:            {updated}")
            print(f"   Is Valid:                {'✅ YES' if is_valid else '❌ NO (EXPIRED)'}")
            
            if hours is not None:
                if hours > 0:
                    days = hours / 24
                    print(f"   Time Until Expiry:       {days:.1f} days ({hours:.1f} hours)")
                else:
                    print(f"   Time Since Expiry:       {abs(hours):.1f} hours ago")
            print()
            
            if not is_valid:
                print("⚠️  TOKEN IS EXPIRED!")
                print("   The application should try to refresh it automatically.")
                print("   If refresh fails, you need to re-authenticate.")
                print()
    
    # Also check OAuth config
    print("=" * 80)
    print("📋 OAUTH CONFIGURATION")
    print("=" * 80)
    print()
    
    cursor.execute("""
        SELECT 
            id,
            client_id,
            redirect_uri,
            created_by,
            created_at
        FROM anaf_oauth_configs;
    """)
    
    config_rows = cursor.fetchall()
    
    if not config_rows:
        print("❌ NO OAUTH CONFIG FOUND!")
        print("   Admin needs to configure OAuth at: Admin → ANAF OAuth Config")
    else:
        for config in config_rows:
            config_id, client_id, redirect_uri, created_by, created_at = config
            print(f"✅ OAuth Config ID: {config_id}")
            print(f"   Client ID:      {client_id}")
            print(f"   Redirect URI:   {redirect_uri}")
            print(f"   Created By:     User {created_by}")
            print(f"   Created At:     {created_at}")
            print()
    
    # Check companies
    print("=" * 80)
    print("🏢 COMPANIES")
    print("=" * 80)
    print()
    
    cursor.execute("""
        SELECT 
            id,
            user_id,
            cif,
            name,
            auto_sync_enabled
        FROM companies;
    """)
    
    company_rows = cursor.fetchall()
    
    if not company_rows:
        print("❌ NO COMPANIES FOUND!")
        print("   Add a company at: My Companies → Add Company")
    else:
        for company in company_rows:
            comp_id, user_id, cif, name, auto_sync = company
            print(f"✅ Company ID: {comp_id}")
            print(f"   CIF:         {cif}")
            print(f"   Name:        {name}")
            print(f"   User ID:     {user_id}")
            print(f"   Auto Sync:   {'✅ Enabled' if auto_sync else '❌ Disabled'}")
            
            # Check invoices for this company
            cursor.execute("SELECT COUNT(*) FROM invoices WHERE company_id = %s;", (comp_id,))
            invoice_count = cursor.fetchone()[0]
            print(f"   Invoices:    {invoice_count}")
            print()
    
    cursor.close()
    conn.close()
    
    print("=" * 80)
    
except psycopg2.Error as e:
    print(f"❌ Database error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

