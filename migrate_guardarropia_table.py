"""
Script de migración para crear la tabla guardarropia_items
Ejecutar con: python migrate_guardarropia_table.py
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.models.guardarropia_models import GuardarropiaItem

def migrate():
    """Crea la tabla guardarropia_items si no existe (sin eliminar datos existentes)"""
    app = create_app()
    
    with app.app_context():
        try:
            from sqlalchemy import inspect, text
            
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            # Si la tabla no existe, crearla
            if 'guardarropia_items' not in tables:
                print("📋 Creando tabla 'guardarropia_items'...")
                # Crear solo esta tabla específica
                GuardarropiaItem.__table__.create(db.engine, checkfirst=True)
                print("✅ Tabla 'guardarropia_items' creada exitosamente")
            else:
                print("✅ Tabla 'guardarropia_items' ya existe")
                
                # Verificar y agregar columnas faltantes sin perder datos
                columns = inspector.get_columns('guardarropia_items')
                column_names = [col['name'] for col in columns]
                
                # Agregar columnas faltantes si no existen
                if 'price' not in column_names:
                    print("➕ Agregando columna 'price'...")
                    db.session.execute(text('ALTER TABLE guardarropia_items ADD COLUMN price NUMERIC(10, 2)'))
                    db.session.commit()
                    print("✅ Columna 'price' agregada")
                
                if 'payment_type' not in column_names:
                    print("➕ Agregando columna 'payment_type'...")
                    db.session.execute(text('ALTER TABLE guardarropia_items ADD COLUMN payment_type VARCHAR(20)'))
                    db.session.commit()
                    print("✅ Columna 'payment_type' agregada")
                
                if 'sale_id' not in column_names:
                    print("➕ Agregando columna 'sale_id'...")
                    db.session.execute(text('ALTER TABLE guardarropia_items ADD COLUMN sale_id INTEGER'))
                    db.session.commit()
                    print("✅ Columna 'sale_id' agregada")
            
            # Verificar estructura final
            columns = inspector.get_columns('guardarropia_items')
            print("\n📋 Estructura final de la tabla:")
            for col in columns:
                print(f"   - {col['name']}: {col['type']}")
            
            # Contar registros existentes
            result = db.session.execute(text('SELECT COUNT(*) FROM guardarropia_items'))
            count = result.scalar()
            print(f"\n📊 Registros en la tabla: {count}")
            
            return True
                
        except Exception as e:
            print(f"❌ Error al crear/actualizar la tabla: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False

if __name__ == '__main__':
    print("🚀 Iniciando migración de tabla guardarropia_items...")
    success = migrate()
    
    if success:
        print("\n✅ Migración completada exitosamente")
        sys.exit(0)
    else:
        print("\n❌ La migración falló")
        sys.exit(1)

