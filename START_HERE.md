# 🚨 PROBLEMĂ IDENTIFICATĂ: OAuth Token Valid DAR API Returnează 401

---

## ⚡ START RAPID (5 minute)

### 🎯 **CAUZA (90% probabilitate):**

**Aplicația din portal ANAF NU este înregistrată pentru serviciul "E-Factura"**

---

### ✅ **VERIFICARE (2 minute):**

1. **Deschide:** https://www.anaf.ro/InregOauth
2. **Login** cu certificatul digital
3. **Găsește aplicația** cu Client ID: `80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969`
4. **Verifică câmpul "Serviciu"**

**❓ Este "E-Factura"?**

- ✅ **DA** → Mergi la SPV: https://www.anaf.ro/SpvInfoWebService/
  - Poți vedea facturi pentru CIF 51331025?
  - ✅ DA → Contactează suport ANAF
  - ❌ NU → Solicită access pentru CIF

- ❌ **NU** → **AICI ESTE PROBLEMA!** Vezi soluția mai jos ⬇️

---

### 🔧 **SOLUȚIE (10 minute):**

#### 1. Recrează aplicația în portal ANAF

```
Portal: https://www.anaf.ro/InregOauth

1. Login cu certificatul
2. Creează aplicație nouă
3. Denumire: eFactura_Gateway
4. Serviciu: E-Factura  ← IMPORTANT!
5. Callback URL: https://web.anaf-efactura.orb.local/anaf/callback
6. Salvează
7. NOTEAZĂ: Client ID și Client Secret (îți trebuie mai jos)
```

#### 2. Actualizează în aplicație

```
URL: http://localhost:8008/admin/anaf-oauth

1. Introdu noul Client ID
2. Introdu noul Client Secret
3. Click "Save Configuration"
```

#### 3. Re-autentifică

```
URL: http://localhost:8008/anaf/status

1. Click "Disconnect & Delete Token"
2. Click "Connect ANAF Account"
3. Selectează certificatul
4. Autorizează accesul
```

#### 4. Test

```
URL: http://localhost:8008/

1. Selectează compania
2. Click "Sync Invoices"
3. ✅ Ar trebui să apară facturi!
```

---

## 📊 DIAGNOSTIC AUTOMAT

```bash
# Rulează diagnostic complet:
./RUN_DIAGNOSTIC.sh

# Sau în Docker:
docker exec anaf_efactura-web-1 python /app/diagnostic_anaf.py
```

---

## 📚 DOCUMENTAȚIE COMPLETĂ

| Fișier | Descriere |
|--------|-----------|
| **DIAGNOSTIC_README.md** | **Ghid complet** - citește primul |
| REZUMAT_DIAGNOSTIC.md | Analiza tehnică detaliată |
| VERIFICARE_PORTAL_ANAF.md | Pași verificare portal |

---

## 🎓 DE CE SE ÎNTÂMPLĂ?

**Token-ul OAuth ANAF este legat de SERVICIUL aplicației:**

- Aplicație pentru "e-Transport" → Token NU funcționează pentru "E-Factura"
- Aplicație pentru "E-Factura" → Token funcționează DOAR pentru "E-Factura"

**Eroarea "invalid_token" înseamnă:**
- Token VALID din punct de vedere OAuth ✅
- DAR fără permisiuni pentru acest API/serviciu ❌

---

## 📞 SUPORT ANAF

Dacă problema persistă după toate verificările:

**Email:** suport.efactura@anaf.ro  
**Template mesaj:** Vezi `REZUMAT_DIAGNOSTIC.md`

---

## ✅ REZUMAT

**PROBLEMA:**
```
✅ OAuth funcționează
✅ Token valid (89 zile)
✅ Companie înregistrată
❌ API returnează: 401 Unauthorized (error="invalid_token")
```

**CAUZA:**
```
Token-ul OAuth este pentru ALT SERVICIU (nu E-Factura)
```

**SOLUȚIE:**
```
1. Recrează aplicația cu serviciul "E-Factura"
2. Actualizează Client ID/Secret
3. Re-autentifică
4. Test
```

**TIMP ESTIMAT:** 10-15 minute

---

🎯 **ACȚIUNE IMEDIATĂ:** Verifică portal ANAF ACUM → https://www.anaf.ro/InregOauth

📖 **DETALII COMPLETE:** Citește `DIAGNOSTIC_README.md`

