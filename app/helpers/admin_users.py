import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app


ADMIN_USERS_FILE = '.admin_users.json'


def get_admin_users_file():
    """Obtiene la ruta del archivo de usuarios admin"""
    instance_path = current_app.instance_path
    return os.path.join(instance_path, ADMIN_USERS_FILE)


def load_admin_users():
    """Carga los usuarios admin desde el archivo"""
    users_file = get_admin_users_file()
    
    if not os.path.exists(users_file):
        # Crear usuarios por defecto
        default_users = {
            'sebagatica': {
                'password_hash': generate_password_hash('12345', method='pbkdf2:sha256'),
                'username': 'sebagatica'
            }
        }
        save_admin_users(default_users)
        return default_users
    
    try:
        with open(users_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        current_app.logger.error(f"Error al cargar usuarios admin: {e}")
        # Retornar usuarios por defecto si hay error
        return {
            'sebagatica': {
                'password_hash': generate_password_hash('12345', method='pbkdf2:sha256'),
                'username': 'sebagatica'
            }
        }


def save_admin_users(users):
    """Guarda los usuarios admin en el archivo"""
    users_file = get_admin_users_file()
    
    try:
        with open(users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        current_app.logger.error(f"Error al guardar usuarios admin: {e}")
        return False


def verify_admin_user(username, password):
    """Verifica si el usuario y contraseña son correctos"""
    users = load_admin_users()
    
    if username not in users:
        return False
    
    user = users[username]
    stored_hash = user.get('password_hash')
    
    if not stored_hash:
        return False
    
    # Verificar contraseña
    if stored_hash.startswith('pbkdf2:'):
        return check_password_hash(stored_hash, password)
    else:
        # Fallback: comparar texto plano (migración)
        if password == '12345' and username == 'sebagatica':
            # Actualizar al hash
            users[username]['password_hash'] = generate_password_hash(password, method='pbkdf2:sha256')
            save_admin_users(users)
            return True
        return False


def create_admin_user(username, password):
    """Crea un nuevo usuario admin"""
    users = load_admin_users()
    
    if username in users:
        return False  # Usuario ya existe
    
    users[username] = {
        'password_hash': generate_password_hash(password, method='pbkdf2:sha256'),
        'username': username
    }
    
    return save_admin_users(users)


def update_admin_user_password(username, new_password):
    """Actualiza la contraseña de un usuario admin"""
    users = load_admin_users()
    
    if username not in users:
        return False
    
    users[username]['password_hash'] = generate_password_hash(new_password, method='pbkdf2:sha256')
    return save_admin_users(users)


def delete_admin_user(username):
    """Elimina un usuario admin"""
    users = load_admin_users()
    
    if username not in users:
        return False
    
    if len(users) <= 1:
        return False  # No se puede eliminar el último usuario
    
    del users[username]
    return save_admin_users(users)


def list_admin_users():
    """Lista todos los usuarios admin (sin contraseñas)"""
    users = load_admin_users()
    return [{'username': username} for username in users.keys()]





