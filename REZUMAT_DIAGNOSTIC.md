# 🔍 REZUMAT DIAGNOSTIC ANAF e-Factura OAuth2

**Data diagnosticului:** 2 Decembrie 2025  
**Status:** ❌ PROBLEME DETECTATE

---

## ✅ CE FUNCȚIONEAZĂ

| Componentă | Status | Detalii |
|------------|--------|---------|
| **Configurație OAuth** | ✅ OK | Client ID: `80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969` |
| **Token OAuth** | ✅ OK | Token valid (expiră în 89 zile) |
| **Companie înregistrată** | ✅ OK | ProcessIQ Consulting SRL (CIF: 51331025) |
| **Autentificare OAuth** | ✅ OK | Flow complet: authorization → token exchange |
| **Redirect URI** | ✅ OK | `https://web.anaf-efactura.orb.local/anaf/callback` |

---

## ❌ CE NU FUNCȚIONEAZĂ

| Problemă | Severitate | Detalii |
|----------|-----------|---------|
| **API Call** | 🔴 CRITICAL | 401 Unauthorized |
| **Error Code** | 🔴 CRITICAL | `invalid_token` |
| **WWW-Authenticate** | 🔴 CRITICAL | `error="invalid_token"` |

### 📊 Rezultate Test API:

```
✅ OAuth Authentication: SUCCESS
   • Authorization Code: Obținut
   • Access Token: 1492c9a3d806292f29c6...034d8191ee4088ad4987
   • Refresh Token: Obținut
   • Expiry: 90 zile
   • Scope: clientappid issuer role serial

❌ API Call: FAILED
   • Endpoint: https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura
   • Method: GET
   • Params: ?zile=60&cif=51331025
   • Headers: Authorization: Bearer {token}
   • Response: 401 Unauthorized
   • Error: {"message":"Unauthorized","status":"401"}
```

---

## 🎯 CAUZA PROBABILĂ

### **Token-ul OAuth este VALID pentru autentificare, DAR:**

#### 🔴 **CAUZA #1: Aplicația NU este pentru serviciul "E-Factura"**

**Probabilitate:** 🔴🔴🔴🔴🔴 **FOARTE MARE** (90%)

**Explicație:**
- Token-ul OAuth este legat de SERVICIUL pentru care a fost înregistrată aplicația
- Dacă aplicația este înregistrată pentru "e-Transport", token-ul NU va funcționa pentru "E-Factura"
- Token-ul este VALID din punct de vedere OAuth, dar NU are permisiuni pentru API-ul e-Factura

**Verificare:**
```
1. Mergi la: https://www.anaf.ro/InregOauth
2. Login cu certificatul
3. Găsește aplicația cu Client ID: 80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969
4. Verifică câmpul "Serviciu"
5. Este "E-Factura"? 
   ✅ DA → Treci la CAUZA #2
   ❌ NU → ACESTA ESTE PROBLEMA!
```

**Soluție:**
```
OPȚIUNEA A: Editează aplicația existentă (dacă portal permite)
   1. Selectează aplicația
   2. Schimbă serviciul la "E-Factura"
   3. Salvează

OPȚIUNEA B: Creează aplicație nouă (recomandat)
   1. Șterge aplicația existentă (opțional)
   2. Creează aplicație nouă
   3. Denumire: eFactura_Gateway
   4. Serviciu: E-Factura  ← IMPORTANT!
   5. Callback URL: https://web.anaf-efactura.orb.local/anaf/callback
   6. Salvează
   7. Notează noul Client ID și Client Secret
   
   8. Actualizează în aplicație:
      http://localhost:8008/admin/anaf-oauth
      
   9. Re-autentifică:
      http://localhost:8008/anaf/status
      → Disconnect & Delete Token
      → Connect ANAF Account
```

---

#### 🟠 **CAUZA #2: Certificatul NU are access la CIF în SPV**

**Probabilitate:** 🟠🟠🟠 **MEDIE** (30%)

**Explicație:**
- Token-ul OAuth este legat de certificatul digital folosit
- Certificatul TREBUIE să aibă access în SPV pentru CIF-ul respectiv
- Token-ul este valid, dar certificatul nu are permisiuni pentru acest CIF

**Verificare:**
```
1. Mergi la: https://www.anaf.ro/SpvInfoWebService/
2. Login cu ACELAȘI certificat folosit la OAuth
3. Selectează CIF 51331025
4. Mergi la "Facturi primite" sau "Facturi emise"
5. Poți vedea facturi?
   ✅ DA → Token-ul ar trebui să funcționeze (problema e altundeva)
   ❌ NU → ACESTA ESTE PROBLEMA!
```

**Soluție:**
```
1. Solicită access pentru CIF 51331025 de la administrator
2. SAU adaugă CIF-ul în SPV (dacă ești reprezentant legal)
3. Așteaptă aprobare
4. Re-autentifică în aplicație pentru token nou
```

---

#### 🟡 **CAUZA #3: Client ID greșit**

**Probabilitate:** 🟡🟡 **MICĂ** (10%)

**Explicație:**
- Token-ul a fost generat cu alt Client ID decât cel din aplicație
- Aplicația folosește un Client ID, dar token-ul a fost generat pentru alt Client ID

**Verificare:**
```
1. Mergi la: https://www.anaf.ro/InregOauth
2. Găsește aplicația ta
3. Compară Client ID din portal cu cel din aplicație:
   
   Portal ANAF:  _________________________
   Aplicație:    80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969
   
4. Sunt identice?
   ✅ DA → Problema e altundeva
   ❌ NU → ACESTA ESTE PROBLEMA!
```

**Soluție:**
```
1. Actualizează Client ID în aplicație cu cel din portal
2. http://localhost:8008/admin/anaf-oauth
3. Introdu Client ID și Client Secret corecte
4. Salvează
5. Re-autentifică
```

---

## 🔧 PAȘI DE REMEDIERE

### **PASUL 1: Verificare Portal ANAF** (OBLIGATORIU!)

```bash
# Acțiune:
1. Deschide: https://www.anaf.ro/InregOauth
2. Login cu certificatul digital
3. Găsește aplicația cu Client ID: 80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969

# Verifică:
✅ Serviciu: E-Factura (NU alt serviciu!)
✅ Client ID: 80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969
✅ Callback URL: https://web.anaf-efactura.orb.local/anaf/callback

# Dacă Serviciu ≠ "E-Factura":
→ Recrează aplicația cu serviciul "E-Factura"
→ Actualizează Client ID/Secret în aplicație
→ Re-autentifică
```

### **PASUL 2: Verificare SPV** (OBLIGATORIU!)

```bash
# Acțiune:
1. Deschide: https://www.anaf.ro/SpvInfoWebService/
2. Login cu ACELAȘI certificat folosit la OAuth
3. Selectează CIF: 51331025

# Verifică:
✅ Poți vedea CIF 51331025 în listă?
✅ Poți accesa "Facturi primite"?
✅ Poți vedea facturi pentru ultimele 60 zile?

# Dacă NU poți vedea facturi:
→ Solicită access de la administrator CIF
→ SAU adaugă certificatul în SPV pentru CIF
→ Re-autentifică după aprobare
```

### **PASUL 3: Actualizare Configurație** (dacă Client ID s-a schimbat)

```bash
# Acțiune:
1. Accesează: http://localhost:8008/admin/anaf-oauth
2. Introdu noul Client ID (din portal ANAF)
3. Introdu noul Client Secret (din portal ANAF)
4. Salvează
```

### **PASUL 4: Re-autentificare** (OBLIGATORIU după orice modificare)

```bash
# Acțiune:
1. Accesează: http://localhost:8008/anaf/status
2. Click "Disconnect & Delete Token"
3. Click "Connect ANAF Account"
4. Selectează certificatul când browser-ul întreabă
5. Autorizează accesul
```

### **PASUL 5: Test Final**

```bash
# Diagnostic automat:
docker exec anaf_efactura-web-1 python /app/diagnostic_anaf.py

# Verificare logs:
docker logs anaf_efactura-web-1 -f

# Test manual:
1. Mergi la Dashboard: http://localhost:8008/
2. Selectează compania: ProcessIQ Consulting SRL
3. Click "Sync Invoices"
4. Verifică dacă apar facturi
```

---

## 📊 CHECKLIST COMPLET

Urmează acest checklist în ordine:

### ✅ Verificări Sistem

- [x] Configurație OAuth există
- [x] Client ID configurat: `80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969`
- [x] Redirect URI corect: `https://web.anaf-efactura.orb.local/anaf/callback`
- [x] Token OAuth obținut
- [x] Token valid (nu expirat)
- [x] Companie înregistrată: CIF 51331025

### ❓ Verificări Portal ANAF (TREBUIE FĂCUTE MANUAL!)

- [ ] Aplicația din portal are serviciul "E-Factura" selectat
- [ ] Client ID din portal = Client ID din aplicație
- [ ] Callback URL din portal = Callback URL din aplicație
- [ ] Client Secret este corect și actualizat

### ❓ Verificări SPV (TREBUIE FĂCUTE MANUAL!)

- [ ] Certificatul poate accesa SPV
- [ ] CIF 51331025 apare în listă
- [ ] Pot vedea facturi manual în SPV pentru CIF 51331025
- [ ] Certificatul are rol de Administrator sau Utilizator

### 🔄 Acțiuni de Remediere

- [ ] Am verificat serviciul aplicației în portal ANAF
- [ ] Am recreat/modificat aplicația (dacă serviciul nu era "E-Factura")
- [ ] Am actualizat Client ID/Secret în aplicație (dacă s-a schimbat)
- [ ] Am șters token-ul vechi
- [ ] Am re-autentificat cu certificatul
- [ ] Am testat sync din dashboard
- [ ] Am verificat logs pentru erori

---

## 🎯 ACȚIUNE IMEDIATĂ

**PRIORITATE MAXIMĂ:**

1. **Verifică portal ANAF acum**: https://www.anaf.ro/InregOauth
   - Serviciul aplicației TREBUIE să fie "E-Factura"
   - Dacă NU este, ACESTA este problema!

2. **Dacă serviciul NU este "E-Factura":**
   - Recrează aplicația cu serviciul "E-Factura"
   - Actualizează Client ID/Secret în aplicație
   - Re-autentifică

3. **Dacă serviciul ESTE "E-Factura":**
   - Verifică SPV: https://www.anaf.ro/SpvInfoWebService/
   - Certificatul TREBUIE să aibă access la CIF 51331025

---

## 📞 CONTACT SUPORT ANAF

Dacă după toate verificările problema persistă:

**Email:** suport.efactura@anaf.ro

**Template mesaj:**

```
Subiect: Eroare 401 Unauthorized la accesarea API e-Factura cu OAuth2

Bună ziua,

Am implementat o aplicație pentru accesarea API-ului e-Factura folosind 
autentificarea OAuth2 conform documentației oficiale.

DETALII APLICAȚIE:
- Denumire: eFactura_Gateway
- Client ID: 80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969
- Serviciu: E-Factura
- Callback URL: https://web.anaf-efactura.orb.local/anaf/callback

PROBLEMA:
- Autentificarea OAuth funcționează (obțin access_token)
- Token scope: "clientappid issuer role serial"
- Token valid: 90 zile
- DAR la apelarea API-ului primesc 401 Unauthorized, error="invalid_token"

ENDPOINT TESTAT:
GET https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura?zile=60&cif=51331025
Authorization: Bearer {access_token}

VERIFICĂRI EFECTUATE:
✅ Certificatul poate accesa manual SPV și e-Factura portal
✅ Pot vedea facturi manual în portal pentru CIF 51331025
✅ Token-ul nu este expirat
✅ Folosesc endpoint-ul corect: api.anaf.ro
✅ Aplicația este înregistrată pentru serviciul "E-Factura"

Vă rog să verificați configurația aplicației și permisiunile token-ului OAuth.

Mulțumesc,
[Numele tău]
```

---

## 📚 DOCUMENTAȚIE RELEVANTĂ

- Portal dezvoltatori: https://www.anaf.ro/InregOauth
- SPV: https://www.anaf.ro/SpvInfoWebService/
- e-Factura portal: https://efactura.mfinante.gov.ro
- Documentație API: https://mfinante.gov.ro/static/10/eFactura/prezentare%20api%20efactura.pdf

---

**Ultima actualizare:** 2 Decembrie 2025  
**Status diagnostic:** ❌ PROBLEME DETECTATE - NECESITĂ VERIFICARE MANUALĂ PORTAL ANAF

