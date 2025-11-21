# Reverse Proxy Configuration for Nginx Proxy Manager

## Issue: Redirect URI shows HTTP instead of HTTPS

When Flask is behind a reverse proxy (nginx, Apache, etc.), it may not detect that it's using HTTPS unless the proxy sends the appropriate headers.

## Solution for Nginx Proxy Manager

The application now includes `ProxyFix` middleware to handle this. You need to configure Nginx Proxy Manager to forward the required headers.

### Step 1: Configure Custom Nginx Configuration

1. In Nginx Proxy Manager, go to **Hosts** → Select your proxy host (e.g., `anaf.processiq.ro`)
2. Click **Edit** (or the three dots menu → Edit)
3. Go to the **"Advanced"** tab
4. In the **"Custom Nginx Configuration"** text area, add the following:

```nginx
# Forward protocol information to Flask application
location / {
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

**Important Notes:**
- Nginx Proxy Manager already sets some headers by default, but we need to ensure `X-Forwarded-Proto` is explicitly set
- The `$scheme` variable will be `https` when SSL is enabled
- This configuration must be in a `location /` block

### Step 2: Verify SSL Settings

1. Go to the **"SSL"** tab in the proxy host settings
2. Ensure:
   - **SSL Certificate** is set (e.g., Let's Encrypt)
   - **Force SSL** is enabled (recommended)
   - **HTTP/2 Support** is enabled (optional but recommended)
   - **HSTS Enabled** is enabled (optional but recommended for security)

### Step 3: Verify Details Tab

In the **"Details"** tab, ensure:
- **Forward Hostname/IP** points to your Flask application (e.g., `http://192.168.1.221:8000`)
- **Forward Port** is correct (e.g., `8000`)
- **Block Common Exploits** is enabled (recommended)
- **Websockets Support** is enabled if needed

### Alternative: If Custom Location is Needed

If you need to add headers in a custom location (as the warning suggests), you can use:

```nginx
# Custom location for root path
location = / {
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# Apply to all paths
location / {
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
}
```

### Standard Nginx Configuration (if not using Nginx Proxy Manager)

If you're configuring nginx directly, add these headers:

```nginx
location / {
    proxy_pass http://localhost:8000;  # or your Flask app URL
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;  # IMPORTANT: This tells Flask it's HTTPS
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
}
```

### Apache Configuration

For Apache with mod_proxy:

```apache
ProxyPreserveHost On
ProxyPass / http://localhost:8000/
ProxyPassReverse / http://localhost:8000/

# Set headers for proxy
RequestHeader set X-Forwarded-Proto "https"
RequestHeader set X-Forwarded-Host "%{HTTP_HOST}e"
```

### Docker/Container Setup

If using Docker with a reverse proxy, ensure the proxy container sends these headers.

## Verification

After configuring your reverse proxy:

1. Restart your Flask application
2. Check the redirect URI in the OAuth configuration form
3. It should now show `https://` instead of `http://`
4. Verify it matches exactly what's registered in ANAF's portal

## Current ANAF Registration

According to your ANAF portal:
- **Callback URL:** `https://anaf.processiq.ro/anaf/callback`
- **Client ID:** `7b043c363ea2619b84c85ea545332edd0c58d20f08551f69`

Make sure the redirect URI in your application matches this exactly.

