#!/bin/bash

##############################################################################
# Script de Backup Completo del Sistema BIMBA
# Este script crea un backup completo del sitio incluyendo:
# - Todo el código fuente
# - Bases de datos
# - Configuraciones (sin datos sensibles)
# - Documentación
##############################################################################

set -e  # Salir si hay algún error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directorio base del proyecto
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Timestamp para el backup
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="backups"
BACKUP_NAME="bimba_backup_completo_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🔄 INICIANDO BACKUP COMPLETO DEL SISTEMA BIMBA${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# Crear directorio de backup
mkdir -p "$BACKUP_PATH"
echo -e "${GREEN}✅ Directorio de backup creado: ${BACKUP_PATH}${NC}"

# =============================================================================
# 1. BACKUP DE CÓDIGO FUENTE
# =============================================================================
echo -e "\n${YELLOW}📦 Copiando código fuente...${NC}"

# Crear directorio para código
mkdir -p "$BACKUP_PATH/codigo"

# Copiar todo el código, excluyendo archivos innecesarios
rsync -av --progress \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.git/' \
    --exclude='node_modules/' \
    --exclude='*.log' \
    --exclude='*.db' \
    --exclude='backups/' \
    --exclude='.env' \
    --exclude='*.swp' \
    --exclude='*.swo' \
    --exclude='.DS_Store' \
    --exclude='.vscode/' \
    --exclude='.idea/' \
    . "$BACKUP_PATH/codigo/" 2>&1 | grep -E "^(sending|sent|total)" || true

echo -e "${GREEN}✅ Código fuente copiado${NC}"

# =============================================================================
# 2. BACKUP DE BASES DE DATOS
# =============================================================================
echo -e "\n${YELLOW}💾 Copiando bases de datos...${NC}"

mkdir -p "$BACKUP_PATH/bases_datos"

# Copiar bases de datos principales
if [ -f "instance/bimba.db" ]; then
    cp "instance/bimba.db" "$BACKUP_PATH/bases_datos/bimba.db"
    echo -e "${GREEN}✅ bimba.db copiada${NC}"
else
    echo -e "${YELLOW}⚠️  No se encontró instance/bimba.db${NC}"
fi

if [ -f "instance/bimba_kiosk.db" ]; then
    cp "instance/bimba_kiosk.db" "$BACKUP_PATH/bases_datos/bimba_kiosk.db"
    echo -e "${GREEN}✅ bimba_kiosk.db copiada${NC}"
else
    echo -e "${YELLOW}⚠️  No se encontró instance/bimba_kiosk.db${NC}"
fi

# Copiar otras bases de datos si existen
for db_file in instance/*.db; do
    if [ -f "$db_file" ]; then
        filename=$(basename "$db_file")
        if [ "$filename" != "bimba.db" ] && [ "$filename" != "bimba_kiosk.db" ]; then
            cp "$db_file" "$BACKUP_PATH/bases_datos/$filename"
            echo -e "${GREEN}✅ $filename copiada${NC}"
        fi
    fi
done

# =============================================================================
# 3. BACKUP DE CONFIGURACIONES
# =============================================================================
echo -e "\n${YELLOW}⚙️  Copiando configuraciones...${NC}"

mkdir -p "$BACKUP_PATH/configuracion"

# Crear archivo de configuración de ejemplo (sin datos sensibles)
if [ -f ".env" ]; then
    # Crear copia sin valores sensibles
    grep -v -E "(PASSWORD|SECRET|KEY|TOKEN|API_KEY)" .env > "$BACKUP_PATH/configuracion/.env.example" 2>/dev/null || true
    echo -e "${GREEN}✅ .env.example creado (sin datos sensibles)${NC}"
fi

# Copiar requirements.txt
if [ -f "requirements.txt" ]; then
    cp "requirements.txt" "$BACKUP_PATH/configuracion/"
    echo -e "${GREEN}✅ requirements.txt copiado${NC}"
fi

# =============================================================================
# 4. INFORMACIÓN DEL SISTEMA
# =============================================================================
echo -e "\n${YELLOW}📋 Generando información del sistema...${NC}"

INFO_FILE="$BACKUP_PATH/INFORMACION_BACKUP.txt"
cat > "$INFO_FILE" << EOF
═══════════════════════════════════════════════════════════════════════════
BACKUP COMPLETO DEL SISTEMA BIMBA
═══════════════════════════════════════════════════════════════════════════

Fecha y Hora: $(date '+%Y-%m-%d %H:%M:%S')
Directorio de Backup: $BACKUP_PATH

═══════════════════════════════════════════════════════════════════════════
CONTENIDO DEL BACKUP
═══════════════════════════════════════════════════════════════════════════

1. CÓDIGO FUENTE
   - Todo el código de la aplicación
   - Templates HTML
   - Archivos estáticos (CSS, JS, imágenes)
   - Scripts de utilidad
   - Excluye: venv, __pycache__, .git, node_modules

2. BASES DE DATOS
EOF

# Agregar información de bases de datos
for db_file in "$BACKUP_PATH/bases_datos"/*.db; do
    if [ -f "$db_file" ]; then
        filename=$(basename "$db_file")
        size=$(du -h "$db_file" | cut -f1)
        echo "   - $filename ($size)" >> "$INFO_FILE"
    fi
done

cat >> "$INFO_FILE" << EOF

3. CONFIGURACIONES
   - requirements.txt (dependencias Python)
   - .env.example (configuración sin datos sensibles)

═══════════════════════════════════════════════════════════════════════════
INFORMACIÓN DEL SISTEMA
═══════════════════════════════════════════════════════════════════════════

Sistema Operativo: $(uname -s) $(uname -r)
Python: $(python3 --version 2>/dev/null || echo "No disponible")
Ubicación del Proyecto: $PROJECT_ROOT

═══════════════════════════════════════════════════════════════════════════
INSTRUCCIONES DE RESTAURACIÓN
═══════════════════════════════════════════════════════════════════════════

1. Extraer el archivo comprimido:
   tar -xzf ${BACKUP_NAME}.tar.gz

2. Restaurar código fuente:
   Copiar el contenido de codigo/ al directorio del proyecto

3. Restaurar bases de datos:
   cp bases_datos/*.db instance/

4. Restaurar configuraciones:
   - Revisar .env.example y crear .env con tus valores
   - Instalar dependencias: pip install -r requirements.txt

5. Verificar permisos:
   chmod +x scripts/*.sh

═══════════════════════════════════════════════════════════════════════════
EOF

echo -e "${GREEN}✅ Información del backup generada${NC}"

# =============================================================================
# 5. COMPRIMIR BACKUP
# =============================================================================
echo -e "\n${YELLOW}🗜️  Comprimiendo backup...${NC}"

cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME" 2>&1 | grep -v "Removing leading" || true

# Calcular tamaño del archivo comprimido
COMPRESSED_SIZE=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
echo -e "${GREEN}✅ Backup comprimido: ${BACKUP_NAME}.tar.gz ($COMPRESSED_SIZE)${NC}"

# Volver al directorio del proyecto
cd "$PROJECT_ROOT"

# Calcular tamaño del directorio sin comprimir
UNCOMPRESSED_SIZE=$(du -sh "$BACKUP_PATH" | cut -f1)
echo -e "${BLUE}   Tamaño sin comprimir: $UNCOMPRESSED_SIZE${NC}"

# =============================================================================
# 6. RESUMEN FINAL
# =============================================================================
echo -e "\n${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ BACKUP COMPLETO FINALIZADO${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}📦 Archivo de backup:${NC}"
echo -e "   ${YELLOW}${BACKUP_DIR}/${BACKUP_NAME}.tar.gz${NC}"
echo ""
echo -e "${GREEN}📁 Directorio del backup:${NC}"
echo -e "   ${YELLOW}${BACKUP_PATH}${NC}"
echo ""
echo -e "${GREEN}📊 Tamaño:${NC}"
echo -e "   Comprimido: ${YELLOW}$COMPRESSED_SIZE${NC}"
echo -e "   Sin comprimir: ${YELLOW}$UNCOMPRESSED_SIZE${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"

# Opcional: Eliminar directorio sin comprimir para ahorrar espacio
read -p "¿Deseas eliminar el directorio sin comprimir para ahorrar espacio? (s/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    rm -rf "$BACKUP_PATH"
    echo -e "${GREEN}✅ Directorio sin comprimir eliminado${NC}"
else
    echo -e "${YELLOW}⚠️  Directorio sin comprimir conservado en: ${BACKUP_PATH}${NC}"
fi

echo -e "\n${GREEN}🎉 Backup completado exitosamente!${NC}"

