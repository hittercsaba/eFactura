#!/bin/bash

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "================================================================================"
echo "  🔍 DIAGNOSTIC AUTOMAT ANAF e-Factura OAuth2"
echo "================================================================================"
echo ""

# Check if Docker is running
if ! docker ps &> /dev/null; then
    echo -e "${RED}❌ Docker nu rulează sau nu ai permisiuni!${NC}"
    exit 1
fi

# Check if container is running
if ! docker ps | grep -q "anaf_efactura-web-1"; then
    echo -e "${RED}❌ Container-ul anaf_efactura-web-1 nu rulează!${NC}"
    echo -e "${YELLOW}Pornește aplicația cu: docker-compose up -d${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker și container-ul rulează${NC}"
echo ""

# Run diagnostic script
echo "================================================================================"
echo "  📊 RULARE DIAGNOSTIC..."
echo "================================================================================"
echo ""

docker exec anaf_efactura-web-1 python /app/diagnostic_anaf.py

DIAGNOSTIC_EXIT=$?

echo ""
echo "================================================================================"
echo "  📋 REZUMAT"
echo "================================================================================"
echo ""

if [ $DIAGNOSTIC_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ TOATE VERIFICĂRILE AU TRECUT!${NC}"
    echo ""
    echo "Sistemul funcționează corect. Poți sincroniza facturi din dashboard."
    echo ""
else
    echo -e "${RED}❌ AU FOST DETECTATE PROBLEME!${NC}"
    echo ""
    echo -e "${YELLOW}📝 Consultă fișierele pentru soluții detaliate:${NC}"
    echo ""
    echo "   1. REZUMAT_DIAGNOSTIC.md - Rezumat complet cu cauze și soluții"
    echo "   2. VERIFICARE_PORTAL_ANAF.md - Pași de verificare în portal ANAF"
    echo ""
    echo -e "${YELLOW}🎯 ACȚIUNE IMEDIATĂ:${NC}"
    echo ""
    echo "   1. Verifică portal ANAF: https://www.anaf.ro/InregOauth"
    echo "      • Aplicația TREBUIE să fie pentru serviciul 'E-Factura'"
    echo "      • Verifică că Client ID este corect"
    echo ""
    echo "   2. Verifică SPV: https://www.anaf.ro/SpvInfoWebService/"
    echo "      • Certificatul TREBUIE să aibă access la CIF 51331025"
    echo "      • Poți vedea facturi manual în SPV?"
    echo ""
    echo "   3. Dacă aplicația NU este pentru 'E-Factura':"
    echo "      • Recrează aplicația cu serviciul 'E-Factura'"
    echo "      • Actualizează Client ID/Secret în: http://localhost:8008/admin/anaf-oauth"
    echo "      • Re-autentifică din: http://localhost:8008/anaf/status"
    echo ""
    echo -e "${BLUE}📖 Pentru detalii complete, citește: REZUMAT_DIAGNOSTIC.md${NC}"
    echo ""
fi

echo "================================================================================"
echo ""

exit $DIAGNOSTIC_EXIT
