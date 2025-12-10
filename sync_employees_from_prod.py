"""
Script para sincronizar empleados desde producción a local
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
import sqlite3

def sync_employees():
    """Sincroniza empleados desde PostgreSQL (producción) a SQLite (local)"""
    
    # Conectar a producción (PostgreSQL via proxy)
    prod_url = "postgresql://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@localhost:5432/bimba"
    prod_engine = create_engine(prod_url)
    
    # Conectar a local (SQLite)
    local_db = "instance/bimba.db"
    local_conn = sqlite3.connect(local_db)
    local_cursor = local_conn.cursor()
    
    try:
        print("🔍 Sincronizando empleados desde producción...")
        
        with prod_engine.connect() as prod_conn:
            # Obtener todos los empleados activos de producción
            result = prod_conn.execute(text('''
                SELECT id, name, cargo, pin, is_active, is_bartender, is_cashier,
                       created_at, updated_at
                FROM employees
                WHERE is_active = true
                ORDER BY name
            '''))
            
            rows = result.fetchall()
            print(f"📦 Empleados en producción: {len(rows)}")
            
            if len(rows) == 0:
                print("⚠️  No hay empleados en producción")
                return
            
            # Mostrar empleados que se van a sincronizar
            print("\n👥 Empleados a sincronizar:")
            for row in rows:
                print(f"   - {row[1]}: {row[2]}")
            
            # Insertar o actualizar en local
            inserted = 0
            updated = 0
            
            for row in rows:
                # Verificar si existe
                local_cursor.execute('SELECT id FROM employees WHERE id = ?', (row[0],))
                exists = local_cursor.fetchone()
                
                if exists:
                    # Actualizar
                    local_cursor.execute('''
                        UPDATE employees SET
                            name = ?, cargo = ?, pin = ?, is_active = ?,
                            is_bartender = ?, is_cashier = ?,
                            created_at = ?, updated_at = ?
                        WHERE id = ?
                    ''', row[1:8] + (row[0],))
                    updated += 1
                else:
                    # Insertar
                    local_cursor.execute('''
                        INSERT INTO employees (
                            id, name, cargo, pin, is_active,
                            is_bartender, is_cashier,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', row)
                    inserted += 1
            
            local_conn.commit()
            
            print(f"\n✅ Sincronización completada:")
            print(f"   - Insertados: {inserted}")
            print(f"   - Actualizados: {updated}")
            print(f"   - Total: {inserted + updated} empleados")
            
            if inserted > 0 or updated > 0:
                print("\n🎉 ¡Empleados sincronizados exitosamente!")
            else:
                print("\n⚠️  No se realizaron cambios (empleados ya estaban sincronizados)")
                
    except Exception as e:
        print(f"❌ Error al sincronizar: {e}")
        import traceback
        traceback.print_exc()
        local_conn.rollback()
    finally:
        local_conn.close()
        prod_engine.dispose()

if __name__ == '__main__':
    sync_employees()




