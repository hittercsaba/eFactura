#!/usr/bin/env python3
"""
Script de diagnostic și remediere automată pentru integrarea ANAF OAuth2
Verifică configurația și token-urile și sugerează soluții
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection from environment
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://anaf_user:anaf_pass@localhost:5432/anaf_efactura')

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_success(msg):
    """Print success message"""
    print(f"✅ {msg}")

def print_error(msg):
    """Print error message"""
    print(f"❌ {msg}")

def print_warning(msg):
    """Print warning message"""
    print(f"⚠️  {msg}")

def print_info(msg):
    """Print info message"""
    print(f"ℹ️  {msg}")

def get_db_connection():
    """Get database connection"""
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        return Session(), engine
    except Exception as e:
        print_error(f"Nu s-a putut conecta la baza de date: {e}")
        return None, None

def check_oauth_config(session):
    """Check OAuth configuration"""
    print_header("1. VERIFICARE CONFIGURAȚIE OAUTH")
    
    try:
        result = session.execute(text("""
            SELECT id, client_id, redirect_uri, created_by, created_at
            FROM anaf_oauth_configs
            ORDER BY created_at DESC
            LIMIT 1
        """))
        config = result.fetchone()
        
        if not config:
            print_error("Nu există configurație OAuth în baza de date!")
            print_info("SOLUȚIE: Accesează Admin → ANAF OAuth Config și configurează aplicația")
            return None
        
        print_success("Configurație OAuth găsită:")
        print(f"   ID: {config.id}")
        print(f"   Client ID: {config.client_id}")
        print(f"   Redirect URI: {config.redirect_uri}")
        print(f"   Creat de user: {config.created_by}")
        print(f"   Creat la: {config.created_at}")
        
        # Validate Client ID format (ANAF uses 48 characters)
        if len(config.client_id) < 32:
            print_warning(f"Client ID pare prea scurt: {len(config.client_id)} caractere")
        else:
            print_success(f"Client ID are format corect ({len(config.client_id)} caractere)")
        
        # Check redirect URI
        if not config.redirect_uri.startswith('https://'):
            print_error(f"Redirect URI NU folosește HTTPS: {config.redirect_uri}")
        else:
            print_success(f"Redirect URI folosește HTTPS: {config.redirect_uri}")
        
        return config.id
        
    except Exception as e:
        print_error(f"Eroare la verificarea configurației: {e}")
        return None

def check_tokens(session):
    """Check OAuth tokens"""
    print_header("2. VERIFICARE TOKEN-URI OAUTH")
    
    try:
        result = session.execute(text("""
            SELECT 
                t.id, 
                t.user_id, 
                u.email,
                t.access_token, 
                t.refresh_token,
                t.token_expiry
            FROM anaf_tokens t
            JOIN users u ON t.user_id = u.id
            ORDER BY t.id DESC
        """))
        tokens = result.fetchall()
        
        if not tokens:
            print_warning("Nu există token-uri OAuth în baza de date!")
            print_info("SOLUȚIE: Accesează ANAF Connection și click 'Connect ANAF Account'")
            return []
        
        print_success(f"Au fost găsite {len(tokens)} token-uri:")
        
        token_info = []
        for token in tokens:
            print(f"\n   Token ID: {token.id}")
            print(f"   User: {token.email} (ID: {token.user_id})")
            print(f"   Access Token: {token.access_token[:20]}...{token.access_token[-20:]}")
            print(f"   Has Refresh Token: {'✅' if token.refresh_token else '❌'}")
            print(f"   Token Expiry: {token.token_expiry}")
            
            # Check if token is expired
            now = datetime.now(timezone.utc)
            if token.token_expiry.tzinfo is None:
                expiry = token.token_expiry.replace(tzinfo=timezone.utc)
            else:
                expiry = token.token_expiry
            
            if expiry < now:
                print_error("   Token EXPIRAT!")
            else:
                remaining = expiry - now
                days = remaining.days
                print_success(f"   Token VALID (expiră în {days} zile)")
            
            token_info.append({
                'user_id': token.user_id,
                'email': token.email,
                'access_token': token.access_token,
                'expired': expiry < now
            })
        
        return token_info
        
    except Exception as e:
        print_error(f"Eroare la verificarea token-urilor: {e}")
        return []

def check_companies(session):
    """Check registered companies"""
    print_header("3. VERIFICARE COMPANII ÎNREGISTRATE")
    
    try:
        result = session.execute(text("""
            SELECT id, user_id, cif, name, created_at
            FROM companies
            ORDER BY created_at DESC
        """))
        companies = result.fetchall()
        
        if not companies:
            print_warning("Nu există companii înregistrate în baza de date!")
            print_info("SOLUȚIE: Companiile ar trebui să fie adăugate automat după autentificarea OAuth")
            print_info("         Sau le poți adăuga manual din Admin → Companies")
            return []
        
        print_success(f"Au fost găsite {len(companies)} companii:")
        
        company_info = []
        for company in companies:
            print(f"\n   Company ID: {company.id}")
            print(f"   User ID: {company.user_id}")
            print(f"   CIF: {company.cif}")
            print(f"   Name: {company.name}")
            print(f"   Created At: {company.created_at}")
            
            company_info.append({
                'id': company.id,
                'user_id': company.user_id,
                'cif': company.cif,
                'name': company.name
            })
        
        return company_info
        
    except Exception as e:
        print_error(f"Eroare la verificarea companiilor: {e}")
        return []

def test_anaf_api(token_info, company_info):
    """Test ANAF API with current token"""
    print_header("4. TEST ANAF API")
    
    if not token_info:
        print_error("Nu există token-uri pentru test!")
        return False
    
    if not company_info:
        print_error("Nu există companii pentru test!")
        return False
    
    # Use first valid token
    token_data = None
    for token in token_info:
        if not token['expired']:
            token_data = token
            break
    
    if not token_data:
        print_error("Toate token-urile sunt expirate!")
        print_info("SOLUȚIE: Re-autentifică din ANAF Connection → Re-authenticate")
        return False
    
    # Use first company
    company = company_info[0]
    
    print_info(f"Testare cu token pentru: {token_data['email']}")
    print_info(f"Testare cu companie: {company['name']} (CIF: {company['cif']})")
    
    # Test endpoints from documentation
    base_urls = [
        'https://api.anaf.ro',
        'https://webservicesp.anaf.ro',
        'https://webserviceapl.anaf.ro'
    ]
    
    access_token = token_data['access_token']
    cif = company['cif']
    
    for base_url in base_urls:
        print(f"\n   Testare endpoint: {base_url}")
        
        # Test listaMesajeFactura endpoint
        url = f"{base_url}/prod/FCTEL/rest/listaMesajeFactura"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        params = {
            'zile': 60,
            'cif': cif
        }
        
        try:
            print(f"      URL: {url}")
            print(f"      Params: ?zile=60&cif={cif}")
            print(f"      Authorization: Bearer {access_token[:20]}...{access_token[-20:]}")
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            print(f"      Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print_success(f"API call SUCCESS pe {base_url}!")
                try:
                    data = response.json()
                    print(f"      Response data: {json.dumps(data, indent=2)[:500]}...")
                    return True
                except:
                    print(f"      Response text: {response.text[:500]}...")
                    return True
            elif response.status_code == 401:
                print_error(f"401 Unauthorized pe {base_url}")
                print(f"      Headers: {dict(response.headers)}")
                try:
                    error_data = response.json()
                    print(f"      Error: {error_data}")
                except:
                    print(f"      Error text: {response.text}")
            elif response.status_code == 404:
                print_warning(f"404 Not Found pe {base_url} (endpoint greșit)")
            elif response.status_code == 403:
                print_error(f"403 Forbidden pe {base_url}")
            else:
                print_warning(f"Status code neașteptat: {response.status_code}")
                print(f"      Response: {response.text[:500]}")
                
        except requests.exceptions.Timeout:
            print_error(f"Timeout la conectarea către {base_url}")
        except requests.exceptions.ConnectionError as e:
            print_error(f"Connection error: {e}")
        except Exception as e:
            print_error(f"Eroare la testarea API-ului: {e}")
    
    return False

def analyze_documentation():
    """Analyze official documentation"""
    print_header("5. ANALIZĂ DOCUMENTAȚIE OFICIALĂ")
    
    print_info("Conform documentației ANAF e-Factura:")
    print("\n   📄 Documentație: https://mfinante.gov.ro/static/10/eFactura/prezentare%20api%20efactura.pdf")
    
    print("\n   🔑 AUTENTIFICARE:")
    print("      • OAuth2 Authorization Code Grant")
    print("      • Authorization URL: https://logincert.anaf.ro/anaf-oauth2/v1/authorize")
    print("      • Token URL: https://logincert.anaf.ro/anaf-oauth2/v1/token")
    print("      • Revoke URL: https://logincert.anaf.ro/anaf-oauth2/v1/revoke")
    print("      • Authentication: HTTP Basic Auth (client_id:client_secret)")
    
    print("\n   🌐 ENDPOINT-URI API:")
    print("      • OAuth2 Bearer Token: https://api.anaf.ro/prod/FCTEL/rest/...")
    print("      • Certificate mTLS: https://webservicesp.anaf.ro/prod/FCTEL/rest/...")
    print("      • TEST: https://webserviceapl.anaf.ro/test_efactura/... (doar test)")
    
    print("\n   ⚠️  IMPORTANT:")
    print("      • Token-ul OAuth este legat de CERTIFICATUL DIGITAL folosit")
    print("      • Certificatul TREBUIE să aibă access în SPV pentru CIF-ul respectiv")
    print("      • Aplicația TREBUIE să fie înregistrată pentru serviciul 'E-Factura'")
    print("      • Scope-ul OAuth: 'clientappid issuer role serial'")

def provide_solutions(oauth_config, tokens, companies, api_success):
    """Provide solutions based on diagnostic results"""
    print_header("6. SOLUȚII ȘI RECOMANDĂRI")
    
    issues = []
    
    if not oauth_config:
        issues.append({
            'severity': 'CRITICAL',
            'issue': 'Configurație OAuth lipsă',
            'solution': 'Accesează http://localhost:8008/admin/anaf-oauth și configurează Client ID/Secret din portal ANAF'
        })
    
    if not tokens:
        issues.append({
            'severity': 'CRITICAL',
            'issue': 'Token OAuth lipsă',
            'solution': 'Accesează http://localhost:8008/anaf/status și click "Connect ANAF Account"'
        })
    
    expired_tokens = [t for t in tokens if t.get('expired', False)]
    if expired_tokens:
        issues.append({
            'severity': 'HIGH',
            'issue': f'{len(expired_tokens)} token(uri) expirat(e)',
            'solution': 'Accesează http://localhost:8008/anaf/status și click "Re-authenticate"'
        })
    
    if not companies:
        issues.append({
            'severity': 'MEDIUM',
            'issue': 'Nicio companie înregistrată',
            'solution': 'Companiile ar trebui adăugate automat după autentificare. Verifică logs sau adaugă manual.'
        })
    
    if not api_success and tokens and companies:
        issues.append({
            'severity': 'CRITICAL',
            'issue': 'API call eșuat (401 Unauthorized)',
            'solution': [
                '1. Verifică în portal ANAF (https://www.anaf.ro/InregOauth):',
                '   • Aplicația TREBUIE să fie pentru serviciul "E-Factura"',
                '   • Client ID trebuie să fie corect',
                '   • Callback URL trebuie să fie corect',
                '2. Verifică în SPV (https://www.anaf.ro/SpvInfoWebService/):',
                '   • Certificatul TREBUIE să aibă access la CIF-ul respectiv',
                '   • Poți vedea facturi manual în SPV pentru acest CIF?',
                '3. Dacă aplicația este pentru alt serviciu (nu E-Factura):',
                '   • Creează o nouă aplicație în portal ANAF cu serviciul "E-Factura"',
                '   • Actualizează Client ID/Secret în aplicație',
                '   • Disconnect și re-autentifică'
            ]
        })
    
    if not issues:
        print_success("Nu au fost detectate probleme majore!")
        if api_success:
            print_success("API call SUCCESS! Totul funcționează corect! 🎉")
        return True
    
    print(f"\n   Au fost detectate {len(issues)} probleme:\n")
    
    for i, issue in enumerate(issues, 1):
        severity_icons = {
            'CRITICAL': '🔴',
            'HIGH': '🟠',
            'MEDIUM': '🟡',
            'LOW': '🟢'
        }
        icon = severity_icons.get(issue['severity'], '⚪')
        
        print(f"{icon} PROBLEMA {i} [{issue['severity']}]: {issue['issue']}")
        solution = issue['solution']
        if isinstance(solution, list):
            print("   SOLUȚIE:")
            for line in solution:
                print(f"      {line}")
        else:
            print(f"   SOLUȚIE: {solution}")
        print()
    
    return len(issues) == 0

def main():
    """Main diagnostic function"""
    print_header("🔍 DIAGNOSTIC ANAF e-Factura OAuth2")
    print("\nAcest script va verifica configurația, token-urile și va testa API-ul ANAF.\n")
    
    session, engine = get_db_connection()
    if not session:
        sys.exit(1)
    
    try:
        # Run diagnostics
        oauth_config = check_oauth_config(session)
        tokens = check_tokens(session)
        companies = check_companies(session)
        
        # Test API
        api_success = False
        if tokens and companies:
            api_success = test_anaf_api(tokens, companies)
        
        # Analyze documentation
        analyze_documentation()
        
        # Provide solutions
        success = provide_solutions(oauth_config, tokens, companies, api_success)
        
        print_header("FINALIZARE DIAGNOSTIC")
        
        if success and api_success:
            print_success("✅ Toate verificările au trecut! Sistemul funcționează corect!")
            sys.exit(0)
        else:
            print_error("❌ Au fost detectate probleme. Urmează soluțiile de mai sus.")
            sys.exit(1)
        
    finally:
        session.close()
        engine.dispose()

if __name__ == '__main__':
    main()

