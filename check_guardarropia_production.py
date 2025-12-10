"""
Script para verificar datos de guardarropía en producción
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from sqlalchemy import text

def check_production_data():
    """Verifica datos en producción"""
    # Si DATABASE_URL ya está configurado (por el script), usarlo
    # Si no, intentar usar la URL de Cloud SQL directa
    if 'DATABASE_URL' not in os.environ:
        # Para conexión local via proxy
        os.environ['DATABASE_URL'] = 'postgresql://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@localhost:5432/bimba'
    
    app = create_app()
    
    with app.app_context():
        try:
            # Verificar si la tabla existe
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"📋 Tablas en la base de datos: {len(tables)}")
            
            if 'guardarropia_items' in tables:
                print("✅ Tabla 'guardarropia_items' existe en producción")
                
                # Contar registros
                result = db.session.execute(text('SELECT COUNT(*) FROM guardarropia_items'))
                count = result.scalar()
                print(f"📊 Total de registros: {count}")
                
                if count > 0:
                    # Mostrar algunos registros
                    result = db.session.execute(text('SELECT ticket_code, customer_name, status, price, deposited_at FROM guardarropia_items ORDER BY deposited_at DESC LIMIT 10'))
                    rows = result.fetchall()
                    
                    print(f"\n📋 Últimos {len(rows)} registros:")
                    for row in rows:
                        print(f"   - {row[0]}: {row[1]} - {row[2]} - ${row[3] or 0} - {row[4]}")
                else:
                    print("⚠️  No hay registros en la tabla")
            else:
                print("❌ Tabla 'guardarropia_items' NO existe en producción")
                print("   Esto significa que la tabla nunca se creó en producción")
            
            return True
            
        except Exception as e:
            print(f"❌ Error al conectar a producción: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("🔍 Verificando datos de guardarropía en producción...")
    print("⚠️  Nota: Esto requiere conexión a Cloud SQL")
    print()
    
    success = check_production_data()
    
    if success:
        print("\n✅ Verificación completada")
    else:
        print("\n❌ Error en la verificación")
        print("   Asegúrate de tener:")
        print("   1. Cloud SQL Proxy ejecutándose")
        print("   2. Permisos de acceso a la base de datos")

