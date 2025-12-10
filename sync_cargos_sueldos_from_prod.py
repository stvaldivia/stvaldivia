#!/usr/bin/env python3
"""
Script para sincronizar cargos y sueldos desde producción (Cloud SQL) a local (SQLite)
"""
import os
import sys
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Configuración de Cloud SQL (producción)
CLOUD_SQL_CONNECTION = "pelagic-river-479014-a3:us-central1:bimba-db"
DB_NAME = "bimba"
DB_USER = "bimba_user"
DB_PASSWORD = "qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas="

# Ruta a la base de datos local
LOCAL_DB_PATH = "instance/bimba.db"

def connect_to_prod():
    """Conecta a la base de datos de producción usando Cloud SQL Proxy"""
    try:
        # Intentar conectar usando el proxy local
        conn = psycopg2.connect(
            host="127.0.0.1",
            port=5432,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print("✅ Conectado a producción (Cloud SQL)")
        return conn
    except Exception as e:
        print(f"❌ Error al conectar a producción: {e}")
        print("\n💡 Asegúrate de que el Cloud SQL Proxy esté corriendo:")
        print("   ./cloud-sql-proxy pelagic-river-479014-a3:us-central1:bimba-db")
        sys.exit(1)

def connect_to_local():
    """Conecta a la base de datos local SQLite"""
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        print("✅ Conectado a base de datos local")
        return conn
    except Exception as e:
        print(f"❌ Error al conectar a base de datos local: {e}")
        sys.exit(1)

def sync_cargos(prod_conn, local_conn):
    """Sincroniza la tabla de cargos"""
    print("\n📋 Sincronizando cargos...")
    
    # Obtener cargos de producción
    prod_cursor = prod_conn.cursor(cursor_factory=RealDictCursor)
    prod_cursor.execute("""
        SELECT id, nombre, descripcion, activo, orden, created_at, updated_at
        FROM cargos
        ORDER BY orden, nombre
    """)
    prod_cargos = prod_cursor.fetchall()
    
    print(f"   📥 Encontrados {len(prod_cargos)} cargos en producción")
    
    # Obtener cargos locales
    local_cursor = local_conn.cursor()
    local_cursor.execute("SELECT id, nombre FROM cargos")
    local_cargos = {row[1]: row[0] for row in local_cursor.fetchall()}
    
    # Sincronizar
    inserted = 0
    updated = 0
    
    for cargo in prod_cargos:
        nombre = cargo['nombre']
        if nombre in local_cargos:
            # Actualizar cargo existente
            local_cursor.execute("""
                UPDATE cargos 
                SET descripcion = ?, activo = ?, orden = ?, updated_at = ?
                WHERE nombre = ?
            """, (
                cargo['descripcion'],
                1 if cargo['activo'] else 0,
                cargo['orden'],
                cargo['updated_at'].isoformat() if cargo['updated_at'] else None,
                nombre
            ))
            updated += 1
        else:
            # Insertar nuevo cargo
            local_cursor.execute("""
                INSERT INTO cargos (nombre, descripcion, activo, orden, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                cargo['nombre'],
                cargo['descripcion'],
                1 if cargo['activo'] else 0,
                cargo['orden'],
                cargo['created_at'].isoformat() if cargo['created_at'] else None,
                cargo['updated_at'].isoformat() if cargo['updated_at'] else None
            ))
            inserted += 1
    
    local_conn.commit()
    print(f"   ✅ Cargos sincronizados: {inserted} nuevos, {updated} actualizados")

def sync_cargo_salaries(prod_conn, local_conn):
    """Sincroniza la configuración de sueldos por cargo"""
    print("\n💰 Sincronizando sueldos por cargo...")
    
    # Obtener sueldos de producción
    prod_cursor = prod_conn.cursor(cursor_factory=RealDictCursor)
    prod_cursor.execute("""
        SELECT cargo, sueldo_por_turno, bono_fijo, created_at, updated_at
        FROM cargo_salary_configs
        ORDER BY cargo
    """)
    prod_salaries = prod_cursor.fetchall()
    
    print(f"   📥 Encontradas {len(prod_salaries)} configuraciones de sueldo en producción")
    
    # Obtener sueldos locales
    local_cursor = local_conn.cursor()
    local_cursor.execute("SELECT cargo FROM cargo_salary_configs")
    local_salaries = {row[0] for row in local_cursor.fetchall()}
    
    # Sincronizar
    inserted = 0
    updated = 0
    
    for salary in prod_salaries:
        cargo = salary['cargo']
        sueldo = float(salary['sueldo_por_turno'] or 0)
        bono = float(salary['bono_fijo'] or 0)
        
        if cargo in local_salaries:
            # Actualizar sueldo existente
            local_cursor.execute("""
                UPDATE cargo_salary_configs 
                SET sueldo_por_turno = ?, bono_fijo = ?, updated_at = ?
                WHERE cargo = ?
            """, (
                sueldo,
                bono,
                salary['updated_at'].isoformat() if salary['updated_at'] else None,
                cargo
            ))
            updated += 1
            print(f"   💵 {cargo}: ${sueldo:,.0f} + ${bono:,.0f} bono (actualizado)")
        else:
            # Insertar nuevo sueldo
            local_cursor.execute("""
                INSERT INTO cargo_salary_configs (cargo, sueldo_por_turno, bono_fijo, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                cargo,
                sueldo,
                bono,
                salary['created_at'].isoformat() if salary['created_at'] else None,
                salary['updated_at'].isoformat() if salary['updated_at'] else None
            ))
            inserted += 1
            print(f"   💵 {cargo}: ${sueldo:,.0f} + ${bono:,.0f} bono (nuevo)")
    
    local_conn.commit()
    print(f"   ✅ Sueldos sincronizados: {inserted} nuevos, {updated} actualizados")

def main():
    print("🔄 Sincronización de Cargos y Sueldos desde Producción")
    print("=" * 60)
    
    # Conectar a ambas bases de datos
    prod_conn = connect_to_prod()
    local_conn = connect_to_local()
    
    try:
        # Sincronizar cargos
        sync_cargos(prod_conn, local_conn)
        
        # Sincronizar sueldos
        sync_cargo_salaries(prod_conn, local_conn)
        
        print("\n" + "=" * 60)
        print("✅ Sincronización completada exitosamente")
        print("\n💡 Los datos de cargos y sueldos ahora están sincronizados con producción")
        
    except Exception as e:
        print(f"\n❌ Error durante la sincronización: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        prod_conn.close()
        local_conn.close()

if __name__ == "__main__":
    main()




