#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# download_three_vendors.sh
# Descarga los loaders de Three.js r172 que faltan para el previewer
# Ejecutar desde la raíz del proyecto:
#   chmod +x download_three_vendors.sh
#   ./download_three_vendors.sh
# ══════════════════════════════════════════════════════════════════

BASE="https://unpkg.com/three@0.172.0/examples/jsm"
DEST="app/static/vendor/three"
UTILS="app/static/vendor/utils"

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Descargando vendors Three.js r172 para 3D Previewer...${NC}"
echo "Destino: ${DEST}/"
echo ""

# Verificar que existe la carpeta destino
if [ ! -d "$DEST" ]; then
  echo "ERROR: No se encontró la carpeta ${DEST}"
  echo "Asegúrate de ejecutar este script desde la raíz del proyecto."
  exit 1
fi

# Crear carpeta de utils si no existe
mkdir -p "$UTILS"

# Descargar los 3 loaders principales
curl -s -o "${DEST}/GLTFLoader.js"   "${BASE}/loaders/GLTFLoader.js"
echo -e "${GREEN}✓${NC} GLTFLoader.js"

curl -s -o "${DEST}/SVGLoader.js"    "${BASE}/loaders/SVGLoader.js"
echo -e "${GREEN}✓${NC} SVGLoader.js"

curl -s -o "${DEST}/GLTFExporter.js" "${BASE}/exporters/GLTFExporter.js"
echo -e "${GREEN}✓${NC} GLTFExporter.js"

# Descargar dependencia de GLTFLoader (r172+)
curl -s -o "${UTILS}/BufferGeometryUtils.js" "${BASE}/utils/BufferGeometryUtils.js"
echo -e "${GREEN}✓${NC} BufferGeometryUtils.js"

# Parchear imports 'from 'three'' → path local
sed -i "s|from 'three'|from '/static/vendor/three/three.module.js'|g" \
  "${DEST}/GLTFLoader.js" \
  "${DEST}/SVGLoader.js" \
  "${DEST}/GLTFExporter.js" \
  "${UTILS}/BufferGeometryUtils.js"
echo -e "${GREEN}✓${NC} Imports parcheados (from 'three' → local)"

echo ""
echo -e "${GREEN}✓ Listo. Ahora reinicia el servidor y visita /3dpreviewer${NC}"