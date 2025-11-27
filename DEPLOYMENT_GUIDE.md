# Production Deployment Guide - OAuth Redesign

## 📋 Overview

This guide will help you deploy the latest OAuth redesign changes to your production server.

**What's Changed:**
- OAuth is now system-wide (admin configures once for all users)
- Fixed multiple security issues and bugs
- Added new database migrations
- Improved error handling and user experience

---

## 🗂️ Migration Files to Deploy

All migration files are in `migrations/versions/`:

1. ✅ `7587afddb10d_initial_migration.py` (Base - probably already deployed)
2. ✅ `0dceccd3d798_add_user_admin_approval_fields.py` (Probably already deployed)
3. ✅ `2554acb395ee_increase_password_hash_column_size.py` (Probably already deployed)
4. 🆕 `eb59af9858d8_increase_api_key_hash_column_size.py` (New - fixes API key errors)
5. 🆕 `f3a8b9c5d1e2_increase_client_secret_column_size.py` (New - fixes OAuth secret storage)
6. 🆕 `a9c4d3e2f1b5_convert_oauth_to_system_wide.py` (New - OAuth redesign)

---

## 📦 Step 1: Prepare Deployment Package

### On Your Local Machine:

```bash
# Navigate to your project
cd /Users/csabahitter/Desktop/python/ANAF_eFactura

# Create a deployment package (if using Git)
git add .
git commit -m "OAuth redesign - system-wide configuration"
git push origin main

# OR create a tarball for manual upload
tar -czf anaf_efactura_update.tar.gz \
  app/ \
  migrations/ \
  requirements.txt \
  entrypoint.sh \
  docker-compose.yml \
  Dockerfile
```

---

## 🚀 Step 2: Deploy to Production Server

### Option A: Using Git (Recommended)

```bash
# SSH into your production server
ssh user@your-production-server

# Navigate to application directory
cd /path/to/ANAF_eFactura

# Backup current version
cp -r . ../ANAF_eFactura_backup_$(date +%Y%m%d_%H%M%S)

# Pull latest changes
git pull origin main

# Rebuild Docker containers
docker-compose build

# Stop the application
docker-compose down

# Run migrations
docker-compose up -d db
sleep 10  # Wait for DB to be ready
docker-compose run --rm web flask db upgrade

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f web
```

### Option B: Manual File Upload

```bash
# 1. On your local machine, upload the tarball
scp anaf_efactura_update.tar.gz user@your-production-server:/tmp/

# 2. SSH into production server
ssh user@your-production-server

# 3. Navigate to application directory
cd /path/to/ANAF_eFactura

# 4. Backup current version
sudo cp -r . ../ANAF_eFactura_backup_$(date +%Y%m%d_%H%M%S)

# 5. Extract new files
sudo tar -xzf /tmp/anaf_efactura_update.tar.gz -C .

# 6. Rebuild and restart
sudo docker-compose build
sudo docker-compose down
sudo docker-compose up -d db
sleep 10
sudo docker-compose run --rm web flask db upgrade
sudo docker-compose up -d

# 7. Check logs
sudo docker-compose logs -f web
```

---

## 🔍 Step 3: Verify Database Migrations

### Check Current Migration Version

```bash
# SSH into your production server
ssh user@your-production-server
cd /path/to/ANAF_eFactura

# Check current database version
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "SELECT version_num FROM alembic_version;"
```

**Expected Result:**
```
 version_num  
--------------
 a9c4d3e2f1b5
(1 row)
```

If you see a different version (older), the migrations didn't run. Try:

```bash
# Force migration upgrade
docker-compose run --rm web flask db upgrade

# Or manually run Alembic
docker-compose run --rm web alembic upgrade head
```

### Check Migration History

```bash
docker-compose run --rm web flask db history
```

You should see all 6 migrations listed.

---

## ⚙️ Step 4: Configure OAuth (Admin)

After deployment, **admin users** need to configure OAuth:

1. **Login to Production App:**
   ```
   https://anaf.processiq.ro/auth/login
   ```

2. **Go to OAuth Config:**
   - Click: **Admin → ANAF OAuth Config** (in left sidebar)

3. **Enter ANAF Credentials:**
   - **Client ID**: `84c9275730878042df67bf27ff8a2edd0c58d20fb6292869`
   - **Client Secret**: `4eba53e771cb2e7e84405c88e65ad0e9c02bed1d35922edd0c58d20fb6292869`
   - **Redirect URI**: `https://anaf.processiq.ro/anaf/callback`

4. **Click "Save Configuration"**

---

## 🧪 Step 5: Test the Application

### Test 1: Basic Login
```bash
# Access the app
https://anaf.processiq.ro/auth/login

# Login with your credentials (email/password)
# You should reach the dashboard
```

### Test 2: OAuth Configuration (Admin Only)
```bash
# Go to: Admin → ANAF OAuth Config
# Verify the configuration shows correctly
```

### Test 3: ANAF Connection Diagnostics
```bash
# Go to: https://anaf.processiq.ro/anaf/test
# Run all diagnostic tests
# Share results if issues persist
```

### Test 4: Connect to ANAF (When Ready)
```bash
# From dashboard, click "Connect with ANAF Certificate"
# Should redirect to ANAF for certificate authentication
```

---

## 🔧 Troubleshooting

### Issue 1: Migrations Fail

**Error:** `alembic.util.exc.CommandError: Can't locate revision identified by...`

**Solution:**
```bash
# Check current version
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "SELECT * FROM alembic_version;"

# If empty or wrong, stamp with correct version
docker-compose run --rm web flask db stamp head

# Then upgrade
docker-compose run --rm web flask db upgrade
```

### Issue 2: OAuth Config Not Found After Migration

**Error:** `ANAF OAuth is not configured`

**Solution:**
The migration `a9c4d3e2f1b5` converts per-user OAuth to system-wide. If you had OAuth configs before:

```bash
# Check if config exists
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "SELECT id, client_id, created_by FROM anaf_oauth_configs;"

# If empty, you need to re-enter it via Admin UI
```

### Issue 3: Old OAuth Config References

**Error:** Database errors about `user_id` in `anaf_oauth_configs`

**Solution:**
```bash
# The migration should handle this, but if not:
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "ALTER TABLE anaf_oauth_configs DROP COLUMN IF EXISTS user_id;"
```

### Issue 4: Container Won't Start

**Error:** Docker containers fail to start

**Solution:**
```bash
# Check logs
docker-compose logs web

# Rebuild without cache
docker-compose build --no-cache

# Reset and restart
docker-compose down -v
docker-compose up -d
```

---

## 📊 Verify Deployment Success

Run these checks to ensure everything is working:

### 1. Check Container Status
```bash
docker-compose ps
```
All containers should be "Up".

### 2. Check Database Migration
```bash
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "SELECT version_num FROM alembic_version;"
```
Should show: `a9c4d3e2f1b5`

### 3. Check OAuth Config Table Structure
```bash
docker-compose exec db psql -U efactura_user -d efactura_db -c \
  "\d anaf_oauth_configs"
```
Should **NOT** have `user_id` column, should have `created_by` column.

### 4. Check Application Logs
```bash
docker-compose logs -f web | head -50
```
Should show no errors, "Background scheduler started" messages.

### 5. Access the Application
```bash
# Open in browser
https://anaf.processiq.ro/

# Should load without errors
```

---

## 🔄 Rollback Plan (If Needed)

If something goes wrong, you can rollback:

### Rollback Code
```bash
cd /path/to/ANAF_eFactura
docker-compose down

# Restore backup
rm -rf app migrations
cp -r ../ANAF_eFactura_backup_YYYYMMDD_HHMMSS/* .

docker-compose up -d
```

### Rollback Database
```bash
# Rollback to previous migration
docker-compose run --rm web flask db downgrade -1

# Or rollback to specific version
docker-compose run --rm web flask db downgrade f3a8b9c5d1e2

# Restart
docker-compose restart web
```

---

## ✅ Post-Deployment Checklist

- [ ] All containers are running (`docker-compose ps`)
- [ ] Database migration is at `a9c4d3e2f1b5`
- [ ] Application loads at `https://anaf.processiq.ro/`
- [ ] Can login with email/password
- [ ] Admin can access OAuth config page
- [ ] OAuth credentials are entered and saved
- [ ] No errors in application logs
- [ ] Test page accessible at `/anaf/test`

---

## 📞 Support

If you encounter issues:

1. **Check Logs:**
   ```bash
   docker-compose logs -f web
   docker-compose logs db
   ```

2. **Check Database:**
   ```bash
   docker-compose exec db psql -U efactura_user -d efactura_db
   ```

3. **Review Error Messages:**
   - Note the exact error message
   - Check which migration failed (if any)
   - Share logs for assistance

---

## 📝 Summary of Changes

### Database Changes
- `anaf_oauth_configs` table restructured (per-user → system-wide)
- Increased `api_key.key_hash` column size (128 → 255)
- Increased `anaf_oauth_configs.client_secret` column size (255 → 500)

### Code Changes
- OAuth system redesigned (system-wide configuration)
- Fixed redirect loops
- Fixed HTML entity encoding in OAuth URLs
- Added comprehensive error messages
- Added diagnostic test page
- Improved security and validation

### New Features
- Admin-only OAuth configuration
- Better error handling
- Diagnostic test page at `/anaf/test`
- Improved user experience (no auto-redirects)

---

**Remember:** Access the production app at `https://anaf.processiq.ro` (primary domain) for OAuth to work correctly!

