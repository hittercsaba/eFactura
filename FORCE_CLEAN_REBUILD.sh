#!/bin/bash
# Complete clean rebuild - removes ALL cached data

set -e

cd /Users/csabahitter/Desktop/python/ANAF_eFactura

echo "🛑 Stopping ALL containers..."
docker-compose down -v

echo ""
echo "🗑️  Removing web image completely..."
docker rmi anaf_efactura-web 2>/dev/null || echo "Image already removed"

echo ""
echo "🧹 Cleaning Python cache in local directory..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

echo ""
echo "🔨 Building image from scratch (no cache)..."
docker-compose build --no-cache web

echo ""
echo "🚀 Starting containers..."
docker-compose up -d

echo ""
echo "⏳ Waiting 20 seconds for services to start..."
sleep 20

echo ""
echo "✅ DONE!"
echo ""
echo "🔍 Checking if endpoint is correct..."
docker logs anaf_efactura-web-1 2>&1 | grep -A 5 "ANAF API REQUEST" | tail -10 || echo "No API requests yet"

echo ""
echo "📊 Full logs:"
docker logs anaf_efactura-web-1 --tail 30

echo ""
echo "🧪 NOW TEST:"
echo "   1. Open http://localhost:8008/"
echo "   2. Login"
echo "   3. Dashboard → Sync Now"
echo "   4. MUST see: https://webservicesp.anaf.ro NOT api.anaf.ro"
echo ""
echo "📊 Watch logs live:"
echo "   docker logs anaf_efactura-web-1 -f"

