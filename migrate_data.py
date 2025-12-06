#!/usr/bin/env python3
"""
Script para migrar datos de SQLite local a PostgreSQL en Cloud SQL
Sistema BIMBA
"""
import sqlite3
import psycopg2
import os
import sys
from datetime import datetime

# Configuración de Cloud SQL (desde cloud_sql_credentials.txt)
CLOUD_SQL_CONFIG = {
    'host': '/cloudsql/pelagic-river-479014-a3:us-central1:bimba-db',
    'database': 'bimba',
    'user': 'bimba_user',
    'password': 'qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas='
}

# Base de datos SQLite local
SQLITE_DB = 'instance/bimba.db'

# Tablas a migrar (en orden de dependencias)
TABLES_TO_MIGRATE = [
    'employees',
    'cargos',
    'cargo_salary_configs',
    'jornadas',
    'planilla_trabajadores',
    'register_closes',
    'api_connection_logs',
    'audit_logs',
    'ficha_review_logs',
    'notifications'
]

def connect_sqlite():
    """Conecta a SQLite local"""
    if not os.path.exists(SQLITE_DB):
        print(f"❌ Error: No se encontró {SQLITE_DB}")
        sys.exit(1)
    
    return sqlite3.connect(SQLITE_DB)

def connect_postgres():
    """Conecta a PostgreSQL en Cloud SQL"""
    try:
        # Intentar conexión con socket Unix (para Cloud Run)
        conn = psycopg2.connect(**CLOUD_SQL_CONFIG)
        return conn
    except Exception as e:
        print(f"⚠️  No se pudo conectar con socket Unix: {e}")
        print("Intentando con conexión TCP/IP...")
        
        # Intentar con IP pública
        config_tcp = CLOUD_SQL_CONFIG.copy()
        config_tcp['host'] = '35.238.80.13'  # IP pública de Cloud SQL
        config_tcp['port'] = 5432
        
        try:
            conn = psycopg2.connect(**config_tcp)
            return conn
        except Exception as e2:
            print(f"❌ Error al conectar a PostgreSQL: {e2}")
            print("\n💡 Sugerencia: Ejecuta este script desde Cloud Shell o habilita la IP pública")
            sys.exit(1)

def get_table_schema(sqlite_conn, table_name):
    """Obtiene el esquema de una tabla de SQLite"""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()

def get_table_data(sqlite_conn, table_name):
    """Obtiene todos los datos de una tabla"""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    return cursor.fetchall()

def migrate_table(sqlite_conn, postgres_conn, table_name):
    """Migra una tabla de SQLite a PostgreSQL"""
    print(f"\n📦 Migrando tabla: {table_name}")
    
    try:
        # Obtener datos de SQLite
        data = get_table_data(sqlite_conn, table_name)
        
        if not data:
            print(f"  ⚠️  Tabla vacía, saltando...")
            return True
        
        print(f"  📊 {len(data)} registros encontrados")
        
        # Obtener nombres de columnas
        cursor = sqlite_conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
        columns = [description[0] for description in cursor.description]
        
        # Preparar query de inserción
        placeholders = ','.join(['%s'] * len(columns))
        columns_str = ','.join(columns)
        insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        
        # Insertar datos en PostgreSQL
        pg_cursor = postgres_conn.cursor()
        inserted = 0
        
        for row in data:
            try:
                pg_cursor.execute(insert_query, row)
                inserted += 1
            except Exception as e:
                print(f"  ⚠️  Error en registro: {e}")
                continue
        
        postgres_conn.commit()
        print(f"  ✅ {inserted} registros migrados")
        return True
        
    except Exception as e:
        print(f"  ❌ Error al migrar tabla {table_name}: {e}")
        postgres_conn.rollback()
        return False

def verify_migration(sqlite_conn, postgres_conn, table_name):
    """Verifica que la migración fue exitosa"""
    try:
        # Contar registros en SQLite
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        sqlite_count = sqlite_cursor.fetchone()[0]
        
        # Contar registros en PostgreSQL
        pg_cursor = postgres_conn.cursor()
        pg_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        pg_count = pg_cursor.fetchone()[0]
        
        if sqlite_count == pg_count:
            print(f"  ✅ Verificación OK: {pg_count} registros")
            return True
        else:
            print(f"  ⚠️  Diferencia: SQLite={sqlite_count}, PostgreSQL={pg_count}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error en verificación: {e}")
        return False

def main():
    print("=" * 60)
    print("🔄 MIGRACIÓN DE DATOS: SQLite → PostgreSQL (Cloud SQL)")
    print("=" * 60)
    print()
    
    # Conectar a bases de datos
    print("📡 Conectando a bases de datos...")
    sqlite_conn = connect_sqlite()
    print("  ✅ SQLite conectado")
    
    postgres_conn = connect_postgres()
    print("  ✅ PostgreSQL conectado")
    print()
    
    # Migrar cada tabla
    results = {}
    for table in TABLES_TO_MIGRATE:
        success = migrate_table(sqlite_conn, postgres_conn, table)
        results[table] = success
        
        if success:
            verify_migration(sqlite_conn, postgres_conn, table)
    
    # Cerrar conexiones
    sqlite_conn.close()
    postgres_conn.close()
    
    # Resumen
    print()
    print("=" * 60)
    print("📊 RESUMEN DE MIGRACIÓN")
    print("=" * 60)
    
    successful = sum(1 for v in results.values() if v)
    failed = len(results) - successful
    
    print(f"\n✅ Exitosas: {successful}/{len(results)}")
    print(f"❌ Fallidas: {failed}/{len(results)}")
    
    if failed > 0:
        print("\n⚠️  Tablas con errores:")
        for table, success in results.items():
            if not success:
                print(f"  - {table}")
    
    print("\n" + "=" * 60)
    
    if failed == 0:
        print("🎉 ¡Migración completada exitosamente!")
        print("\n📋 Próximo paso:")
        print("   Actualiza el sitio en producción desde el Panel de Control")
        print("   o ejecuta: ./deploy.sh")
    else:
        print("⚠️  Migración completada con errores")
        print("   Revisa los mensajes de error arriba")
    
    print("=" * 60)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migración cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
