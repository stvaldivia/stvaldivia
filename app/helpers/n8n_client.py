"""
Cliente para enviar eventos a n8n
Permite que la aplicación envíe eventos a n8n cuando ocurren acciones específicas
"""
import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from flask import current_app

logger = logging.getLogger(__name__)


def send_to_n8n(event_type: str, data: Dict[str, Any], workflow_id: Optional[str] = None) -> bool:
    """
    Envía un evento a n8n
    
    Args:
        event_type: Tipo de evento (ej: 'delivery_created', 'inventory_updated', 'shift_closed')
        data: Datos del evento
        workflow_id: ID del workflow específico (opcional)
        
    Returns:
        bool: True si el evento se envió correctamente, False en caso contrario
    """
    webhook_url = current_app.config.get('N8N_WEBHOOK_URL')
    
    if not webhook_url:
        logger.debug("N8N_WEBHOOK_URL no configurada, no se enviará evento a n8n")
        return False
    
    # Si hay workflow_id, agregarlo a la URL
    if workflow_id:
        # Si la URL termina con /, no agregar otro /
        if webhook_url.endswith('/'):
            webhook_url = f"{webhook_url}{workflow_id}"
        else:
            webhook_url = f"{webhook_url}/{workflow_id}"
    
    payload = {
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        'data': data
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Agregar autenticación si está configurada (leer desde SystemConfig primero)
    try:
        from app.models.system_config_models import SystemConfig
        secret = SystemConfig.get('n8n_webhook_secret') or current_app.config.get('N8N_WEBHOOK_SECRET')
        api_key = SystemConfig.get('n8n_api_key') or current_app.config.get('N8N_API_KEY')
    except:
        secret = current_app.config.get('N8N_WEBHOOK_SECRET')
        api_key = current_app.config.get('N8N_API_KEY')
    
    if secret:
        headers['X-Webhook-Secret'] = secret
    
    if api_key:
        headers['X-API-Key'] = api_key
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
        logger.info(f"Evento enviado a n8n: {event_type}")
        return True
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout enviando evento a n8n: {event_type}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error enviando evento a n8n: {event_type}, error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado enviando evento a n8n: {event_type}, error: {e}")
        return False


def send_delivery_created(delivery_id: int, item_name: str, quantity: int, bartender: str, barra: str):
    """
    Envía evento cuando se crea una entrega
    
    Args:
        delivery_id: ID de la entrega
        item_name: Nombre del item
        quantity: Cantidad
        bartender: Nombre del bartender
        barra: Nombre de la barra
    """
    return send_to_n8n('delivery_created', {
        'delivery_id': delivery_id,
        'item_name': item_name,
        'quantity': quantity,
        'bartender': bartender,
        'barra': barra
    })


def send_inventory_updated(ingredient_id: int, ingredient_name: str, quantity: float, location: str):
    """
    Envía evento cuando se actualiza el inventario
    
    Args:
        ingredient_id: ID del ingrediente
        ingredient_name: Nombre del ingrediente
        quantity: Nueva cantidad
        location: Ubicación
    """
    return send_to_n8n('inventory_updated', {
        'ingredient_id': ingredient_id,
        'ingredient_name': ingredient_name,
        'quantity': quantity,
        'location': location
    })


def send_shift_closed(shift_date: str, total_sales: float, total_deliveries: int):
    """
    Envía evento cuando se cierra un turno
    
    Args:
        shift_date: Fecha del turno
        total_sales: Total de ventas
        total_deliveries: Total de entregas
    """
    return send_to_n8n('shift_closed', {
        'shift_date': shift_date,
        'total_sales': total_sales,
        'total_deliveries': total_deliveries
    })


def send_sale_created(sale_id: str, amount: float, payment_method: str, register_id: int):
    """
    Envía evento cuando se crea una venta
    
    Args:
        sale_id: ID de la venta
        amount: Monto de la venta
        payment_method: Método de pago
        register_id: ID de la caja
    """
    return send_to_n8n('sale_created', {
        'sale_id': sale_id,
        'amount': amount,
        'payment_method': payment_method,
        'register_id': register_id
    })


def send_custom_event(event_type: str, data: Dict[str, Any], workflow_id: Optional[str] = None):
    """
    Envía un evento personalizado a n8n
    
    Args:
        event_type: Tipo de evento personalizado
        data: Datos del evento
        workflow_id: ID del workflow específico (opcional)
    """
    return send_to_n8n(event_type, data, workflow_id)

