import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app


def get_admin_password_hash():
    """Obtiene o genera el hash de la contraseña del administrador"""
    instance_path = current_app.instance_path
    password_hash_file = os.path.join(instance_path, '.admin_password_hash')
    
    # Si existe hash guardado, usarlo
    if os.path.exists(password_hash_file):
        with open(password_hash_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    # Si no existe, obtener la contraseña del env y generar hash
    plain_password = current_app.config.get('ADMIN_PASSWORD')
    if not plain_password:
        return None
    
    # Generar hash y guardarlo (usar pbkdf2:sha256 compatible con Python 3.9)
    password_hash = generate_password_hash(plain_password, method='pbkdf2:sha256')
    with open(password_hash_file, 'w', encoding='utf-8') as f:
        f.write(password_hash)
    
    return password_hash


def verify_admin_password(password):
    """Verifica si la contraseña proporcionada es correcta"""
    stored_hash = get_admin_password_hash()
    if not stored_hash:
        return False
    
    # Si el hash empieza con pbkdf2: (werkzeug), usar check_password_hash
    # Si no, podría ser texto plano (migración)
    if stored_hash.startswith('pbkdf2:'):
        return check_password_hash(stored_hash, password)
    else:
        # Fallback para migración: comparar texto plano
        # Esto permite migrar sin perder acceso
        plain_password = current_app.config.get('ADMIN_PASSWORD')
        if plain_password and plain_password == password:
            # Si coincide, actualizar al hash (usar pbkdf2:sha256 compatible con Python 3.9)
            new_hash = generate_password_hash(password, method='pbkdf2:sha256')
            instance_path = current_app.instance_path
            password_hash_file = os.path.join(instance_path, '.admin_password_hash')
            with open(password_hash_file, 'w', encoding='utf-8') as f:
                f.write(new_hash)
            return True
        return False


def update_admin_password(new_password):
    """Actualiza la contraseña del administrador"""
    # Usar pbkdf2:sha256 compatible con Python 3.9
    new_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
    instance_path = current_app.instance_path
    password_hash_file = os.path.join(instance_path, '.admin_password_hash')
    
    with open(password_hash_file, 'w', encoding='utf-8') as f:
        f.write(new_hash)
    
    return True

