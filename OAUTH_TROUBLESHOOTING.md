# ANAF OAuth Troubleshooting Guide

## Common Error: "OAuth error: access_denied"

This error occurs when ANAF's OAuth service denies the authorization request. Here are the most common causes and solutions:

### 1. Redirect URI Mismatch (Most Common)

**Problem:** The redirect URI in your application does not match exactly what is registered with ANAF.

**Solution:**
- The redirect URI must match **EXACTLY** including:
  - Protocol (http vs https)
  - Domain name
  - Port number (if any)
  - Path
  - Trailing slashes
  
**Example:**
- ✅ Correct: `https://web.anaf-efactura.orb.local/anaf/callback`
- ❌ Wrong: `https://web.anaf-efactura.orb.local/anaf/callback/` (trailing slash)
- ❌ Wrong: `http://web.anaf-efactura.orb.local/anaf/callback` (wrong protocol)

**How to fix:**
1. Check the redirect URI shown in the form (it's displayed below the input field)
2. Log into ANAF's developer portal
3. Verify the redirect URI registered with ANAF matches exactly
4. Update either the application registration or the form value to match

### 2. Invalid Client Credentials

**Problem:** The Client ID or Client Secret is incorrect.

**Solution:**
- Double-check the Client ID and Client Secret from ANAF's developer portal
- Ensure there are no extra spaces or characters
- Verify the credentials haven't expired or been revoked

### 3. Scope Not Authorized

**Problem:** The requested scopes (`openid profile email`) are not authorized for your application.

**Solution:**
1. Check ANAF's developer portal to see which scopes are enabled for your application
2. The application may need to request specific scopes that ANAF requires
3. Contact ANAF support to enable the required scopes

**Note:** ANAF may require different scopes. Common alternatives:
- `openid`
- `profile`
- `email`
- `efactura` (if specific to eFactura API)
- Custom scopes as defined by ANAF

### 4. User Permissions

**Problem:** The user attempting to authorize does not have the required permissions in ANAF.

**Solution:**
- The user must be registered on the ANAF portal
- The user must have a valid digital certificate
- The user must have one of the SPV PJ roles:
  - Legal representative
  - Designated representative
  - Authorized person

### 5. Application Not Properly Registered

**Problem:** The application is not correctly registered with ANAF.

**Solution:**
1. Verify your application is registered in ANAF's developer portal
2. Ensure the application status is "Active" or "Approved"
3. Check that all required information is provided
4. Contact ANAF support if the application is pending approval

## Debugging Steps

### Step 1: Check Application Logs

The application now logs detailed information about the OAuth flow. Check your application logs for:

```
INFO: Generated ANAF authorization URL for user X
DEBUG: Authorization URL: https://logincert.anaf.ro/...
INFO: Redirecting user X to ANAF authorization. Redirect URI: ...
ERROR: OAuth authorization error for user X: error=access_denied, description=...
```

### Step 2: Verify Redirect URI

1. Go to the ANAF connection page
2. Check the redirect URI shown below the input field
3. Compare it with what's registered in ANAF's portal
4. They must match exactly

### Step 3: Test Authorization URL

You can use the test script to generate and verify the authorization URL:

```bash
python test_oauth.py
```

This will help you:
- Verify the URL format
- Check all parameters
- Test the redirect URI format

### Step 4: Check Browser Network Tab

1. Open browser developer tools (F12)
2. Go to the Network tab
3. Attempt the OAuth connection
4. Look for the redirect to ANAF
5. Check the callback URL for error parameters:
   - `?error=access_denied&error_description=...`
   - `?code=...` (success)

### Step 5: Verify ANAF Registration

1. Log into ANAF's developer portal
2. Find your application
3. Verify:
   - Client ID matches
   - Redirect URI matches exactly
   - Application is active
   - Required scopes are enabled

## Testing the OAuth Flow

### Manual Test

1. Fill in the OAuth configuration form:
   - Client ID
   - Client Secret
   - Redirect URI (verify it matches ANAF registration)

2. Click "Save & Connect to ANAF"

3. You should be redirected to ANAF's login page

4. After login, you should either:
   - Be redirected back with a `code` parameter (success)
   - Be redirected back with an `error` parameter (failure)

### Using the Test Script

Run the test script to verify URL generation:

```bash
python test_oauth.py
```

This will:
- Generate a test authorization URL
- Show all parameters
- Validate the redirect URI format
- Provide a checklist of things to verify

## Common ANAF OAuth Endpoints

- **Authorization:** `https://logincert.anaf.ro/anaf-oauth2/v1/authorize`
- **Token:** `https://logincert.anaf.ro/anaf-oauth2/v1/token`
- **Revoke:** `https://logincert.anaf.ro/anaf-oauth2/v1/revoke`

## Getting Help

If you continue to experience issues:

1. **Check Application Logs:** Look for detailed error messages
2. **Verify Configuration:** Use the test script to verify your setup
3. **Contact ANAF Support:** For issues with:
   - Application registration
   - Scope authorization
   - User permissions
   - API access

## Additional Notes

- The redirect URI is case-sensitive
- Some ANAF environments may require HTTPS only
- The state parameter is used for CSRF protection
- Authorization codes are typically single-use and expire quickly

