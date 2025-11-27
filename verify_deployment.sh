#!/bin/bash

echo "===================================================="
echo "Production Deployment Verification Script"
echo "===================================================="
echo ""

echo "1. Checking if admin_config.html exists locally..."
if [ -f "app/templates/anaf/admin_config.html" ]; then
    echo "   ✅ admin_config.html EXISTS locally"
else
    echo "   ❌ admin_config.html NOT FOUND locally"
fi

echo ""
echo "2. Checking if file is tracked in Git..."
git ls-files app/templates/anaf/admin_config.html | grep -q admin_config && echo "   ✅ admin_config.html is TRACKED in Git" || echo "   ❌ admin_config.html is NOT tracked in Git"

echo ""
echo "3. Checking admin route in anaf.py..."
grep -q "def admin_config" app/routes/anaf.py && echo "   ✅ admin_config route EXISTS" || echo "   ❌ admin_config route NOT FOUND"

echo ""
echo "4. Checking models.py OAuth changes..."
grep -q "created_by" app/models.py && echo "   ✅ System-wide OAuth model EXISTS" || echo "   ❌ Old per-user OAuth model STILL IN USE"

echo ""
echo "5. Checking latest migration..."
LATEST_MIG=$(ls -1 migrations/versions/*.py | tail -1 | xargs basename)
echo "   Latest migration: $LATEST_MIG"
if [[ "$LATEST_MIG" == "a9c4d3e2f1b5_convert_oauth_to_system_wide.py" ]]; then
    echo "   ✅ Correct migration present"
else
    echo "   ⚠️  Expected: a9c4d3e2f1b5_convert_oauth_to_system_wide.py"
fi

echo ""
echo "6. Recent Git commits..."
git log --oneline -3

echo ""
echo "===================================================="
echo "PRODUCTION DEPLOYMENT STEPS:"
echo "===================================================="
echo "If all checks above pass, run these on your production server:"
echo ""
echo "ssh user@your-server"
echo "cd /path/to/ANAF_eFactura"
echo "git pull origin main"
echo "docker-compose build"
echo "docker-compose down"
echo "docker-compose up -d db"
echo "sleep 10"
echo "docker-compose run --rm web flask db upgrade"
echo "docker-compose up -d"
echo "docker-compose logs -f web"
echo ""
echo "Then access: https://anaf.processiq.ro/auth/login"
echo "Admin menu should show: Admin → ANAF OAuth Config"
echo "===================================================="

