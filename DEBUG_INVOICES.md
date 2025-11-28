# Debugging Invoice Sync - ANAF e-Factura

## 🔍 Problema Raportată

**Simptom:** După autentificare OAuth reușită, nu pot vedea facturile în aplicație, deși în portal-ul ANAF le văd când selectez "maximum 60 days back".

---

## 📋 Checklist Diagnostic

### 1. Verifică Autentificarea
- ✅ OAuth funcționează
- ✅ Token-ul este salvat în DB
- ❓ Token-ul este valid pentru API calls

### 2. Verifică Companiile
- ❓ Ai companii adăugate în sistem?
- ❓ CIF-ul companiei este corect?
- ❓ Auto-sync este activat?

### 3. Verifică Logs pentru Erori
- ❓ Apar erori la sync?
- ❓ API endpoint-ul răspunde?
- ❓ Token-ul este acceptat de API?

---

## 🔧 Pași de Rezolvare

### Pas 1: Verifică Starea Sistemului

Rulează în terminal (local):

```bash
# Verifică dacă ai token ANAF
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "SELECT user_id, LEFT(access_token, 20) as token_preview, token_expiry FROM anaf_tokens;"

# Verifică companiile tale
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "SELECT id, user_id, cif, name, auto_sync_enabled FROM companies;"

# Verifică facturile sincronizate
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "SELECT COUNT(*) as total_invoices, company_id FROM invoices GROUP BY company_id;"
```

### Pas 2: Verifică Logs pentru Erori de Sync

```bash
# Caută erori în logs
docker-compose logs --tail=200 web | grep -i "error\|invoice\|sync"

# Caută API calls către ANAF
docker-compose logs --tail=200 web | grep -i "anaf\|lista"
```

### Pas 3: Testează Manual Sync-ul

1. **Accesează aplicația**: https://web.anaf-efactura.orb.local/
2. **Mergi la dashboard**
3. **Click pe "Sync Invoices"** (dacă ai o companie selectată)
4. **Observă logs-urile** în timp real:

```bash
docker-compose logs -f web
```

---

## 🐛 Probleme Posibile și Soluții

### Problema 1: Nicio Companie Adăugată

**Simptom:** Dashboard arată "No Companies Found"

**Cauză:** După OAuth, companiile nu sunt descoperite automat (endpoint-ul ANAF pentru company discovery nu există sau nu funcționează).

**Soluție:** Adaugă manual compania:
1. Mergi la "My Companies"
2. Click "Add Company"
3. Introdu CIF-ul și numele companiei
4. Salvează

### Problema 2: API Endpoint Incorect

**Endpoint actual în cod:**
```python
url = "https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura"
```

**Verificare:** Acest endpoint poate fi diferit. Trebuie verificat în documentația ANAF actualizată.

**Soluție:** Actualizează endpoint-ul cu cel corect din documentația ANAF.

### Problema 3: Token-ul Nu Are Permisiuni pentru API

**Simptom:** OAuth funcționează, dar API calls returnează 401/403.

**Cauză:** Token-ul OAuth este valid dar nu are scope-ul necesar pentru API e-Factura.

**Soluție:** Verifică în portal-ul ANAF dacă aplicația ta are permisiuni pentru serviciul "E-Factura".

### Problema 4: Răspunsul ANAF Are Structură Diferită

**Cod actual parsează:**
```python
invoices_data = invoice_list.get('listaMesajeFactura', []) or \
                invoice_list.get('data', []) or \
                invoice_list.get('invoices', [])
```

**Problemă:** Dacă ANAF returnează structura altfel, lista rămâne goală.

**Soluție:** Logghează răspunsul complet pentru a vedea structura reală.

### Problema 5: Parametrul CIF Trebuie Formatat Diferit

**Cod actual:**
```python
params = {
    'zile': 60,
    'cif': cif  # Ex: "12345678" sau "RO12345678"?
}
```

**Problemă:** ANAF poate aștepta CIF cu sau fără prefix "RO".

**Soluție:** Testează ambele formate.

---

## 🔨 Fix: Adaugă Logging Detaliat

Trebuie să modificăm codul pentru a loga răspunsul de la ANAF.

