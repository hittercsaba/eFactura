# Verificare Portal ANAF - Pași Critici

## 🔍 Problema Actuală

OAuth funcționează (token obținut cu succes), DAR API-ul e-Factura returnează 401 Unauthorized cu `error="invalid_token"`.

## ✅ Pași de Verificare

### 1. Verifică Înregistrarea Aplicației

**Mergi la:** https://www.anaf.ro/InregOauth

**Login** cu certificatul digital

**Verifică:**

#### A. Serviciu Selectat
```
Serviciu:* E-Factura  ← TREBUIE să fie bifat!
```

**Dacă nu este "E-Factura":**
- Aplicația ta este înregistrată pentru alt serviciu (ex: e-Transport)
- Token-ul nu va funcționa pentru e-Factura API

**FIX:** Creează o nouă aplicație SAU modifică aplicația existentă și selectează "E-Factura"

#### B. Callback URLs
```
Callback URL 1: https://web.anaf-efactura.orb.local/anaf/callback
Callback URL 2: (opțional)
```

#### C. Client ID
```
Client ID actual în aplicație: 80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969
Client ID în portal ANAF: _________________________ ← COMPARĂ!
```

**Dacă sunt DIFERITE:** Aplicația folosește Client ID greșit!

---

### 2. Verifică Access în SPV

**Mergi la:** https://www.anaf.ro/SpvInfoWebService/

**Login** cu certificatul digital (ACELAȘI certificat folosit la OAuth!)

**Verifică:**

#### A. Drepturile pentru CIF 51331025
```
□ Are acces la SPV pentru acest CIF?
□ Poate vedea facturi pentru acest CIF?
□ Are rol de "Administrator" sau "Utilizator" pentru acest CIF?
```

**Dacă NU:**
- Certificatul tău nu are drept de acces la acest CIF în SPV
- Token-ul OAuth nu va funcționa pentru acest CIF
- **FIX:** Solicită acces pentru CIF în SPV

#### B. Testează Manual în SPV
```
1. Intră în SPV cu certificatul
2. Selectează CIF 51331025
3. Mergi la "Facturi primite" sau "Facturi emise"
4. Poți vedea facturi?
```

**Dacă DA în SPV, dar NU prin API:**
→ Token-ul OAuth nu este legat corect de certificat/CIF

---

### 3. Verifică Setările Aplicației OAuth

În portal ANAF la **InregOauth**, verifică:

```
Denumire aplicație: eFactura_Gateway (sau similar)

Callback URL 1: https://web.anaf-efactura.orb.local/anaf/callback

Serviciu: E-Factura  ← CRITIC! TREBUIE să fie E-Factura!

Client ID: 80ff76ff68508d6594d862aee5ee2edd0c58d20fd14f2969

Client Secret: (secret)
```

**Regenerează Client Secret** dacă:
- Ai dubii că e corect
- A fost schimbat recent și nu ai actualizat în aplicație

---

### 4. Verifică Log-urile ANAF (Dacă Disponibile)

În portal dezvoltatori ANAF, există de obicei o secțiune pentru **logs** sau **audit**:

```
- Vezi request-urile OAuth făcute de aplicația ta
- Vezi erorile returnate
- Vezi token-urile generate și status-ul lor
```

Caută:
- `invalid_token` errors
- `insufficient_scope` errors
- `access_denied` errors

---

## 🔧 FIX-uri Posibile

### FIX 1: Recreează Aplicația în Portal ANAF

**Pași:**
1. Șterge aplicația existentă din portal ANAF
2. Creează o nouă aplicație
3. **IMPORTANT:** Selectează **"E-Factura"** la "Serviciu"
4. Setează Callback URL: `https://web.anaf-efactura.orb.local/anaf/callback`
5. Salvează și notează noul Client ID și Client Secret
6. Actualizează în aplicația ta (Admin → ANAF OAuth Config)
7. Șterge token-ul vechi (ANAF Connection → Disconnect)
8. Re-autentifică (Connect ANAF Account)

### FIX 2: Adaugă Access la CIF în SPV

**Pași:**
1. Login la SPV cu certificatul
2. Dacă nu vezi CIF 51331025 în lista ta:
   - Solicită acces de la administratorul CIF-ului
   - SAU adaugă CIF-ul în SPV (dacă ești reprezentant legal)
3. Așteaptă aprobare
4. Re-autentifică în aplicație

### FIX 3: Verifică Certificatul Digital

**IMPORTANT:** Certificatul folosit la OAuth **TREBUIE** să fie același cu cel înregistrat în SPV pentru CIF!

Verifică:
```
- Serialul certificatului din logs OAuth
- Serialul certificatului în SPV pentru CIF 51331025
- TREBUIE să fie ACELAȘI!
```

---

## 📊 Comparație Rapidă

| Verificare | Status | FIX Necesar |
|------------|--------|-------------|
| OAuth token obținut? | ✅ DA | - |
| Token are `expires_in`? | ✅ DA (90 zile) | - |
| Aplicație are serviciu "E-Factura"? | ❓ **VERIFICĂ!** | Recreează aplicația |
| CIF 51331025 are access în SPV? | ❓ **VERIFICĂ!** | Solicită access |
| Client ID match cu portal? | ❓ **VERIFICĂ!** | Update în app |
| Certificat același în OAuth și SPV? | ❓ **VERIFICĂ!** | Re-autentifică cu certificatul corect |

---

## 🎯 Acțiune Imediată

**PASUL 1:** Mergi la https://www.anaf.ro/InregOauth

**PASUL 2:** Verifică că aplicația are **"Serviciu: E-Factura"** selectat

**PASUL 3:** 
- Dacă NU → Recreează aplicația cu E-Factura
- Dacă DA → Verifică access la CIF în SPV

**PASUL 4:** După orice modificare, **RE-AUTENTIFICĂ** din aplicație

---

## 📝 Notă

Eroarea `error="invalid_token"` de obicei înseamnă:
- Token-ul OAuth este pentru alt serviciu (nu E-Factura)
- Token-ul nu are permisiuni pentru acest CIF
- Token-ul a fost revocat în portal

**NU înseamnă** că token-ul a expirat (avem 90 zile valabilitate).

