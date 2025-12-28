"""
Helper para integración con KLAP Checkout
"""
import logging
from typing import Optional, Dict, Any

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def get_klap_config() -> Dict[str, Any]:
    """Obtiene la configuración de KLAP desde variables de entorno"""
    return {
        'api_base_url': current_app.config.get('KLAP_API_BASE_URL'),
        'checkout_create_url': current_app.config.get('KLAP_CHECKOUT_CREATE_URL'),
        'checkout_status_url': current_app.config.get('KLAP_CHECKOUT_STATUS_URL'),
        'api_key': current_app.config.get('KLAP_API_KEY'),
        'api_key_header': current_app.config.get('KLAP_API_KEY_HEADER', 'Authorization'),
        'demo_mode': current_app.config.get('KLAP_DEMO_MODE', False),
    }


def _build_klap_headers(config: Dict[str, Any]) -> Dict[str, str]:
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    api_key = config.get('api_key')
    if api_key:
        header_name = config.get('api_key_header') or 'Authorization'
        if header_name.lower() == 'authorization':
            headers[header_name] = f"Bearer {api_key}"
        else:
            headers[header_name] = api_key
    return headers


def create_klap_checkout(
    amount: float,
    currency: str,
    order_id: str,
    customer_data: Dict[str, Any],
    return_url: str,
    cancel_url: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Crea un checkout en KLAP

    Returns:
        Dict con payment_id y checkout_url, o None si hay error
    """
    config = get_klap_config()

    if config.get('demo_mode'):
        demo_payment_id = f"DEMO-KLAP-{order_id}"
        demo_checkout_url = f"{return_url}?payment_id={demo_payment_id}&status=APPROVED"
        return {
            'payment_id': demo_payment_id,
            'checkout_url': demo_checkout_url,
            'payment_data': {
                'status': 'APPROVED',
                'message': 'Pago simulado en modo demo KLAP',
            }
        }

    create_url = config.get('checkout_create_url')
    if not create_url:
        api_base_url = config.get('api_base_url')
        if not api_base_url:
            logger.error("KLAP API base URL no configurada (KLAP_API_BASE_URL/KLAP_CHECKOUT_CREATE_URL)")
            return None
        create_url = f"{api_base_url.rstrip('/')}/checkout"

    payload = {
        'amount': amount,
        'currency': currency,
        'order_id': order_id,
        'return_url': return_url,
        'cancel_url': cancel_url,
        'customer': customer_data,
        'metadata': metadata or {},
    }

    headers = _build_klap_headers(config)

    try:
        logger.info(f"Creando checkout KLAP en {create_url} para orden {order_id}")
        response = requests.post(create_url, json=payload, headers=headers, timeout=20)
        if response.status_code >= 400:
            logger.error(f"Error KLAP Checkout: {response.status_code} - {response.text}")
            return None

        payment_response = response.json()
        checkout_url = (
            payment_response.get('checkout_url')
            or payment_response.get('checkoutUrl')
            or payment_response.get('redirect_url')
            or payment_response.get('url')
            or payment_response.get('payment_url')
        )
        payment_id = (
            payment_response.get('payment_id')
            or payment_response.get('id')
            or payment_response.get('paymentId')
        )

        if not checkout_url or not payment_id:
            logger.error(f"Respuesta KLAP inválida: {payment_response}")
            return None

        return {
            'payment_id': payment_id,
            'checkout_url': checkout_url,
            'payment_data': payment_response,
        }
    except Exception as e:
        logger.error(f"Excepción al crear checkout KLAP: {e}", exc_info=True)
        return None


def get_klap_payment_status(payment_id: str) -> Optional[Dict[str, Any]]:
    """Consulta estado de pago en KLAP si hay endpoint configurado."""
    config = get_klap_config()

    status_url_template = config.get('checkout_status_url')
    api_base_url = config.get('api_base_url')
    if status_url_template:
        status_url = status_url_template.format(payment_id=payment_id)
    elif api_base_url:
        status_url = f"{api_base_url.rstrip('/')}/checkout/{payment_id}"
    else:
        return None

    headers = _build_klap_headers(config)

    try:
        response = requests.get(status_url, headers=headers, timeout=20)
        if response.status_code >= 400:
            logger.error(f"Error KLAP status: {response.status_code} - {response.text}")
            return None
        return response.json()
    except Exception as e:
        logger.error(f"Excepción al consultar status KLAP: {e}", exc_info=True)
        return None


def is_klap_payment_approved(payment_status: Dict[str, Any]) -> bool:
    """Determina si el pago KLAP está aprobado según status conocido."""
    if not payment_status:
        return False
    status = str(payment_status.get('status') or payment_status.get('state') or '').upper()
    if status in {'APPROVED', 'PAID', 'SUCCESS', 'COMPLETED'}:
        return True
    if payment_status.get('success') is True:
        return True
    return False


def extract_klap_payment_info(payment_status: Dict[str, Any]) -> Dict[str, Any]:
    """Extrae información relevante desde payload de KLAP."""
    return {
        'payment_id': payment_status.get('payment_id') or payment_status.get('id') or payment_status.get('paymentId'),
        'status': payment_status.get('status') or payment_status.get('state'),
        'transaction_id': payment_status.get('transaction_id') or payment_status.get('transactionId'),
        'raw': payment_status,
    }
