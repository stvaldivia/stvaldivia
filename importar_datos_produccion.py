#!/usr/bin/env python3
"""
Script para importar datos de SQLite local a PostgreSQL en producción
"""
import os
import sys
import sqlite3
from datetime import datetime

# Configuración
LOCAL_DB = "instance/bimba.db"
PROD_DB_URL = "postgresql://bimba_user:bimba_prod_2024_secure@34.176.144.166:5432/bimba"

def get_table_counts(db_path):
    """Obtiene el conteo de registros por tabla"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables = []
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    for (table_name,) in cursor.fetchall():
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            count = cursor.fetchone()[0]
            tables.append((table_name, count))
        except Exception as e:
            print(f"  ⚠️  Error contando {table_name}: {e}")
            tables.append((table_name, 0))
    
    conn.close()
    return tables

def export_table_to_csv(db_path, table_name, output_file):
    """Exporta una tabla de SQLite a CSV"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Obtener columnas
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = [row[1] for row in cursor.fetchall()]
        
        if not columns:
            return False
        
        # Exportar datos
        cursor.execute(f'SELECT * FROM "{table_name}"')
        rows = cursor.fetchall()
        
        if not rows:
            return False
        
        # Escribir CSV
        import csv
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        
        return True
    except Exception as e:
        print(f"  ❌ Error exportando {table_name}: {e}")
        return False
    finally:
        conn.close()

def main():
    print("=" * 60)
    print("🔄 IMPORTACIÓN DE DATOS LOCALES A PRODUCCIÓN")
    print("=" * 60)
    print()
    
    if not os.path.exists(LOCAL_DB):
        print(f"❌ Base de datos local no encontrada: {LOCAL_DB}")
        return 1
    
    print("📊 Analizando base de datos local...")
    tables = get_table_counts(LOCAL_DB)
    
    print(f"\n📋 Encontradas {len(tables)} tablas:")
    total_records = 0
    tables_with_data = []
    for table_name, count in tables:
        if count > 0:
            print(f"  ✅ {table_name}: {count:,} registros")
            tables_with_data.append((table_name, count))
            total_records += count
        else:
            print(f"  ⏭️  {table_name}: Sin datos")
    
    print(f"\n📊 Total: {total_records:,} registros en {len(tables_with_data)} tablas")
    
    if not tables_with_data:
        print("\n⚠️  No hay datos para importar")
        return 0
    
    print("\n" + "=" * 60)
    print("🚀 INICIANDO IMPORTACIÓN")
    print("=" * 60)
    print()
    print("⚠️  Este proceso importará los datos a PostgreSQL en producción")
    print("⚠️  Los datos existentes en producción pueden ser sobrescritos")
    print()
    
    # Permitir ejecución automática con --yes
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    if not auto_confirm:
        try:
            response = input("¿Continuar? (s/N): ").strip().lower()
            if response != 's':
                print("❌ Importación cancelada")
                return 0
        except EOFError:
            # Si no hay input disponible, continuar automáticamente
            print("   (Modo automático - continuando...)")
    else:
        print("   (Modo automático - continuando...)")
    
    # Crear directorio temporal
    import tempfile
    temp_dir = tempfile.mkdtemp()
    print(f"\n📁 Directorio temporal: {temp_dir}")
    
    # Exportar tablas a CSV
    print("\n📤 Exportando tablas a CSV...")
    exported_tables = []
    for table_name, count in tables_with_data:
        csv_file = os.path.join(temp_dir, f"{table_name}.csv")
        print(f"  📥 Exportando {table_name} ({count:,} registros)...", end=" ")
        if export_table_to_csv(LOCAL_DB, table_name, csv_file):
            exported_tables.append((table_name, csv_file, count))
            print("✅")
        else:
            print("❌")
    
    if not exported_tables:
        print("\n❌ No se pudo exportar ninguna tabla")
        return 1
    
    print(f"\n✅ {len(exported_tables)} tablas exportadas")
    
    # Crear script de importación para PostgreSQL
    print("\n📝 Creando script de importación...")
    import_script = os.path.join(temp_dir, "import.sql")
    
    with open(import_script, 'w') as f:
        f.write("-- Script de importación de datos\n")
        f.write("-- Generado automáticamente\n\n")
        f.write("BEGIN;\n\n")
        
        for table_name, csv_file, count in exported_tables:
            f.write(f"-- Importar {table_name} ({count:,} registros)\n")
            f.write(f"\\echo 'Importando {table_name}...'\n")
            f.write(f"\\copy \"{table_name}\" FROM '{csv_file}' WITH (FORMAT csv, HEADER true, DELIMITER ',', NULL '');\n\n")
        
        f.write("COMMIT;\n")
    
    print(f"✅ Script creado: {import_script}")
    
    # Subir archivos a la VM
    print("\n📤 Subiendo archivos a la VM...")
    import subprocess
    
    VM_USER = "stvaldiviazal"
    VM_IP = "34.176.144.166"
    SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519_gcp")
    
    # Subir CSVs
    for table_name, csv_file, count in exported_tables:
        remote_path = f"/tmp/{table_name}_import.csv"
        print(f"  📤 Subiendo {table_name}...", end=" ")
        try:
            subprocess.run(
                ['scp', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
                 csv_file, f"{VM_USER}@{VM_IP}:{remote_path}"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("✅")
        except Exception as e:
            print(f"❌ Error: {e}")
            return 1
    
    # Subir script SQL
    print(f"  📤 Subiendo script SQL...", end=" ")
    try:
        subprocess.run(
            ['scp', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
             import_script, f"{VM_USER}@{VM_IP}:/tmp/import_data.sql"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("✅")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    # Ejecutar importación
    print("\n🔄 Ejecutando importación en PostgreSQL...")
    print("   (Esto puede tardar varios minutos dependiendo del volumen de datos)")
    print()
    
    try:
        # Actualizar rutas en el script SQL para que apunten a /tmp
        remote_script = "/tmp/import_data_fixed.sql"
        ssh_cmd = f"""
        cat > {remote_script} << 'SQLSCRIPT'
        BEGIN;
        """
        
        for table_name, csv_file, count in exported_tables:
            ssh_cmd += f"""
        \\echo 'Importando {table_name} ({count:,} registros)...'
        \\copy "{table_name}" FROM '/tmp/{table_name}_import.csv' WITH (FORMAT csv, HEADER true, DELIMITER ',', NULL '');
        """
        
        ssh_cmd += """
        COMMIT;
        SQLSCRIPT
        """
        
        # Ejecutar creación del script
        subprocess.run(
            ['ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
             f"{VM_USER}@{VM_IP}", ssh_cmd],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Ejecutar importación
        result = subprocess.run(
            ['ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
             f"{VM_USER}@{VM_IP}",
             "sudo -u postgres psql -d bimba -f /tmp/import_data_fixed.sql"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Importación completada exitosamente")
            # Mostrar output relevante
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if 'Importando' in line or 'COPY' in line or 'ERROR' in line or '❌' in line:
                    print(f"   {line}")
        else:
            print("❌ Error durante la importación:")
            print(result.stderr)
            return 1
            
    except Exception as e:
        print(f"❌ Error ejecutando importación: {e}")
        return 1
    
    # Limpiar archivos temporales
    print("\n🧹 Limpiando archivos temporales...")
    import shutil
    shutil.rmtree(temp_dir)
    
    # Limpiar archivos en la VM
    try:
        subprocess.run(
            ['ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
             f"{VM_USER}@{VM_IP}",
             "rm -f /tmp/*_import.csv /tmp/import_data*.sql"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except:
        pass
    
    print("\n" + "=" * 60)
    print("✅ IMPORTACIÓN COMPLETADA")
    print("=" * 60)
    print()
    print("📊 Verificando datos importados...")
    
    # Verificar conteos
    try:
        verify_cmd = """
        sudo -u postgres psql -d bimba -c "
        SELECT 
            schemaname,
            tablename,
            n_tup_ins as registros
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY n_tup_ins DESC
        LIMIT 15;
        "
        """
        result = subprocess.run(
            ['ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
             f"{VM_USER}@{VM_IP}", verify_cmd],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(result.stdout)
    except:
        pass
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

