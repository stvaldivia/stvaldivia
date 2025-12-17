#!/bin/bash
# Script de deploy para servidor VM
# Uso: ./deploy_vm.sh

set -e  # Salir si algún comando falla

# Variables (edita si tu vhost apunta a otra carpeta)
REPO_URL="https://github.com/stvaldivia/stvaldivia.git"
WEBROOT="/var/www/stvaldivia"
BACKUP_BASE="/tmp/stvaldivia_backup"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "🚀 DEPLOY STVALDIVIA - VM"
echo "=========================================="
echo ""

# 1) Ver qué hay hoy en /var/www/stvaldivia (por si NO quieres borrarlo)
echo "📋 1) Verificando contenido actual de $WEBROOT..."
if [ -d "$WEBROOT" ] && [ "$(ls -A $WEBROOT 2>/dev/null)" ]; then
    echo -e "${YELLOW}⚠️  Contenido encontrado en $WEBROOT:${NC}"
    sudo ls -la "$WEBROOT" | head -10
    echo ""
    read -p "¿Continuar con backup y deploy? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Deploy cancelado por el usuario"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Carpeta vacía o no existe${NC}"
fi

# 2) Crear backup del contenido actual (si existe)
TS=$(date +%Y%m%d_%H%M%S)
BACKUP="${BACKUP_BASE}_${TS}"

if [ -d "$WEBROOT" ] && [ "$(ls -A $WEBROOT 2>/dev/null)" ]; then
    echo ""
    echo "💾 2) Creando backup en $BACKUP..."
    sudo mkdir -p "$(dirname $BACKUP)"
    sudo mv "$WEBROOT" "$BACKUP"
    echo -e "${GREEN}✅ Backup creado: $BACKUP${NC}"
else
    echo ""
    echo "💾 2) No hay contenido previo para hacer backup"
    BACKUP=""  # No hay backup disponible
fi

# 3) Crear carpeta webroot limpia
echo ""
echo "📁 3) Creando carpeta webroot limpia..."
sudo mkdir -p "$WEBROOT"
sudo chown -R "$USER":"$USER" "$WEBROOT"
echo -e "${GREEN}✅ Carpeta creada y permisos configurados${NC}"

# 4) Clonar repo
echo ""
echo "📥 4) Clonando repo desde GitHub..."
git clone "$REPO_URL" "$WEBROOT"
echo -e "${GREEN}✅ Repo clonado${NC}"

# 5) Verificar clone
echo ""
echo "🔍 5) Verificando clone..."
cd "$WEBROOT"
echo "Estado del repo:"
git status --short
echo ""
echo "Último commit:"
git log -1 --oneline
echo -e "${GREEN}✅ Verificación completada${NC}"

# 6) Copiar .env desde backup (si existe)
echo ""
echo "⚙️  6) Copiando .env desde backup..."
if [ -n "$BACKUP" ] && [ -f "$BACKUP/.env" ]; then
    cp "$BACKUP/.env" "$WEBROOT/.env"
    echo -e "${GREEN}✅ .env copiado desde backup${NC}"
elif [ -f "$WEBROOT/.env.example" ]; then
    echo -e "${YELLOW}⚠️  No hay .env en backup, pero existe .env.example${NC}"
    echo "   Recuerda configurar .env manualmente"
else
    echo -e "${YELLOW}⚠️  WARNING: no encontré .env en el backup${NC}"
    echo "   Asegúrate de configurar .env manualmente antes de iniciar la app"
fi

# 6.5) Backup de base de datos (antes de cualquier cambio)
echo ""
echo "💾 6.5) Haciendo backup de base de datos..."
if [ -f "$WEBROOT/.env" ]; then
    # Cargar variables de entorno
    export $(grep -v '^#' "$WEBROOT/.env" | grep DATABASE_URL | xargs)
    
    if [ -n "$DATABASE_URL" ]; then
        DB_BACKUP_FILE="/tmp/stvaldivia_db_backup_${TS}.sql"
        
        # Extraer datos de conexión de DATABASE_URL (formato: postgresql://user:pass@host:port/dbname)
        if [[ $DATABASE_URL =~ postgresql://([^:]+):([^@]+)@([^:]+):([^/]+)/(.+) ]]; then
            DB_USER="${BASH_REMATCH[1]}"
            DB_PASS="${BASH_REMATCH[2]}"
            DB_HOST="${BASH_REMATCH[3]}"
            DB_PORT="${BASH_REMATCH[4]}"
            DB_NAME="${BASH_REMATCH[5]}"
            
            # Hacer backup con pg_dump
            if command -v pg_dump &>/dev/null; then
                export PGPASSWORD="$DB_PASS"
                pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F c -f "$DB_BACKUP_FILE" 2>/dev/null && \
                    echo -e "${GREEN}✅ Backup de BD creado: $DB_BACKUP_FILE${NC}" || \
                    echo -e "${YELLOW}⚠️  No se pudo hacer backup de BD (puede que no esté disponible pg_dump)${NC}"
                unset PGPASSWORD
            else
                echo -e "${YELLOW}⚠️  pg_dump no está instalado, saltando backup de BD${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  DATABASE_URL no tiene formato PostgreSQL estándar, saltando backup${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  DATABASE_URL no encontrado en .env${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No hay .env, saltando backup de BD${NC}"
fi

# 7) Copiar uploads / assets locales (si existen)
echo ""
echo "📦 7) Copiando uploads/assets locales..."
if [ -n "$BACKUP" ] && [ -d "$BACKUP/static/uploads" ]; then
    mkdir -p "$WEBROOT/static"
    cp -R "$BACKUP/static/uploads" "$WEBROOT/static/"
    echo -e "${GREEN}✅ Uploads copiados${NC}"
elif [ -n "$BACKUP" ] && [ -d "$BACKUP/instance" ]; then
    # Si hay carpeta instance con datos locales
    mkdir -p "$WEBROOT/instance"
    cp -R "$BACKUP/instance"/* "$WEBROOT/instance/" 2>/dev/null || true
    echo -e "${GREEN}✅ Instance copiado${NC}"
else
    echo "ℹ️  No hay uploads/assets locales para copiar"
fi

# 8) Instalar dependencias (si hay requirements.txt)
echo ""
echo "📦 8) Instalando dependencias..."
if [ -f "$WEBROOT/requirements.txt" ]; then
    cd "$WEBROOT"
    if [ -d "venv" ]; then
        echo "Activando venv existente..."
        source venv/bin/activate
    else
        echo "Creando venv..."
        python3 -m venv venv
        source venv/bin/activate
    fi
    pip install --upgrade pip
    pip install -r requirements.txt
    echo -e "${GREEN}✅ Dependencias instaladas${NC}"
else
    echo "ℹ️  No se encontró requirements.txt"
fi

# 8.5) Ejecutar migraciones de base de datos
echo ""
echo "🗄️  8.5) Ejecutando migraciones de base de datos..."
cd "$WEBROOT"

# Activar venv si existe
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Verificar que .env existe y tiene DATABASE_URL
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | grep DATABASE_URL | xargs)
    
    if [ -n "$DATABASE_URL" ]; then
        # Intentar ejecutar migraciones con Flask-Migrate o directamente con psql
        if [ -d "migrations" ]; then
            echo "Ejecutando migraciones Flask-Migrate..."
            flask db upgrade 2>/dev/null && \
                echo -e "${GREEN}✅ Migraciones Flask-Migrate ejecutadas${NC}" || \
                echo -e "${YELLOW}⚠️  No se pudieron ejecutar migraciones Flask-Migrate (puede que no esté configurado)${NC}"
        fi
        
        # Ejecutar migraciones SQL directas si existen
        if [ -d "migrations" ]; then
            echo "Buscando migraciones SQL..."
            SQL_MIGRATIONS=$(find migrations -name "*.sql" -type f | sort)
            if [ -n "$SQL_MIGRATIONS" ]; then
                # Extraer datos de conexión
                if [[ $DATABASE_URL =~ postgresql://([^:]+):([^@]+)@([^:]+):([^/]+)/(.+) ]]; then
                    DB_USER="${BASH_REMATCH[1]}"
                    DB_PASS="${BASH_REMATCH[2]}"
                    DB_HOST="${BASH_REMATCH[3]}"
                    DB_PORT="${BASH_REMATCH[4]}"
                    DB_NAME="${BASH_REMATCH[5]}"
                    
                    if command -v psql &>/dev/null; then
                        export PGPASSWORD="$DB_PASS"
                        for migration in $SQL_MIGRATIONS; do
                            echo "  Ejecutando: $migration"
                            psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration" 2>/dev/null || \
                                echo -e "  ${YELLOW}⚠️  Migración $migration puede haber fallado o ya estar aplicada${NC}"
                        done
                        unset PGPASSWORD
                        echo -e "${GREEN}✅ Migraciones SQL ejecutadas${NC}"
                    else
                        echo -e "${YELLOW}⚠️  psql no está instalado, saltando migraciones SQL${NC}"
                    fi
                fi
            fi
        fi
        
        # Verificar conexión a la base de datos
        echo "Verificando conexión a la base de datos..."
        python3 -c "
import os
import sys
sys.path.insert(0, '$WEBROOT')
from dotenv import load_dotenv
load_dotenv('$WEBROOT/.env')
from app import create_app
app = create_app()
with app.app_context():
    from app.models import db
    try:
        db.engine.execute('SELECT 1')
        print('✅ Conexión a BD exitosa')
    except Exception as e:
        print(f'❌ Error de conexión: {e}')
        sys.exit(1)
" 2>/dev/null && echo -e "${GREEN}✅ Base de datos verificada${NC}" || \
            echo -e "${YELLOW}⚠️  No se pudo verificar la BD (puede requerir configuración manual)${NC}"
        
        # Verificar y crear cajas si no existen
        echo ""
        echo "🏪 Verificando cajas en la base de datos..."
        python3 "$WEBROOT/scripts/verify_and_seed_cajas.py" 2>/dev/null && \
            echo -e "${GREEN}✅ Cajas verificadas/creadas${NC}" || \
            echo -e "${YELLOW}⚠️  No se pudieron verificar/crear cajas (revisar logs)${NC}"
    else
        echo -e "${YELLOW}⚠️  DATABASE_URL no encontrado en .env${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No hay .env, saltando migraciones${NC}"
fi

# 9) Reiniciar servicios
echo ""
echo "🔄 9) Reiniciando servicios..."
if systemctl is-active --quiet gunicorn 2>/dev/null; then
    sudo systemctl restart gunicorn
    echo -e "${GREEN}✅ gunicorn reiniciado${NC}"
else
    echo -e "${YELLOW}⚠️  gunicorn no está activo o no existe${NC}"
fi

if systemctl is-active --quiet nginx 2>/dev/null; then
    sudo systemctl restart nginx
    echo -e "${GREEN}✅ nginx reiniciado${NC}"
else
    echo -e "${YELLOW}⚠️  nginx no está activo o no existe${NC}"
fi

# 10) Verificar logs
echo ""
echo "📋 10) Verificando logs de gunicorn..."
if systemctl is-active --quiet gunicorn 2>/dev/null; then
    echo "Últimas 30 líneas de logs:"
    sudo journalctl -u gunicorn -n 30 --no-pager || true
    echo ""
    echo "Estado del servicio:"
    sudo systemctl status gunicorn --no-pager -l || true
else
    echo -e "${YELLOW}⚠️  gunicorn no está activo, no se pueden ver logs${NC}"
fi

# Resumen final
echo ""
echo "=========================================="
echo -e "${GREEN}✅ DEPLOY COMPLETADO${NC}"
echo "=========================================="
echo "Webroot: $WEBROOT"
if [ -n "$BACKUP" ]; then
    echo "Backup: $BACKUP"
fi
echo ""
echo "Próximos pasos:"
echo "1. Verificar que .env esté configurado correctamente"
echo "2. Verificar que las migraciones se ejecutaron: revisar logs arriba"
echo "3. Verificar logs: sudo journalctl -u gunicorn -f"
echo "4. Verificar que nginx esté sirviendo: sudo systemctl status nginx"
if [ -n "$DB_BACKUP_FILE" ] && [ -f "$DB_BACKUP_FILE" ]; then
    echo "5. Backup de BD guardado en: $DB_BACKUP_FILE"
fi
echo ""
