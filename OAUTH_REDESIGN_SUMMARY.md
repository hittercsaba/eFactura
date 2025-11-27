# ANAF OAuth System Redesign - Summary

## What Changed

The OAuth system has been completely redesigned to match ANAF's architecture:

### Before (Per-User OAuth)
- ❌ Each user had their own OAuth client configuration
- ❌ Users had to enter Client ID/Secret themselves
- ❌ Client secret needed re-entry every time

### After (System-Wide OAuth)
- ✅ **One system-wide OAuth configuration** (managed by admin only)
- ✅ **Users authenticate with their digital certificates** (as per ANAF design)
- ✅ **Client secret stored securely** (encrypted, no re-entry needed)
- ✅ **Proper OAuth flow** (removed invalid scopes)

## How It Works Now

### 1. Admin Configuration (One-Time Setup)
**Admin users** configure the system-wide ANAF OAuth settings:

1. Go to: **Admin → ANAF OAuth Config** (new menu item)
2. Enter credentials from ANAF portal:
   - **Client ID**: `84c9275730878042df67bf27ff8a2edd0c58d20fb6292869`
   - **Client Secret**: `4eba53e771cb2e7e84405c88e65ad0e9c02bed1d35922edd0c58d20fb6292869`
   - **Redirect URI**: `https://web.anaf-efactura.orb.local/anaf/callback` (or `https://anaf.processiq.ro/anaf/callback`)
3. Click "Save Configuration"

**Note**: Client secret is only required when creating or updating it. Leave blank to keep existing secret.

### 2. User Authentication (Each User)
**Regular users** simply authenticate with ANAF:

1. Go to Dashboard
2. Click "Connect ANAF Account" button
3. They are redirected to ANAF login page
4. **Select their digital certificate** when prompted
5. Authorize the application
6. They are redirected back with their personal token

**Important**: Each user's token is tied to their digital certificate serial number, not to the OAuth client.

## Key Changes Made

### Database Schema
- **AnafOAuthConfig**: Changed from per-user to system-wide
  - Removed: `user_id` (unique constraint)
  - Added: `created_by` (who configured it)
  - Added: `updated_at` (track modifications)

### Routes
- **New**: `/anaf/admin/config` (GET/POST) - Admin-only OAuth configuration
- **Changed**: `/anaf/connect` (GET only) - Now just redirects users to ANAF for authentication
- **Unchanged**: `/anaf/callback` - Still handles OAuth callback

### Templates
- **New**: `app/templates/anaf/admin_config.html` - Admin OAuth configuration page
- **Removed**: `app/templates/anaf/connect.html` - Old user-facing config form (no longer needed)

### Services
- **OAuthService**: Now loads system-wide OAuth config (not per-user)
- **Client secret**: Always decrypted when loaded, encrypted when stored

### Security Fixes
1. ✅ Removed invalid OAuth scopes (`openid profile email`)
2. ✅ Client secret encryption/decryption fixed
3. ✅ No more double-encryption issues
4. ✅ Increased column sizes for encrypted data

## Current Access Denied Issue

The logs show `access_denied` errors are still occurring. Based on the ANAF documentation and your setup, this could be due to:

### Possible Causes:

1. **Certificate Not Trusted by ANAF**
   - The digital certificate you're using may not be registered in SPV (ANAF's system)
   - ANAF requires a **qualified digital certificate** issued by an accredited provider

2. **User Not Registered in SPV**
   - The user must be registered in ANAF's SPV system
   - They need to have access to e-Factura services

3. **Application Not Fully Approved**
   - Your application might be pending approval in ANAF's developer portal
   - Check the application status at: https://www.anaf.ro/InregOauth

### What to Check:

1. **In ANAF Developer Portal** (https://www.anaf.ro/InregOauth):
   - Application status (Active/Pending?)
   - Callback URLs match exactly:
     - `https://anaf.processiq.ro/anaf/callback`
     - `https://web.anaf-efactura.orb.local/anaf/callback`
   - Service is set to "E-Factura"

2. **Digital Certificate**:
   - Is it a qualified digital certificate from an accredited provider?
   - Is it registered in ANAF's SPV system?
   - Is it valid (not expired)?

3. **User Access**:
   - Does the user have access to e-Factura in SPV?
   - Is the user's CIF registered for e-Factura?

## Next Steps

### 1. Configure OAuth (Admin)
```
1. Login as admin user
2. Go to: Admin → ANAF OAuth Config
3. Enter the correct credentials:
   - Client ID: 84c9275730878042df67bf27ff8a2edd0c58d20fb6292869
   - Client Secret: 4eba53e771cb2e7e84405c88e65ad0e9c02bed1d35922edd0c58d20fb6292869
   - Redirect URI: https://web.anaf-efactura.orb.local/anaf/callback
4. Save
```

### 2. Test User Authentication
```
1. Login as a regular user
2. Go to Dashboard
3. Click "Connect ANAF Account"
4. Select valid digital certificate when prompted
5. Authorize the application
```

### 3. Troubleshoot Access Denied
If still getting `access_denied`:

**A. Verify ANAF Portal Registration**
- Login to https://www.anaf.ro/InregOauth with admin certificate
- Check application status
- Verify callback URLs are exactly: 
  - `https://anaf.processiq.ro/anaf/callback`
  - `https://web.anaf-efactura.orb.local/anaf/callback`

**B. Verify User Certificate**
- Ensure it's a **qualified digital certificate**
- Ensure it's registered in ANAF SPV
- Try using a different certificate if available

**C. Check Logs**
- The logs now show detailed OAuth flow information
- Look for specific error descriptions from ANAF
- Check if authorization code is being returned

## Files Changed

### Models
- `app/models.py` - AnafOAuthConfig schema changes

### Services
- `app/services/oauth_service.py` - System-wide config loading, scope removal

### Routes
- `app/routes/anaf.py` - New admin config route, simplified user connect

### Templates
- `app/templates/anaf/admin_config.html` - New admin config page
- `app/templates/base.html` - Added admin menu section
- `app/templates/anaf/connect.html` - Deleted (no longer needed)

### Migrations
- `migrations/versions/f3a8b9c5d1e2_increase_client_secret_column_size.py` - Increased client_secret to 500 chars
- `migrations/versions/a9c4d3e2f1b5_convert_oauth_to_system_wide.py` - Converted OAuth to system-wide

## Benefits

1. **Simpler for Users**: No need to manage OAuth credentials
2. **More Secure**: Admin-only configuration, encrypted secrets
3. **ANAF Compliant**: Matches ANAF's architecture (certificate-based auth)
4. **Better UX**: Client secret doesn't need re-entry
5. **Centralized**: One place to update OAuth configuration

## Technical Notes

### OAuth Flow (Correct per ANAF Docs)
```
1. User clicks "Connect ANAF Account"
   ↓
2. App redirects to: https://logincert.anaf.ro/anaf-oauth2/v1/authorize
   Parameters: client_id, redirect_uri, response_type=code, state
   (NO scope parameter - ANAF doesn't use OpenID Connect)
   ↓
3. User selects digital certificate
   ↓
4. ANAF authenticates certificate
   ↓
5. User authorizes application
   ↓
6. ANAF redirects to: https://your-domain/anaf/callback?code=XXX&state=YYY
   ↓
7. App exchanges code for token using Basic Auth:
   POST https://logincert.anaf.ro/anaf-oauth2/v1/token
   Authorization: Basic base64(client_id:client_secret)
   Body: grant_type=authorization_code&code=XXX&redirect_uri=...
   ↓
8. ANAF returns access_token + refresh_token
   ↓
9. Token is stored per user (tied to their certificate)
```

### Debugging
The system now logs detailed information at each step:
- Authorization request parameters
- Callback response details
- Token exchange request/response
- Any errors from ANAF

Check logs with:
```bash
docker-compose logs -f web
```

## Support

If you continue to see `access_denied` errors after following this guide:

1. Contact ANAF support regarding application approval status
2. Verify your digital certificate is registered in SPV
3. Check that your CIF is registered for e-Factura services
4. Review ANAF's documentation: https://static.anaf.ro/static/10/Anaf/Informatii_R/API/Oauth_procedura_inregistrare_aplicatii_portal_ANAF.pdf

