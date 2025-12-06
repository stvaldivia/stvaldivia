import os
import json
from flask import current_app

DEFAULT_FRAUD_CONFIG = {
    'max_hours_old_ticket': 24,
    'max_delivery_attempts': 3
}

CONFIG_FILE = 'fraud_config.json'


def get_fraud_config_file():
    """Obtiene la ruta del archivo de configuración de fraude"""
    try:
        instance_path = current_app.instance_path
    except RuntimeError:
        instance_path = os.path.join(os.getcwd(), 'instance')
        os.makedirs(instance_path, exist_ok=True)
    
    return os.path.join(instance_path, CONFIG_FILE)


def load_fraud_config():
    """Carga la configuración de fraude"""
    config_file = get_fraud_config_file()
    
    if not os.path.exists(config_file):
        # Crear archivo con configuración por defecto
        save_fraud_config(DEFAULT_FRAUD_CONFIG)
        return DEFAULT_FRAUD_CONFIG.copy()
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Mergear con defaults para asegurar que todas las keys existan
            merged = DEFAULT_FRAUD_CONFIG.copy()
            merged.update(config)
            return merged
    except Exception as e:
        current_app.logger.error(f"Error al cargar configuración de fraude: {e}")
        return DEFAULT_FRAUD_CONFIG.copy()


def save_fraud_config(config):
    """Guarda la configuración de fraude"""
    config_file = get_fraud_config_file()
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        current_app.logger.error(f"Error al guardar configuración de fraude: {e}")
        return False




