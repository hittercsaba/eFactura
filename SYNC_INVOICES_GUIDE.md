# Ghid Complet - Sincronizare Facturi ANAF

## 🎯 Problema Actuală

1. ✅ **OAuth funcționează** pe https://anaf.processiq.ro/
2. ❌ **OAuth NU funcționează** local pe https://web.anaf-efactura.orb.local/
3. ❌ **Facturile nu apar** în aplicație (chiar și pe producție unde OAuth funcționează)

---

## 📋 Soluția Completă

### Problema 1: OAuth Funcționează Doar pe Producție

**Cauză:** Redirect URI din baza de date este setată la:
```
https://anaf.processiq.ro/anaf/callback
```

Când încerci local (`https://web.anaf-efactura.orb.local`), ANAF respinge pentru că redirect URI nu se potrivește.

**Soluții:**

#### Opțiunea A: Folosește Producția (Recomandat pentru Acum)
- Accesează ÎNTOTDEAUNA aplicația prin: **https://anaf.processiq.ro/**
- OAuth va funcționa corect
- Poți testa sincronizarea facturilor

#### Opțiunea B: Configurează Pentru Local
Dacă vrei să folosești local, trebuie să:

1. **Adaugi callback-ul local în ANAF portal:**
   - Mergi la: https://www.anaf.ro/InregOauth
   - Login cu certificat
   - Găsește aplicația ta: `eFactura_Gateway`
   - Adaugă al doilea callback URL: `https://web.anaf-efactura.orb.local/anaf/callback`
   
2. **Actualizează DB local:**
```bash
# Rulează scriptul de update
cd /Users/csabahitter/Desktop/python/ANAF_eFactura
python3 fix_oauth_redirect_uri.py
# Alege opțiunea 2 (Local)

# Restart containers
docker-compose restart web
```

---

### Problema 2: Facturile Nu Apar în Aplicație

Chiar și pe producție unde OAuth funcționează, facturile nu apar. Hai să debuggăm:

#### Pasul 1: Verifică Dacă Ai Companii Adăugate

**Pe producție (https://anaf.processiq.ro/):**

1. **Login** la aplicație
2. **Mergi la Dashboard**
3. **Verifică dropdown-ul de companii** (sus în topbar)

**Dacă NU vezi companii:**
- Mergi la **"My Companies"** (în sidebar)
- Click **"Add Company"**
- Completează:
  - **CIF:** (ex: `12345678` sau `RO12345678`)
  - **Name:** Numele companiei
- Click **"Save"**

#### Pasul 2: Sincronizează Manual

**Pe Dashboard:**
1. **Selectează compania** din dropdown
2. Click pe butonul **"Sync Invoices"**
3. **Așteaptă 10-15 secunde**

#### Pasul 3: Verifică Logs-urile (Pe Server Producție)

**SSH la server:**
```bash
ssh user@your-production-server
cd /path/to/ANAF_eFactura

# Watch logs în timp real
sudo docker-compose logs -f web
```

**În alt terminal/fereastră:**
- **Accesează aplicația** în browser
- **Click pe "Sync Invoices"**
- **Observă logs-urile** din primul terminal

**Ce să cauți în logs:**

```bash
# Succes:
=== ANAF API REQUEST: Lista Mesaje Factura ===
URL: https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura
CIF: 12345678
Response Status: 200
Response Keys: dict_keys(['listaMesajeFactura', ...])
Extracted 5 invoices from response
Synced 5 invoices for company 1

# Probleme:
Response Status: 404  # <- Endpoint greșit
Response Status: 401  # <- Token invalid/expirat
Response Status: 403  # <- Lipsă permisiuni
Extracted 0 invoices    # <- Răspuns gol de la ANAF
```

---

## 🔍 Diagnosticare Probleme Invoice Sync

### Scenario 1: Status 404 (Not Found)

**Logs:**
```
Response Status: 404
Error Response: Not Found
```

**Cauză:** Endpoint-ul API este incorect.

**Endpoint actual în cod:**
```
https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura
```

**Endpoint-uri alternative de testat:**
- `https://webservicesp.anaf.ro/prod/FCTEL/rest/listaMesajeFactura`
- `https://api.anaf.ro/prod/FCTEL/rest/lista`

**Soluție:** Trebuie să verificăm documentația ANAF pentru endpoint-ul corect actualizat.

---

### Scenario 2: Status 401/403 (Unauthorized/Forbidden)

**Logs:**
```
Response Status: 401
Error Response: {"error": "invalid_token"}
```

**Cauză:** Token-ul OAuth nu are permisiuni pentru API-ul e-Factura.

**Verificări:**
1. **În ANAF portal** (https://www.anaf.ro/InregOauth):
   - Aplicația ta are "Serviciu: E-Factura" selectat?
   - Aplicația este "Active"?

2. **Reconectare OAuth:**
   - Dacă e nevoie, deconectează și reconectează (va fi implementat)
   - Token-ul va fi regenerat cu permisiunile corecte

---

### Scenario 3: Status 200 dar 0 Facturi

**Logs:**
```
Response Status: 200
Response Keys: dict_keys(['listaMesajeFactura'])
Response Data: {"listaMesajeFactura": []}
Extracted 0 invoices from response
```

**Cauze Posibile:**

#### Cauza 3A: CIF Formatat Greșit

ANAF poate aștepta:
- Cu prefix: `RO12345678`
- Fără prefix: `12345678`

**Verificare:** În ANAF portal, cum apare CIF-ul? Cu sau fără "RO"?

**Test:** Adaugă compania cu ambele formate și testează sync pentru fiecare.

#### Cauza 3B: Nu Există Facturi în Perioada

ANAF returnează doar facturi din ultimele **60 de zile**.

**Verificare:** 
- Accesează portal-ul ANAF SPV
- Mergi la e-Factura
- Verifică dacă există facturi în ultimele 60 zile

**Important:** După 60 de zile, facturile nu mai sunt accesibile prin API!

#### Cauza 3C: CIF-ul Nu Are Acces la e-Factura

**Verificare:**
- CIF-ul este înregistrat pentru e-Factura?
- Ai acces la facturi în portal-ul ANAF pentru acest CIF?

---

### Scenario 4: Răspuns cu Structură Diferită

**Logs:**
```
Response Status: 200
Response Keys: dict_keys(['mesaje', 'total', 'pagina'])
Extracted 0 invoices from response
```

**Cauză:** ANAF returnează răspunsul cu o structură diferită.

**Cod actual caută aceste chei:**
- `listaMesajeFactura`
- `data`
- `invoices`
- `mesaje`

**Soluție:** Dacă vezi altă cheie în logs (ex: `rezultate`, `facturi`), trebuie adăugată în cod.

---

## 🛠️ Quick Fixes

### Fix 1: Actualizează Parsing Răspuns

Dacă vezi în logs o cheie nouă (ex: `rezultate`), adaugă-o:

```python
# În app/services/sync_service.py
invoices_data = invoice_list.get('listaMesajeFactura', []) or \
                invoice_list.get('data', []) or \
                invoice_list.get('invoices', []) or \
                invoice_list.get('mesaje', []) or \
                invoice_list.get('rezultate', [])  # <- Adaugă cheia nouă
```

### Fix 2: Adaugă/Remove Prefix RO

```python
# În app/services/anaf_service.py
def lista_mesaje_factura(self, cif, zile=60):
    # Testează cu prefix
    if not cif.upper().startswith('RO'):
        cif_with_prefix = f'RO{cif}'
    else:
        cif_with_prefix = cif
    
    # Sau testează fără prefix
    cif_without_prefix = cif.replace('RO', '').replace('ro', '')
    
    # Încearcă ambele
    params = {
        'zile': zile,
        'cif': cif  # Testează care funcționează
    }
```

---

## 📊 Ce Informații Am Nevoie

După ce testezi sync-ul pe **producție** (https://anaf.processiq.ro/), trimite-mi din logs:

### 1. Request Details
```
=== ANAF API REQUEST: Lista Mesaje Factura ===
URL: ...
CIF: ...
Zile: ...
Full URL: ...
```

### 2. Response Details
```
Response Status: ...
Response Data Type: ...
Response Keys: ...
Response Data (first 500 chars): ...
```

### 3. Processing Results
```
Extracted X invoices from response
Synced X invoices for company Y
```

### 4. Orice Erori
```
Error: ...
Error Response: ...
```

---

## 🚀 Plan de Acțiune

### Pas 1: Folosește Producția Pentru Acum
```
✅ Accesează: https://anaf.processiq.ro/
✅ OAuth funcționează aici
✅ Testează sincronizarea
```

### Pas 2: Adaugă Companie (Dacă Nu Există)
```
My Companies → Add Company
CIF: 12345678 (sau RO12345678)
Name: Numele companiei
Save
```

### Pas 3: Testează Sync
```
Dashboard → Selectează companie → Sync Invoices
```

### Pas 4: Verifică Logs pe Server
```bash
ssh user@server
cd /path/to/app
docker-compose logs -f web | grep -E "(===|Response|Extracted|Error)"
```

### Pas 5: Trimite-Mi Logs-urile
```
Copiază output-ul din terminal și trimite-mi
Voi identifica problema exactă
```

---

## ⚠️ Note Importante

### Despre Limitarea de 60 Zile
Conform documentației ANAF, facturile sunt disponibile în SPV doar **60 de zile** de la emitere. După aceasta:
- ❌ Nu mai pot fi descărcate prin API
- ❌ Nu mai apar în portal
- ✅ Trebuie arhivate local înainte de expirare

**Recomandare:** Configurează sync automat la fiecare 24 ore pentru a nu pierde facturi.

### Despre Dual Domain Setup
Dacă vrei să folosești AMBELE (local + producție):
1. **În ANAF portal**, adaugă ambele callback URLs:
   - `https://anaf.processiq.ro/anaf/callback`
   - `https://web.anaf-efactura.orb.local/anaf/callback`

2. **În aplicație**, schimbă redirect URI după nevoie:
   - Producție: Setează la `https://anaf.processiq.ro/anaf/callback`
   - Local: Setează la `https://web.anaf-efactura.orb.local/anaf/callback`

---

## 📞 Suport

După ce rulezi testele de mai sus pe **producție** și obții logs-urile, trimite-mi:
1. ✅ Status code (200, 404, 401, etc.)
2. ✅ Response structure (ce chei are răspunsul)
3. ✅ Număr de facturi extrase
4. ✅ Orice erori

Cu aceste informații, pot repara problema în câteva minute! 🎯

