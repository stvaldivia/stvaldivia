#!/usr/bin/env python3
"""
Script para gestionar usuarios administradores
"""
import sys
import os
import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.helpers.admin_users import (
    list_admin_users, 
    create_admin_user, 
    update_admin_user_password,
    delete_admin_user,
    verify_admin_user
)

app = create_app()

def main():
    print("=" * 60)
    print("👥 GESTIÓN DE USUARIOS ADMINISTRADORES")
    print("=" * 60)
    print()
    
    with app.app_context():
        # Listar usuarios
        users = list_admin_users()
        print("📋 Usuarios actuales:")
        if users:
            for i, user in enumerate(users, 1):
                print(f"  {i}. {user['username']}")
        else:
            print("  ⚠️  No hay usuarios")
        print()
        
        print("Opciones:")
        print("1. Crear nuevo usuario")
        print("2. Cambiar contraseña de usuario")
        print("3. Eliminar usuario")
        print("4. Verificar credenciales")
        print("5. Salir")
        print()
        
        opcion = input("Selecciona opción [1-5]: ").strip()
        
        if opcion == '1':
            username = input("Usuario: ").strip()
            if not username:
                print("❌ Usuario no puede estar vacío")
                return
            
            password = getpass.getpass("Contraseña: ")
            if len(password) < 4:
                print("❌ La contraseña debe tener al menos 4 caracteres")
                return
            
            if create_admin_user(username, password):
                print(f"✅ Usuario '{username}' creado exitosamente")
            else:
                print(f"❌ El usuario '{username}' ya existe")
        
        elif opcion == '2':
            username = input("Usuario: ").strip()
            password = getpass.getpass("Nueva contraseña: ")
            
            if len(password) < 4:
                print("❌ La contraseña debe tener al menos 4 caracteres")
                return
            
            if update_admin_user_password(username, password):
                print(f"✅ Contraseña de '{username}' actualizada")
            else:
                print(f"❌ Usuario '{username}' no encontrado")
        
        elif opcion == '3':
            username = input("Usuario a eliminar: ").strip()
            
            if delete_admin_user(username):
                print(f"✅ Usuario '{username}' eliminado")
            else:
                print(f"❌ No se pudo eliminar (usuario no existe o es el último)")
        
        elif opcion == '4':
            username = input("Usuario: ").strip()
            password = getpass.getpass("Contraseña: ")
            
            if verify_admin_user(username, password):
                print("✅ Credenciales correctas")
            else:
                print("❌ Credenciales incorrectas")
        
        elif opcion == '5':
            print("👋 Adiós")
        else:
            print("❌ Opción inválida")

if __name__ == '__main__':
    main()



