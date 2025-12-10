"""
Script completo para sincronizar TODOS los datos desde producción a local
Mantiene la base de datos local actualizada con producción
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
import sqlite3

# Tablas a sincronizar (en orden de dependencias)
TABLES_TO_SYNC = [
    {
        'name': 'employees',
        'description': 'Empleados',
        'icon': '👥',
        'order_by': 'name',
        'where': 'is_active = true'
    },
    {
        'name': 'cargos',
        'description': 'Cargos',
        'icon': '💼',
        'order_by': 'nombre'
    },
    {
        'name': 'cargo_salary_configs',
        'description': 'Configuración de Salarios',
        'icon': '💰',
        'order_by': 'cargo'
    },
    {
        'name': 'jornadas',
        'description': 'Jornadas',
        'icon': '📅',
        'order_by': 'fecha_jornada DESC',
        'limit': 50  # Solo últimas 50 jornadas
    },
    {
        'name': 'planilla_trabajadores',
        'description': 'Planilla de Trabajadores',
        'icon': '📋',
        'order_by': 'jornada_id DESC, nombre_empleado',
        'limit': 500  # Solo últimas 500 entradas
    },
    {
        'name': 'guardarropia_items',
        'description': 'Guardarropía',
        'icon': '🧥',
        'order_by': 'deposited_at DESC'
    },
    {
        'name': 'register_closes',
        'description': 'Cierres de Caja',
        'icon': '💵',
        'order_by': 'fecha_cierre DESC',
        'limit': 100  # Solo últimos 100 cierres
    },
    {
        'name': 'notifications',
        'description': 'Notificaciones',
        'icon': '🔔',
        'order_by': 'created_at DESC',
        'limit': 200  # Solo últimas 200 notificaciones
    }
]

def get_table_columns(conn, table_name):
    """Obtiene las columnas de una tabla"""
    result = conn.execute(text(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """))
    return result.fetchall()

def sync_table(prod_conn, local_conn, table_config):
    """Sincroniza una tabla específica"""
    table_name = table_config['name']
    description = table_config.get('description', table_name)
    icon = table_config.get('icon', '📦')
    order_by = table_config.get('order_by', 'id')
    where_clause = table_config.get('where', '1=1')
    limit = table_config.get('limit')
    
    try:
        # Construir query
        query = f"SELECT * FROM {table_name} WHERE {where_clause} ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"
        
        # Obtener datos de producción
        result = prod_conn.execute(text(query))
        rows = result.fetchall()
        
        if len(rows) == 0:
            print(f"   {icon} {description}: 0 registros (vacía)")
            return {'inserted': 0, 'updated': 0, 'total': 0}
        
        # Obtener nombres de columnas
        columns = [desc[0] for desc in result.description]
        columns_str = ','.join(columns)
        placeholders = ','.join(['?' for _ in columns])
        
        local_cursor = local_conn.cursor()
        
        # Contar registros en local antes
        local_cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        local_count_before = local_cursor.fetchone()[0]
        
        inserted = 0
        updated = 0
        
        for row in rows:
            # Convertir row a tupla (puede ser Row object)
            row_tuple = tuple(row)
            
            # Verificar si existe (usar primera columna como ID, asumiendo que es 'id')
            if 'id' in columns:
                id_index = columns.index('id')
                id_value = row_tuple[id_index]
                local_cursor.execute(f'SELECT id FROM {table_name} WHERE id = ?', (id_value,))
                exists = local_cursor.fetchone()
                
                if exists:
                    # Actualizar
                    set_clause = ','.join([f'{col} = ?' for col in columns])
                    update_query = f'UPDATE {table_name} SET {set_clause} WHERE id = ?'
                    local_cursor.execute(update_query, row_tuple + (id_value,))
                    updated += 1
                else:
                    # Insertar
                    insert_query = f'INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})'
                    local_cursor.execute(insert_query, row_tuple)
                    inserted += 1
            else:
                # Si no hay columna 'id', solo insertar (sin verificar duplicados)
                insert_query = f'INSERT OR REPLACE INTO {table_name} ({columns_str}) VALUES ({placeholders})'
                local_cursor.execute(insert_query, row_tuple)
                inserted += 1
        
        local_conn.commit()
        
        # Contar después
        local_cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        local_count_after = local_cursor.fetchone()[0]
        
        print(f"   {icon} {description}:")
        print(f"      Producción: {len(rows)} registros")
        print(f"      Local antes: {local_count_before}")
        print(f"      Insertados: {inserted}, Actualizados: {updated}")
        print(f"      Local después: {local_count_after}")
        
        return {
            'inserted': inserted,
            'updated': updated,
            'total': len(rows),
            'local_before': local_count_before,
            'local_after': local_count_after
        }
        
    except Exception as e:
        print(f"   ❌ Error al sincronizar {table_name}: {e}")
        return {'error': str(e)}

def sync_all_data():
    """Sincroniza todos los datos desde producción"""
    
    # Conectar a producción (PostgreSQL via proxy)
    prod_url = "postgresql://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@localhost:5432/bimba"
    
    try:
        prod_engine = create_engine(prod_url)
        prod_conn = prod_engine.connect()
    except Exception as e:
        print(f"❌ Error al conectar a producción: {e}")
        print("   Asegúrate de que Cloud SQL Proxy esté ejecutándose")
        return False
    
    # Conectar a local (SQLite)
    local_db = "instance/bimba.db"
    if not os.path.exists(local_db):
        print(f"❌ Base de datos local no encontrada: {local_db}")
        return False
    
    local_conn = sqlite3.connect(local_db)
    
    try:
        print(f"🔄 Iniciando sincronización...")
        print(f"   Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("")
        
        total_inserted = 0
        total_updated = 0
        tables_synced = 0
        
        # Sincronizar cada tabla
        for table_config in TABLES_TO_SYNC:
            result = sync_table(prod_conn, local_conn, table_config)
            if 'error' not in result:
                total_inserted += result.get('inserted', 0)
                total_updated += result.get('updated', 0)
                tables_synced += 1
            print("")
        
        print("=" * 50)
        print(f"✅ Sincronización completada:")
        print(f"   Tablas sincronizadas: {tables_synced}/{len(TABLES_TO_SYNC)}")
        print(f"   Total insertados: {total_inserted}")
        print(f"   Total actualizados: {total_updated}")
        print(f"   Total cambios: {total_inserted + total_updated}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error durante la sincronización: {e}")
        import traceback
        traceback.print_exc()
        local_conn.rollback()
        return False
    finally:
        local_conn.close()
        prod_conn.close()
        prod_engine.dispose()

if __name__ == '__main__':
    success = sync_all_data()
    sys.exit(0 if success else 1)




