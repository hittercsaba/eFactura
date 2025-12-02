#!/usr/bin/env python3
"""
Script pentru verificarea documentației oficiale ANAF și interpretarea corectă
"""

import requests
import sys

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def check_documentation_url():
    """Check if documentation URL is accessible"""
    print_header("📄 VERIFICARE DOCUMENTAȚIE OFICIALĂ ANAF")
    
    doc_url = "https://mfinante.gov.ro/static/10/eFactura/prezentare%20api%20efactura.pdf"
    
    print(f"\n📥 Încercare de descărcare documentație de la:")
    print(f"   {doc_url}")
    
    try:
        response = requests.head(doc_url, timeout=10, allow_redirects=True)
        
        if response.status_code == 200:
            print(f"✅ Documentația este accesibilă!")
            print(f"   Content-Type: {response.headers.get('Content-Type')}")
            print(f"   Content-Length: {response.headers.get('Content-Length')} bytes")
            return True
        else:
            print(f"❌ Status Code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Eroare la accesarea documentației: {e}")
        return False

def explain_oauth_flow():
    """Explain the correct OAuth flow based on ANAF documentation"""
    print_header("🔐 FLUXUL OAUTH CORECT CONFORM ANAF")
    
    print("""
PASUL 1: ÎNREGISTRARE APLICAȚIE în Portal ANAF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌐 URL: https://www.anaf.ro/InregOauth

📝 IMPORTANT - Setări Aplicație:
   • Denumire aplicație: eFactura_Gateway (sau numele dorit)
   • Serviciu: "E-Factura"  ← CRITIC! TREBUIE să fie E-Factura!
   • Callback URL: https://web.anaf-efactura.orb.local/anaf/callback
   
⚠️  NOTĂ CRITICĂ:
   Token-ul OAuth va fi VALABIL doar pentru serviciul selectat!
   Dacă selectezi "e-Transport", token-ul NU va funcționa pentru e-Factura!


PASUL 2: AUTENTIFICARE UTILIZATOR cu CERTIFICAT DIGITAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 Caracteristici Token OAuth:
   • Token-ul este legat de CERTIFICATUL DIGITAL folosit
   • Token-ul identifică UTILIZATORUL, nu aplicația
   • Token-ul este valid pentru CIF-urile la care utilizatorul are access în SPV
   
⚠️  VERIFICARE OBLIGATORIE în SPV:
   Portal: https://www.anaf.ro/SpvInfoWebService/
   
   Utilizatorul (certificatul) TREBUIE să aibă:
   ✅ Access la CIF-ul pentru care vrei să accesezi facturile
   ✅ Rol de Administrator sau Utilizator pentru acel CIF
   ✅ Permisiuni de vizualizare facturi în SPV
   
   Testare:
   1. Login în SPV cu ACELAȘI certificat folosit la OAuth
   2. Selectează CIF-ul dorit (ex: 51331025)
   3. Mergi la "Facturi primite" sau "Facturi emise"
   4. Poți vedea facturi? 
      ✅ DA → Token-ul ar trebui să funcționeze
      ❌ NU → Token-ul NU va funcționa pentru acest CIF!


PASUL 3: ENDPOINT-URI API CORECTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 Conform documentației oficiale ANAF:

1️⃣  Pentru OAuth2 (Bearer Token):
    Base URL: https://api.anaf.ro
    Exemplu: https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura
    
    Autentificare:
    Authorization: Bearer {access_token}
    
2️⃣  Pentru Certificat mTLS (direct certificate authentication):
    Base URL: https://webservicesp.anaf.ro
    Exemplu: https://webservicesp.anaf.ro/prod/FCTEL/rest/listaMesajeFactura
    
    Autentificare:
    Client Certificate (mTLS)
    
3️⃣  Pentru TEST (doar pentru dezvoltare):
    Base URL: https://webserviceapl.anaf.ro
    Exemplu: https://webserviceapl.anaf.ro/test_efactura/...


PASUL 4: PARAMETRI REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━

Exemplu listaMesajeFactura:

GET https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura?zile=60&cif=51331025

Headers:
    Authorization: Bearer {access_token}
    Content-Type: application/json
    Accept: application/json

Parametri:
    zile: numărul de zile în urmă (maxim 60)
    cif: CIF-ul companiei (fără RO)


CAUZE COMUNE PENTRU 401 UNAUTHORIZED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 1. Aplicația NU este pentru serviciul "E-Factura"
       → Token-ul este valid pentru alt serviciu (ex: e-Transport)
       → SOLUȚIE: Recrează aplicația cu serviciul "E-Factura"

🔴 2. Certificatul NU are access la CIF în SPV
       → Token-ul este valid, dar fără permisiuni pentru acest CIF
       → SOLUȚIE: Adaugă certificatul în SPV pentru CIF-ul respectiv

🔴 3. Client ID/Secret greșit
       → Token-ul a fost generat cu alt Client ID
       → SOLUȚIE: Verifică că Client ID din aplicație = Client ID din portal

🔴 4. Token expirat
       → Token-ul nu mai este valid
       → SOLUȚIE: Re-autentifică (obține token nou)

🔴 5. Endpoint greșit
       → Folosești webservicesp.anaf.ro în loc de api.anaf.ro
       → SOLUȚIE: Pentru OAuth2, folosește api.anaf.ro


VERIFICARE RAPIDĂ - CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ 1. Aplicația din portal ANAF are serviciul "E-Factura" selectat?
□ 2. Client ID din aplicație = Client ID din portal ANAF?
□ 3. Certificatul poate vedea facturi în SPV manual?
□ 4. Token-ul nu este expirat? (verifică token_expiry)
□ 5. Folosești endpoint-ul corect? (api.anaf.ro pentru OAuth2)
□ 6. CIF-ul este corect și fără prefix "RO"?

""")

def provide_next_steps():
    """Provide next steps for the user"""
    print_header("🚀 PAȘI URMĂTORI")
    
    print("""
ACȚIUNE IMEDIATĂ:

1️⃣  Verifică Portal ANAF:
    https://www.anaf.ro/InregOauth
    
    ✅ Login cu certificatul
    ✅ Verifică aplicația ta
    ✅ Serviciu selectat: E-Factura?
    ✅ Client ID: 80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969?
    
    Dacă serviciul NU este "E-Factura":
    → Recrează aplicația SAU editează aplicația existentă
    → Selectează serviciul "E-Factura"
    → Notează noul Client ID și Client Secret

2️⃣  Verifică SPV:
    https://www.anaf.ro/SpvInfoWebService/
    
    ✅ Login cu ACELAȘI certificat
    ✅ Poți vedea CIF 51331025?
    ✅ Poți vedea facturi pentru acest CIF?
    
    Dacă NU:
    → Solicită access pentru CIF de la administrator
    → SAU adaugă CIF-ul în SPV (dacă ești reprezentant legal)

3️⃣  Actualizează Aplicația (dacă Client ID s-a schimbat):
    
    a) Accesează: http://localhost:8008/admin/anaf-oauth
       sau: https://web.anaf-efactura.orb.local/admin/anaf-oauth
    
    b) Introdu noul Client ID și Client Secret
    
    c) Salvează

4️⃣  Șterge Token-ul Vechi și Re-autentifică:
    
    a) Accesează: http://localhost:8008/anaf/status
    
    b) Click "Disconnect & Delete Token"
    
    c) Click "Connect ANAF Account"
    
    d) Selectează certificatul când ești întrebat
    
    e) Autorizează accesul

5️⃣  Testează din Nou:
    
    a) Mergi la Dashboard
    
    b) Selectează compania (CIF 51331025)
    
    c) Click "Sync Invoices"
    
    d) Verifică logs:
       docker logs anaf_efactura-web-1 -f


CONTACT SUPORT ANAF (dacă problema persistă):

📧 Email: suport.efactura@anaf.ro

📝 Mesaj sugestat:

    Subiect: Eroare 401 Unauthorized la accesarea API e-Factura cu OAuth2
    
    Bună ziua,
    
    Am implementat o aplicație pentru accesarea API-ului e-Factura folosind
    autentificarea OAuth2 conform documentației oficiale.
    
    Detalii aplicație:
    - Denumire: eFactura_Gateway
    - Client ID: 80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969
    - Serviciu: E-Factura
    - Callback URL: https://web.anaf-efactura.orb.local/anaf/callback
    
    PROBLEMA:
    - Autentificarea OAuth funcționează corect (obțin access_token)
    - Token-ul are scope: "clientappid issuer role serial"
    - Token-ul este valid (expires_in: 7776000 = 90 zile)
    
    DAR la apelarea endpoint-ului:
    GET https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura?zile=60&cif=51331025
    
    primesc:
    - Status: 401 Unauthorized
    - Error: "invalid_token"
    - WWW-Authenticate: Bearer realm="jwk_...",error="invalid_token"
    
    VERIFICĂRI EFECTUATE:
    ✅ Certificatul digital poate accesa manual SPV și e-Factura portal
    ✅ Pot vedea facturi manual în portal pentru CIF 51331025
    ✅ Token-ul OAuth nu este expirat
    ✅ Folosesc endpoint-ul corect: api.anaf.ro (nu webservicesp)
    ✅ Authorization header: Bearer {access_token}
    
    Vă rog să verificați dacă:
    - Token-ul OAuth este corect asociat cu certificatul meu
    - Aplicația are permisiunile corecte pentru serviciul E-Factura
    - Există alte setări necesare în portal ANAF
    
    Mulțumesc,
    [Numele tău]

""")

def main():
    """Main function"""
    check_documentation_url()
    explain_oauth_flow()
    provide_next_steps()
    
    print_header("✅ FINALIZARE")
    print("\n📋 Rezumat:")
    print("   1. Verifică portal ANAF - aplicația TREBUIE să fie pentru 'E-Factura'")
    print("   2. Verifică SPV - certificatul TREBUIE să aibă access la CIF")
    print("   3. Actualizează Client ID/Secret dacă s-a schimbat")
    print("   4. Disconnect și re-autentifică pentru token nou")
    print("   5. Testează din dashboard")
    print("\n🎯 ACȚIUNE PRIORITARĂ: Verifică în portal ANAF serviciul aplicației!")
    print()

if __name__ == '__main__':
    main()

