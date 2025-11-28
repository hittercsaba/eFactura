# Comenzi Pentru Copierea Token-ului OAuth din Producție în Dev

## 📤 PE PRODUCȚIE: Extrage Token-ul

**SSH la server și rulează:**

```bash
# Extrage token-ul din baza de date producție
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "SELECT 
    user_id,
    access_token,
    refresh_token,
    to_char(token_expiry, 'YYYY-MM-DD HH24:MI:SS') as token_expiry,
    to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
   FROM anaf_tokens 
   WHERE user_id = 1;"
```

**Output-ul va arăta ceva de genul:**
```
 user_id |              access_token              |             refresh_token              |    token_expiry     |     updated_at      
---------+----------------------------------------+----------------------------------------+---------------------+---------------------
       1 | eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9... | eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9... | 2026-02-25 10:00:00 | 2025-11-28 09:30:00
```

**📋 Salvează aceste 3 valori:**
1. `access_token` - Token-ul JWT complet
2. `refresh_token` - Refresh token-ul complet  
3. `token_expiry` - Data expirării

---

## 📥 PE LOCAL: Importă Token-ul

**În terminalul local, rulează:**

```bash
cd /Users/csabahitter/Desktop/python/ANAF_eFactura

# IMPORTANT: Înlocuiește valorile cu cele de mai sus!
docker-compose exec db psql -U efactura_user -d efactura_db << 'EOF'
INSERT INTO anaf_tokens (user_id, access_token, refresh_token, token_expiry, updated_at) 
VALUES (
  1, 
  'COPIAZĂ_ACCESS_TOKEN_AICI',
  'COPIAZĂ_REFRESH_TOKEN_AICI',
  '2026-02-25 10:00:00+00',
  NOW()
)
ON CONFLICT (user_id) 
DO UPDATE SET
  access_token = EXCLUDED.access_token,
  refresh_token = EXCLUDED.refresh_token,
  token_expiry = EXCLUDED.token_expiry,
  updated_at = NOW();
EOF
```

**Exemplu concret (NU folosi aceste valori, sunt doar exemplu!):**

```bash
docker-compose exec db psql -U efactura_user -d efactura_db << 'EOF'
INSERT INTO anaf_tokens (user_id, access_token, refresh_token, token_expiry, updated_at) 
VALUES (
  1, 
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c',
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c',
  '2026-02-25 10:00:00+00',
  NOW()
)
ON CONFLICT (user_id) 
DO UPDATE SET
  access_token = EXCLUDED.access_token,
  refresh_token = EXCLUDED.refresh_token,
  token_expiry = EXCLUDED.token_expiry,
  updated_at = NOW();
EOF
```

---

## ✅ Verificare După Import

```bash
# Verifică că token-ul a fost importat corect
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "SELECT 
    user_id, 
    LEFT(access_token, 40) as token_preview,
    token_expiry,
    token_expiry > NOW() as is_valid,
    EXTRACT(EPOCH FROM (token_expiry - NOW()))/3600/24 as days_remaining
   FROM anaf_tokens;"
```

**Output așteptat:**
```
 user_id |             token_preview              |    token_expiry     | is_valid | days_remaining 
---------+----------------------------------------+---------------------+----------+----------------
       1 | eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9... | 2026-02-25 10:00:00 | t        |           89.5
```

**Verifică:**
- ✅ `is_valid` = `t` (true) → Token-ul nu este expirat
- ✅ `days_remaining` > 0 → Token-ul este încă valid

---

## 🔄 Restart și Testează

```bash
# Restart aplicația
docker-compose restart web

# Așteaptă 10 secunde
sleep 10

# Watch logs
docker logs anaf_efactura-web-1 -f
```

**În browser:**
1. Accesează: http://localhost:8008/ (sau https://web.anaf-efactura.orb.local/)
2. Dashboard
3. Click "Sync Invoices"

**În logs AR TREBUI să vezi:**
```
=== ANAF API REQUEST: Lista Mesaje Factura ===
URL: https://webservicesp.anaf.ro/prod/FCTEL/rest/listaMesajeFactura  ← NOU!
Response Status: 200  ← NU mai 401!
Extracted X invoices from response
Synced X invoices for company 1
```

---

## 📝 Note Importante

### 1. Token-ul OAuth din Producție
- **Access Token:** Valabil **90 de zile** (conform ANAF)
- **Refresh Token:** Valabil **365 de zile**
- După expirare, aplicația va încerca auto-refresh
- Dacă refresh-ul eșuează, trebuie re-autentificare

### 2. Format Token
Token-urile sunt de obicei în format JWT:
```
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWI...
```
- Foarte lungi (câteva sute de caractere)
- Copiază COMPLET (toată linia)
- Nu adăuga spații sau newlines

### 3. Security
Token-ul dat acces complet la API-ul ANAF pentru CIF-ul tău.
- ⚠️ Nu-l partaja public
- ⚠️ Nu-l commit-a în Git
- ✅ Este stocat criptat în producție

---

## 🚀 Rezumat Rapid

**Fix aplicat:**
- ✅ Schimbat endpoint de la `api.anaf.ro` → `webservicesp.anaf.ro`
- ✅ Adăugat logging detaliat
- ✅ Fix timezone (deja aplicat)

**Ce trebuie să faci:**
1. **Copiază token-ul** din producție (comanda de mai sus)
2. **Importă în local** (comanda INSERT de mai sus)
3. **Restart:** `docker-compose restart web`
4. **Testează sync:** Dashboard → Sync Invoices

**După fix, facturile ar trebui să apară!** 🎉

