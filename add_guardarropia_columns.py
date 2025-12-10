"""
Script para agregar columnas faltantes a la tabla guardarropia_items
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from sqlalchemy import text

def add_columns():
    """Agrega las columnas faltantes"""
    app = create_app()
    
    with app.app_context():
        try:
            # Verificar columnas existentes
            inspector = db.inspect(db.engine)
            columns = inspector.get_columns('guardarropia_items')
            column_names = [col['name'] for col in columns]
            
            print(f"Columnas actuales: {column_names}")
            
            # Agregar columnas faltantes
            if 'price' not in column_names:
                print("Agregando columna 'price'...")
                db.session.execute(text('ALTER TABLE guardarropia_items ADD COLUMN price NUMERIC(10, 2)'))
                db.session.commit()
                print("✅ Columna 'price' agregada")
            
            if 'payment_type' not in column_names:
                print("Agregando columna 'payment_type'...")
                db.session.execute(text('ALTER TABLE guardarropia_items ADD COLUMN payment_type VARCHAR(20)'))
                db.session.commit()
                print("✅ Columna 'payment_type' agregada")
            
            if 'sale_id' not in column_names:
                print("Agregando columna 'sale_id'...")
                db.session.execute(text('ALTER TABLE guardarropia_items ADD COLUMN sale_id INTEGER'))
                db.session.commit()
                print("✅ Columna 'sale_id' agregada")
            
            # Verificar nuevamente
            columns = inspector.get_columns('guardarropia_items')
            column_names = [col['name'] for col in columns]
            print(f"\n✅ Columnas finales: {column_names}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False

if __name__ == '__main__':
    print("🚀 Agregando columnas faltantes a guardarropia_items...")
    success = add_columns()
    
    if success:
        print("\n✅ Migración completada")
        sys.exit(0)
    else:
        print("\n❌ La migración falló")
        sys.exit(1)




