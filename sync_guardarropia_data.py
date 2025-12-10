"""
Script para sincronizar datos de guardarropía desde producción a local
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
import sqlite3

def sync_data():
    """Sincroniza datos desde PostgreSQL (producción) a SQLite (local)"""
    
    # Conectar a producción (PostgreSQL via proxy)
    prod_url = "postgresql://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@localhost:5432/bimba"
    prod_engine = create_engine(prod_url)
    
    # Conectar a local (SQLite)
    local_db = "instance/bimba.db"
    local_conn = sqlite3.connect(local_db)
    local_cursor = local_conn.cursor()
    
    try:
        print("🔍 Verificando datos en producción...")
        
        with prod_engine.connect() as prod_conn:
            # Contar registros en producción
            result = prod_conn.execute(text('SELECT COUNT(*) FROM guardarropia_items'))
            prod_count = result.scalar()
            
            print(f"📊 Registros en producción: {prod_count}")
            
            if prod_count == 0:
                print("⚠️  No hay datos en producción para sincronizar")
                return
            
            # Obtener todos los registros de producción
            result = prod_conn.execute(text('''
                SELECT 
                    id, ticket_code, description, customer_name, customer_phone,
                    status, deposited_at, retrieved_at, deposited_by, retrieved_by,
                    shift_date, price, payment_type, sale_id, notes,
                    created_at, updated_at
                FROM guardarropia_items
                ORDER BY id
            '''))
            
            rows = result.fetchall()
            print(f"📦 Obtenidos {len(rows)} registros de producción")
            
            # Contar registros en local
            local_cursor.execute('SELECT COUNT(*) FROM guardarropia_items')
            local_count = local_cursor.fetchone()[0]
            print(f"📊 Registros en local antes: {local_count}")
            
            # Insertar o actualizar en local
            inserted = 0
            updated = 0
            
            for row in rows:
                # Verificar si existe
                local_cursor.execute('SELECT id FROM guardarropia_items WHERE id = ?', (row[0],))
                exists = local_cursor.fetchone()
                
                if exists:
                    # Actualizar
                    local_cursor.execute('''
                        UPDATE guardarropia_items SET
                            ticket_code = ?, description = ?, customer_name = ?, customer_phone = ?,
                            status = ?, deposited_at = ?, retrieved_at = ?, deposited_by = ?, retrieved_by = ?,
                            shift_date = ?, price = ?, payment_type = ?, sale_id = ?, notes = ?,
                            created_at = ?, updated_at = ?
                        WHERE id = ?
                    ''', row[1:] + (row[0],))
                    updated += 1
                else:
                    # Insertar
                    local_cursor.execute('''
                        INSERT INTO guardarropia_items (
                            id, ticket_code, description, customer_name, customer_phone,
                            status, deposited_at, retrieved_at, deposited_by, retrieved_by,
                            shift_date, price, payment_type, sale_id, notes,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', row)
                    inserted += 1
            
            local_conn.commit()
            
            # Contar registros después
            local_cursor.execute('SELECT COUNT(*) FROM guardarropia_items')
            local_count_after = local_cursor.fetchone()[0]
            
            print(f"\n✅ Sincronización completada:")
            print(f"   - Insertados: {inserted}")
            print(f"   - Actualizados: {updated}")
            print(f"   - Total en local ahora: {local_count_after}")
            
            if inserted > 0 or updated > 0:
                print("\n🎉 ¡Datos sincronizados exitosamente!")
            else:
                print("\n⚠️  No se realizaron cambios (datos ya estaban sincronizados)")
                
    except Exception as e:
        print(f"❌ Error al sincronizar: {e}")
        import traceback
        traceback.print_exc()
        local_conn.rollback()
    finally:
        local_conn.close()
        prod_engine.dispose()

if __name__ == '__main__':
    print("🚀 Iniciando sincronización de guardarropía...")
    print("")
    sync_data()




