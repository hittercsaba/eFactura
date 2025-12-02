#!/bin/bash
# Force complete rebuild to clear Docker cache

set -e  # Exit on error

cd /Users/csabahitter/Desktop/python/ANAF_eFactura

echo "🛑 Stopping containers..."
docker-compose down

echo ""
echo "🗑️  Removing old web image to force rebuild..."
docker rmi anaf_efactura-web 2>/dev/null || true

echo ""
echo "🔨 Building with --no-cache (this will take 2-3 minutes)..."
docker-compose build --no-cache web

echo ""
echo "🚀 Starting containers..."
docker-compose up -d

echo ""
echo "⏳ Waiting 20 seconds for services to initialize..."
sleep 20

echo ""
echo "✅ DONE! Application is ready."
echo ""
echo "📊 Watch logs:"
echo "   docker logs anaf_efactura-web-1 -f"
echo ""
echo "🌐 Open browser:"
echo "   http://localhost:8008/"
echo ""
echo "🧪 Test sync:"
echo "   1. Login"
echo "   2. Dashboard → Click 'Sync Now' button"
echo "   3. Watch logs - should see https://webservicesp.anaf.ro NOT api.anaf.ro"
echo ""
echo "✨ Look for this in logs:"
echo "   INFO in anaf_service: URL: https://webservicesp.anaf.ro/prod/FCTEL/rest/listaMesajeFactura"
echo ""

