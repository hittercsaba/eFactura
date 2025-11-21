#!/usr/bin/env python3
"""
Test script to verify ANAF OAuth implementation
This script helps diagnose OAuth configuration issues
"""

import sys
import os
from urllib.parse import urlencode, urlparse, parse_qs

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_oauth_url_generation():
    """Test OAuth URL generation"""
    print("=" * 60)
    print("ANAF OAuth Configuration Test")
    print("=" * 60)
    
    # Test parameters
    client_id = input("Enter Client ID (or press Enter to use test value): ").strip()
    if not client_id:
        client_id = "test_client_id"
        print(f"Using test Client ID: {client_id}")
    
    redirect_uri = input("Enter Redirect URI (or press Enter to use test value): ").strip()
    if not redirect_uri:
        redirect_uri = "https://web.anaf-efactura.orb.local/anaf/callback"
        print(f"Using test Redirect URI: {redirect_uri}")
    
    state = "test_state_12345"
    scope = "openid profile email"
    
    # Generate authorization URL
    auth_url = "https://logincert.anaf.ro/anaf-oauth2/v1/authorize"
    
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'state': state
    }
    
    full_url = f"{auth_url}?{urlencode(params)}"
    
    print("\n" + "=" * 60)
    print("Generated Authorization URL:")
    print("=" * 60)
    print(full_url)
    print("\n" + "=" * 60)
    print("URL Components:")
    print("=" * 60)
    parsed = urlparse(full_url)
    print(f"Scheme: {parsed.scheme}")
    print(f"Netloc: {parsed.netloc}")
    print(f"Path: {parsed.path}")
    print(f"Query: {parsed.query}")
    
    query_params = parse_qs(parsed.query)
    print("\nQuery Parameters:")
    for key, value in query_params.items():
        print(f"  {key}: {value[0]}")
    
    print("\n" + "=" * 60)
    print("Verification Checklist:")
    print("=" * 60)
    print(f"✓ Client ID: {client_id}")
    print(f"✓ Redirect URI: {redirect_uri}")
    print(f"✓ State: {state}")
    print(f"✓ Scope: {scope}")
    print("\nImportant checks:")
    print("1. Ensure the Redirect URI matches EXACTLY what is registered with ANAF")
    print("2. Verify the Client ID is correct")
    print("3. Check that the requested scopes are authorized for your application")
    print("4. Ensure the user has proper permissions in ANAF")
    print("\n" + "=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print("1. Copy the authorization URL above")
    print("2. Open it in a browser")
    print("3. Check if you get redirected to ANAF login")
    print("4. After login, check the callback URL for 'code' or 'error' parameters")
    print("=" * 60)

def test_redirect_uri_validation():
    """Test redirect URI format"""
    print("\n" + "=" * 60)
    print("Redirect URI Validation Test")
    print("=" * 60)
    
    test_uris = [
        "https://web.anaf-efactura.orb.local/anaf/callback",
        "http://localhost:5000/anaf/callback",
        "https://example.com/anaf/callback",
        "anaf/callback",  # Invalid - no scheme
        "/anaf/callback",  # Invalid - relative
    ]
    
    for uri in test_uris:
        try:
            parsed = urlparse(uri)
            is_valid = bool(parsed.scheme and parsed.netloc)
            scheme_valid = parsed.scheme in ('http', 'https') if parsed.scheme else False
            
            print(f"\nURI: {uri}")
            print(f"  Valid format: {is_valid}")
            print(f"  Valid scheme: {scheme_valid}")
            if is_valid and scheme_valid:
                print(f"  ✓ This URI should work")
            else:
                print(f"  ✗ This URI will cause issues")
        except Exception as e:
            print(f"\nURI: {uri}")
            print(f"  ✗ Error: {e}")

if __name__ == "__main__":
    try:
        test_oauth_url_generation()
        test_redirect_uri_validation()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()

