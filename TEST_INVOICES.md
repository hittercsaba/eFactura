# Test Plan - Invoice Sync

## 🎯 Obiectiv
Să determinăm de ce nu apar facturile în aplicație după autentificare OAuth reușită.

---

## 📋 Pași de Test

### Pasul 1: Verifică Configurarea Inițială

**În aplicație:**
1. Login la: https://web.anaf-efactura.orb.local/auth/login
2. Mergi la Dashboard
3. Verifică dacă ai companii listate

**Dacă NU ai companii:**
1. Mergi la "My Companies"
2. Click "Add Company"
3. Adaugă compania cu CIF-ul tău
4. Salvează

### Pasul 2: Testează Sync Manual

**În aplicație:**
1. Pe Dashboard, selectează o companie
2. Click pe butonul "Sync Invoices"
3. Așteaptă 10-15 secunde

**În terminal (în timp real):**
```bash
docker-compose logs -f web
```

**Ce să cauți în logs:**
- `=== ANAF API REQUEST: Lista Mesaje Factura ===`
- `Response Status: 200` (sau alt status code)
- `Response Data Type: dict` sau `list`
- `Response Keys: ...` (structura răspunsului)
- `Extracted X invoices from response`

### Pasul 3: Analizează Răspunsul

**Notează din logs:**
1. **URL-ul complet**: Ce endpoint exact se apelează?
2. **Status code**: 200 (OK), 401 (Unauthorized), 404 (Not Found), etc.
3. **Response structure**: Ce chei are răspunsul?
4. **Number of invoices**: Câte facturi au fost găsite?

---

## 🐛 Scenarii Posibile și Rezolvări

### Scenariul 1: Status 401 Unauthorized

**Logs:**
```
Response Status: 401
Error Response: {"error": "invalid_token"}
```

**Cauză:** Token-ul OAuth nu este valid pentru API calls.

**Rezolvare:**
1. Token-ul este expirat → Refresh automat (implementat)
2. Token-ul nu are permisiuni API → Verifică în portal ANAF

**Acțiune:**
- Deconectează-te de la ANAF (dacă există opțiunea)
- Reconectează-te și autentifică din nou

### Scenariul 2: Status 404 Not Found

**Logs:**
```
Response Status: 404
```

**Cauză:** Endpoint-ul API este incorect.

**Endpoint actual:** `https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura`

**Rezolvare:** Trebuie să găsim endpoint-ul corect din documentația ANAF.

**Endpoint-uri posibile:**
- `https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura`
- `https://webservicesp.anaf.ro/prod/FCTEL/rest/listaMesajeFactura`
- `https://api.anaf.ro/api/v1/efactura/messages`

### Scenariul 3: Status 200 dar Lista Goală

**Logs:**
```
Response Status: 200
Response Data: {"listaMesajeFactura": []}
Extracted 0 invoices from response
```

**Cauză Posibilă 1:** CIF-ul trebuie formatat diferit

**Test:**
```python
# În DB, verifică cum este stocat CIF-ul
# Poate fi: "12345678" sau "RO12345678"
```

**Cauză Posibilă 2:** Perioada de 60 zile nu include facturi

**Test:** Schimbă parametrul `zile` la 30 sau 90

**Cauză Posibilă 3:** Companiile nu au facturi în SPV

**Verificare:** Intră în portal ANAF și vezi dacă există facturi pentru acest CIF.

### Scenariul 4: Response Are Structură Diferită

**Logs:**
```
Response Status: 200
Response Keys: ['success', 'rezultate', 'total']
Extracted 0 invoices from response
```

**Cauză:** ANAF returnează răspunsul cu o structură diferită decât cea așteptată.

**Cod actual caută:**
- `listaMesajeFactura`
- `data`
- `invoices`
- `mesaje`

**Rezolvare:** Adaugă cheia corectă pe baza logs-urilor.

---

## 🔧 Quick Fixes

### Fix 1: Actualizează Parsing-ul Răspunsului

Dacă logs arată o structură diferită (ex: `{"mesaje": [...]}` sau `{"rezultat": [...]}`):

```python
# În app/services/sync_service.py, adaugă noi chei:
invoices_data = invoice_list.get('listaMesajeFactura', []) or \
                invoice_list.get('data', []) or \
                invoice_list.get('invoices', []) or \
                invoice_list.get('mesaje', []) or \
                invoice_list.get('rezultate', []) or \
                invoice_list.get('rezultat', [])
```

### Fix 2: Actualizează Endpoint-ul API

Dacă primești 404, încearcă alt endpoint:

```python
# În app/services/anaf_service.py:
url = f"{self.base_url}/prod/FCTEL/rest/listaMesajeFactura"  # actual

# Testează cu:
# url = f"https://webservicesp.anaf.ro/prod/FCTEL/rest/listaMesajeFactura"
```

### Fix 3: Adaugă Prefix RO la CIF

Dacă CIF-ul trebuie să aibă prefix:

```python
# În app/services/anaf_service.py:
def lista_mesaje_factura(self, cif, zile=60):
    # Asigură prefix RO dacă lipsește
    if not cif.startswith('RO'):
        cif = f'RO{cif}'
    
    params = {
        'zile': zile,
        'cif': cif
    }
```

---

## 📊 Ce Informații Trebuie Să Îmi Trimiți

După ce rulezi testul, trimite-mi din logs:

1. **Full API URL:**
```
Full URL: https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura?zile=60&cif=XXXXX
```

2. **Response Status:**
```
Response Status: 200
```

3. **Response Structure:**
```
Response Data Type: dict
Response Keys: dict_keys(['listaMesajeFactura', 'serial', 'cui', 'titlu'])
```

4. **Response Content (primele 500 caractere):**
```
Response Data (first 500 chars): {'listaMesajeFactura': [...], ...}
```

5. **Number of Invoices:**
```
Extracted 5 invoices from response
```

Cu aceste informații, pot identifica exact problema și o pot repara!

---

## 🚀 Start Testing

```bash
# Terminal 1: Watch logs
docker-compose logs -f web

# Browser: 
# 1. Go to Dashboard
# 2. Click "Sync Invoices"
# 3. Watch Terminal 1 for detailed logs
```

**Așteaptă 30 secunde** și copiază toate log-urile care încep cu `===` și le trimite aici!

