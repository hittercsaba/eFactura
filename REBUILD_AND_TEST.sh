#!/bin/bash
# Rebuild and restart to clear Python cache

cd /Users/csabahitter/Desktop/python/ANAF_eFactura

echo "🧹 Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo "🔨 Rebuilding Docker containers..."
docker-compose build web

echo "🔄 Restarting containers..."
docker-compose down
docker-compose up -d

echo "⏳ Waiting for services to start..."
sleep 15

echo "✅ Done! Now test sync."
echo ""
echo "📊 Watch logs with:"
echo "   docker logs anaf_efactura-web-1 -f"
echo ""
echo "🌐 Access app at:"
echo "   http://localhost:8008/"
echo ""
echo "Then click: Dashboard → Sync Invoices"

