#!/usr/bin/env python3
"""
Script para hacer backup automático de la base de datos BIMBA
"""
import sys
import os
import shutil
from datetime import datetime, timedelta

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

def backup_database():
    """Crea un backup de la base de datos"""
    app = create_app()
    
    with app.app_context():
        # Obtener ruta de la base de datos
        instance_path = app.config.get('INSTANCE_PATH', 'instance')
        db_path = os.path.join(instance_path, 'bimba.db')
        
        if not os.path.exists(db_path):
            print(f"❌ No se encontró la base de datos en: {db_path}")
            return False
        
        # Crear directorio de backups si no existe
        backups_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
        os.makedirs(backups_dir, exist_ok=True)
        
        # Nombre del archivo de backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'bimba_backup_{timestamp}.db'
        backup_path = os.path.join(backups_dir, backup_filename)
        
        try:
            # Copiar base de datos
            shutil.copy2(db_path, backup_path)
            
            # Obtener tamaño del archivo
            size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            
            print(f"✅ Backup creado exitosamente:")
            print(f"   Archivo: {backup_filename}")
            print(f"   Tamaño: {size_mb:.2f} MB")
            print(f"   Ubicación: {backup_path}")
            
            # Limpiar backups antiguos (mantener solo los últimos 30 días)
            cleanup_old_backups(backups_dir, days=30)
            
            return True
            
        except Exception as e:
            print(f"❌ Error al crear backup: {e}")
            return False


def cleanup_old_backups(backups_dir, days=30):
    """Elimina backups más antiguos que el número de días especificado"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for filename in os.listdir(backups_dir):
            if filename.startswith('bimba_backup_') and filename.endswith('.db'):
                filepath = os.path.join(backups_dir, filename)
                
                # Obtener fecha de modificación
                mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if mod_time < cutoff_date:
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"   🗑️  Eliminado backup antiguo: {filename}")
        
        if deleted_count > 0:
            print(f"   ✅ {deleted_count} backup(s) antiguo(s) eliminado(s)")
        else:
            print(f"   ✅ No hay backups antiguos para eliminar")
            
    except Exception as e:
        print(f"   ⚠️  Error al limpiar backups antiguos: {e}")


if __name__ == '__main__':
    print("🔄 Iniciando backup de base de datos...")
    print("=" * 50)
    success = backup_database()
    print("=" * 50)
    if success:
        print("✅ Proceso de backup completado")
        sys.exit(0)
    else:
        print("❌ Error en el proceso de backup")
        sys.exit(1)

