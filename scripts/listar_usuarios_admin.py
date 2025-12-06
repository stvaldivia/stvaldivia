#!/usr/bin/env python3
"""
Script para listar usuarios admin
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.helpers.admin_users import list_admin_users, load_admin_users

app = create_app()

with app.app_context():
    print("=" * 60)
    print("👥 USUARIOS ADMINISTRADORES")
    print("=" * 60)
    print()
    
    users = list_admin_users()
    all_users = load_admin_users()
    
    if users:
        print("Usuarios encontrados:")
        for user in users:
            username = user['username']
            user_data = all_users.get(username, {})
            has_role = 'role' in user_data
            role = user_data.get('role', 'admin')
            print(f"  ✅ {username}")
            if has_role:
                print(f"     Rol: {role}")
    else:
        print("⚠️  No hay usuarios configurados aún")
        print()
        print("💡 Usuario por defecto (se crea automáticamente):")
        print("   Usuario: sebagatica")
        print("   Contraseña: 12345")
    
    print()
    print("=" * 60)
    print()
    print("📝 Nota: Los usuarios se almacenan en:")
    print(f"   {app.instance_path}/.admin_users.json")



