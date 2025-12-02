# 🔍 Diagnostic ANAF e-Factura OAuth2

Această directorie conține instrumente automate pentru diagnostic și remediere a problemelor OAuth2 cu ANAF e-Factura.

---

## 📊 STATUS ACTUAL

| Verificare | Status | Detalii |
|------------|--------|---------|
| OAuth Config | ✅ OK | Client ID configurat |
| OAuth Token | ✅ OK | Token valid (89 zile) |
| Company | ✅ OK | CIF 51331025 înregistrat |
| **API Call** | ❌ **FAILED** | **401 Unauthorized** |

### 🔴 PROBLEMA IDENTIFICATĂ

**API returnează: 401 Unauthorized cu error="invalid_token"**

**Cauza probabilă (90%):** Aplicația din portal ANAF **NU este înregistrată pentru serviciul "E-Factura"**

---

## 🚀 START RAPID

### 1. Rulează Diagnostic Automat

```bash
./RUN_DIAGNOSTIC.sh
```

Acest script va:
- ✅ Verifica configurația OAuth
- ✅ Verifica token-urile (valabilitate, expirare)
- ✅ Verifica companiile înregistrate
- ✅ Testa toate endpoint-urile ANAF
- ✅ Oferi soluții concrete

### 2. Verifică Portal ANAF (OBLIGATORIU!)

🌐 **https://www.anaf.ro/InregOauth**

**Întrebare critică:** Aplicația ta are serviciul **"E-Factura"** selectat?

- ✅ **DA** → Treci la pasul 3
- ❌ **NU** → **AICI ESTE PROBLEMA!** Vezi secțiunea "Soluții" mai jos

### 3. Verifică SPV (dacă aplicația e pentru E-Factura)

🌐 **https://www.anaf.ro/SpvInfoWebService/**

**Întrebare:** Poți vedea facturi manual pentru CIF 51331025?

- ✅ **DA** → Problema e altundeva, contactează suport ANAF
- ❌ **NU** → Solicită access pentru CIF

---

## 📁 FIȘIERE DISPONIBILE

### Script-uri Diagnostic

| Fișier | Descriere | Cum se rulează |
|--------|-----------|----------------|
| `RUN_DIAGNOSTIC.sh` | **Script principal** - diagnostic complet | `./RUN_DIAGNOSTIC.sh` |
| `diagnostic_anaf.py` | Script Python pentru verificări automate | `docker exec anaf_efactura-web-1 python /app/diagnostic_anaf.py` |
| `check_anaf_docs.py` | Explicație flux OAuth și cauze erori | `docker exec anaf_efactura-web-1 python /app/check_anaf_docs.py` |

### Documentație

| Fișier | Descriere | Când să-l citești |
|--------|-----------|-------------------|
| `REZUMAT_DIAGNOSTIC.md` | **Rezumat complet** cu cauze și soluții | **Citește PRIMUL** |
| `VERIFICARE_PORTAL_ANAF.md` | Pași detaliați pentru portal ANAF | Când verifici portal-ul |
| `DIAGNOSTIC_README.md` | Acest fișier - ghid rapid | Pentru overview |

---

## 🔧 SOLUȚII CONCRETE

### SOLUȚIE 1: Aplicația NU este pentru "E-Factura" (90% probabilitate)

#### Ce trebuie să faci:

**A. Recrează aplicația în portal ANAF**

1. Mergi la: https://www.anaf.ro/InregOauth
2. Login cu certificatul digital
3. **Opțional:** Șterge aplicația existentă
4. Click "Creează aplicație nouă"
5. **IMPORTANT:**
   - Denumire: `eFactura_Gateway` (sau alt nume)
   - **Serviciu: E-Factura** ← **CRITIC!**
   - Callback URL: `https://web.anaf-efactura.orb.local/anaf/callback`
6. Salvează
7. **Notează:** Client ID și Client Secret (le vei folosi mai jos)

**B. Actualizează configurația în aplicație**

```bash
# Accesează:
http://localhost:8008/admin/anaf-oauth
# sau:
https://web.anaf-efactura.orb.local/admin/anaf-oauth

# Pași:
1. Introdu noul Client ID (din portal ANAF)
2. Introdu noul Client Secret (din portal ANAF)
3. Click "Save Configuration"
```

**C. Șterge token-ul vechi și re-autentifică**

```bash
# Accesează:
http://localhost:8008/anaf/status

# Pași:
1. Click "Disconnect & Delete Token"
2. Click "Connect ANAF Account"
3. Selectează certificatul când browser-ul întreabă
4. Autorizează accesul când ANAF întreabă
5. Vei fi redirecționat înapoi → Token nou generat!
```

**D. Testează**

```bash
# Dashboard:
http://localhost:8008/

# Pași:
1. Selectează compania: ProcessIQ Consulting SRL
2. Click "Sync Invoices"
3. Ar trebui să apară facturi! 🎉

# Verifică logs dacă ceva nu merge:
docker logs anaf_efactura-web-1 -f
```

---

### SOLUȚIE 2: Certificatul NU are access la CIF (10% probabilitate)

#### Ce trebuie să faci:

**A. Verifică SPV**

```bash
# Accesează:
https://www.anaf.ro/SpvInfoWebService/

# Pași:
1. Login cu ACELAȘI certificat folosit la OAuth
2. Selectează CIF: 51331025
3. Mergi la "Facturi primite" sau "Facturi emise"
4. Poți vedea facturi?
```

**B. Dacă NU poți vedea facturi:**

```
→ Certificatul nu are access la acest CIF
→ Solicită access de la administratorul CIF-ului
→ SAU adaugă certificatul în SPV (dacă ești reprezentant legal)
→ Așteaptă aprobare
→ Re-autentifică în aplicație (vezi SOLUȚIE 1, pasul C)
```

---

## 📋 CHECKLIST COMPLET

Urmează această listă în ordine:

### ✅ Verificări Automate (făcute de script)

- [x] Configurație OAuth există
- [x] Client ID configurat
- [x] Redirect URI corect
- [x] Token OAuth obținut
- [x] Token valid (nu expirat)
- [x] Companie înregistrată

### ⚠️ Verificări Manuale (TREBUIE FĂCUTE DE TINE!)

- [ ] **Am verificat portal ANAF** (https://www.anaf.ro/InregOauth)
  - [ ] Aplicația are serviciul **"E-Factura"** selectat
  - [ ] Client ID din portal = Client ID din aplicație
  - [ ] Callback URL este corect

- [ ] **Am verificat SPV** (https://www.anaf.ro/SpvInfoWebService/)
  - [ ] Pot accesa SPV cu certificatul
  - [ ] CIF 51331025 apare în listă
  - [ ] Pot vedea facturi manual pentru CIF 51331025

### 🔄 Acțiuni de Remediere

- [ ] Am recreat/modificat aplicația (dacă serviciul nu era "E-Factura")
- [ ] Am actualizat Client ID/Secret în aplicație
- [ ] Am șters token-ul vechi
- [ ] Am re-autentificat cu certificatul
- [ ] Am testat sync din dashboard
- [ ] Am verificat logs pentru erori

---

## 🎯 FLOW COMPLET DE REZOLVARE

```
START
  │
  ├─► Rulează: ./RUN_DIAGNOSTIC.sh
  │   └─► Verifică output
  │
  ├─► Mergi la: https://www.anaf.ro/InregOauth
  │   ├─► Serviciu = "E-Factura"?
  │   │   ├─► DA ─► Mergi la SPV
  │   │   └─► NU ─► Recrează aplicația (SOLUȚIE 1)
  │   │             └─► Actualizează config în app
  │   │                 └─► Re-autentifică
  │   │                     └─► TEST
  │
  ├─► Mergi la: https://www.anaf.ro/SpvInfoWebService/
  │   ├─► Vezi facturi pentru CIF 51331025?
  │   │   ├─► DA ─► Contactează suport ANAF
  │   │   └─► NU ─► Solicită access CIF (SOLUȚIE 2)
  │   │             └─► Așteaptă aprobare
  │   │                 └─► Re-autentifică
  │   │                     └─► TEST
  │
  └─► TEST
      ├─► Dashboard → Sync Invoices
      ├─► Apar facturi?
      │   ├─► DA ─► SUCCESS! 🎉
      │   └─► NU ─► Rulează diagnostic din nou
      │             └─► Contactează suport ANAF
```

---

## 🆘 DACĂ PROBLEMA PERSISTĂ

### 1. Rulează din nou diagnostic

```bash
./RUN_DIAGNOSTIC.sh
```

### 2. Verifică logs detaliate

```bash
docker logs anaf_efactura-web-1 -f
```

### 3. Contactează suport ANAF

📧 **Email:** suport.efactura@anaf.ro

📝 **Template mesaj:** Vezi `REZUMAT_DIAGNOSTIC.md` → secțiunea "CONTACT SUPORT ANAF"

---

## 📚 DOCUMENTAȚIE ANAF

- **Portal dezvoltatori:** https://www.anaf.ro/InregOauth
- **SPV:** https://www.anaf.ro/SpvInfoWebService/
- **e-Factura portal:** https://efactura.mfinante.gov.ro
- **Documentație API:** https://mfinante.gov.ro/static/10/eFactura/prezentare%20api%20efactura.pdf

---

## 🔄 COMENZI UTILE

```bash
# Diagnostic complet
./RUN_DIAGNOSTIC.sh

# Verifică documentația OAuth
docker exec anaf_efactura-web-1 python /app/check_anaf_docs.py

# Vezi logs real-time
docker logs anaf_efactura-web-1 -f

# Restart aplicație
docker-compose restart

# Rebuild complet (fără cache)
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Rebuild cu curățare volumes
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

---

## ❓ ÎNTREBĂRI FRECVENTE

### Q: De ce primesc 401 Unauthorized dacă token-ul e valid?

**A:** Token-ul OAuth este legat de **serviciul** pentru care a fost înregistrată aplicația. Dacă aplicația e pentru "e-Transport", token-ul NU funcționează pentru "E-Factura", chiar dacă e valid din punct de vedere OAuth.

### Q: Cum știu pentru ce serviciu e aplicația mea?

**A:** Mergi la https://www.anaf.ro/InregOauth, găsește aplicația cu Client ID-ul tău și verifică câmpul "Serviciu".

### Q: Pot schimba serviciul unei aplicații existente?

**A:** Depinde de portal. Unele portale permit editarea, altele nu. Cea mai sigură variantă: recrează aplicația cu serviciul corect.

### Q: Ce se întâmplă când recreez aplicația?

**A:** Primești un nou Client ID și Client Secret. Trebuie să le actualizezi în aplicație și să re-autentifici (token-ul vechi nu va mai funcționa).

### Q: Cum știu că certificatul meu are access la CIF?

**A:** Mergi la SPV (https://www.anaf.ro/SpvInfoWebService/), login cu certificatul, selectează CIF-ul și încearcă să vezi facturi. Dacă poți vedea facturi manual, token-ul ar trebui să funcționeze.

---

## 📊 STATISTICI DIAGNOSTIC

```
Configurație verificată:  ✅
Token-uri verificate:     ✅
Companii verificate:      ✅
Endpoint-uri testate:     3 (api.anaf.ro, webservicesp.anaf.ro, webserviceapl.anaf.ro)
Erori detectate:          1 (401 Unauthorized)
Cauze probabile:          2 (aplicație sau CIF)
Probabilitate fix:        90% (recreare aplicație)
Timp estimat fix:         10-15 minute
```

---

## ✅ SUCCES!

Când vezi:

```
✅ API call SUCCESS pe https://api.anaf.ro!
✅ Facturi sincronizate cu succes!
```

Problema e rezolvată! 🎉

---

**Ultima actualizare:** 2 Decembrie 2025  
**Versiune:** 1.0  
**Contact:** Vezi REZUMAT_DIAGNOSTIC.md pentru detalii suport

