"""
Helper para GetNet basado en PlaceToPay API
GetNet usa PlaceToPay como base, por lo que la estructura es similar
"""
import logging
import requests
import hashlib
import base64
import secrets
from typing import Optional, Dict, Any
from flask import current_app
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def generate_placetopay_signature(login: str, trankey: str, seed: str, nonce: str) -> str:
    """
    Genera firma SHA256 para PlaceToPay/GetNet
    
    Formato PlaceToPay estándar: SHA256(nonce + seed + trankey)
    """
    data_to_hash = f"{nonce}{seed}{trankey}"
    signature = hashlib.sha256(data_to_hash.encode('utf-8')).digest()
    return base64.b64encode(signature).decode('utf-8')


def generate_placetopay_auth(login: str, trankey: str) -> Dict[str, str]:
    """
    Genera objeto de autenticación para PlaceToPay/GetNet
    
    Estructura estándar de PlaceToPay:
    {
        "login": "login_value",
        "tranKey": "signature",
        "seed": "ISO8601_timestamp",
        "nonce": "base64_random"
    }
    """
    # Seed: timestamp ISO 8601 en UTC
    seed = datetime.utcnow().isoformat()
    
    # Nonce: valor aleatorio en base64
    nonce_bytes = secrets.token_bytes(16)
    nonce = base64.b64encode(nonce_bytes).decode('utf-8')
    
    # Generar firma
    signature = generate_placetopay_signature(login, trankey, seed, nonce)
    
    return {
        'login': login,
        'tranKey': signature,
        'seed': seed,
        'nonce': nonce
    }


def create_placetopay_payment_request(
    auth: Dict[str, str],
    amount: float,
    currency: str,
    reference: str,
    description: str,
    return_url: str,
    cancel_url: str,
    buyer_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Crea request para PlaceToPay/GetNet según estructura estándar
    
    Estructura PlaceToPay:
    {
        "auth": {...},
        "payment": {
            "reference": "...",
            "description": "...",
            "amount": {
                "currency": "CLP",
                "total": 10000
            }
        },
        "expiration": "ISO8601",
        "returnUrl": "...",
        "cancelUrl": "...",
        "buyer": {...},
        "ipAddress": "...",
        "userAgent": "..."
    }
    """
    return {
        'auth': auth,
        'payment': {
            'reference': reference,
            'description': description,
            'amount': {
                'currency': currency,
                'total': int(amount)  # CLP no usa decimales
            }
        },
        'expiration': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        'returnUrl': return_url,
        'cancelUrl': cancel_url,
        'buyer': buyer_data,
        'ipAddress': buyer_data.get('ipAddress', '127.0.0.1'),
        'userAgent': buyer_data.get('userAgent', 'Mozilla/5.0')
    }


def get_placetopay_endpoint(base_url: str, endpoint_type: str = 'api') -> str:
    """
    Obtiene el endpoint correcto para PlaceToPay/GetNet
    
    PlaceToPay típicamente usa:
    - /api/collect (para crear pagos)
    - /api/query (para consultar)
    - /api/reverse (para reversar)
    
    GetNet puede usar:
    - /api/collect
    - /api/v1/payment
    - /checkout/api/collect
    """
    if endpoint_type == 'collect':
        # Endpoint estándar de PlaceToPay para crear pagos
        return f"{base_url}/api/collect"
    elif endpoint_type == 'query':
        return f"{base_url}/api/query"
    elif endpoint_type == 'reverse':
        return f"{base_url}/api/reverse"
    else:
        # Fallback
        return f"{base_url}/api/collect"


def create_getnet_payment_placetopay(
    amount: float,
    currency: str,
    order_id: str,
    customer_data: Dict[str, Any],
    return_url: str,
    cancel_url: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Crea un pago usando estructura PlaceToPay (estándar de GetNet)
    """
    from app.helpers.getnet_web_helper import get_getnet_config
    
    config = get_getnet_config()
    
    if not config.get('login') or not config.get('trankey'):
        logger.error("GetNet credentials no configuradas")
        return None
    
    try:
        # Generar autenticación
        auth = generate_placetopay_auth(config['login'], config['trankey'])
        
        # Preparar datos del comprador
        buyer_data = {
            'document': customer_data.get('document_number', ''),
            'documentType': 'CC',  # CC, NIT, CE, etc.
            'name': customer_data.get('first_name', ''),
            'surname': customer_data.get('last_name', ''),
            'email': customer_data.get('email', ''),
            'mobile': customer_data.get('phone_number', ''),
            'address': {
                'street': customer_data.get('address', ''),
                'city': customer_data.get('city', 'Santiago'),
                'country': 'CL'  # Chile - código ISO 3166-1 alpha-2
            }
        }
        
        # Crear request
        payment_request = create_placetopay_payment_request(
            auth=auth,
            amount=amount,
            currency=currency,
            reference=order_id,
            description=f'Pago de entradas - {order_id}',
            return_url=return_url,
            cancel_url=cancel_url,
            buyer_data=buyer_data
        )
        
        # Obtener endpoint
        endpoint = get_placetopay_endpoint(config['api_base_url'], 'collect')
        
        # Headers
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        logger.info(f"Creando pago PlaceToPay/GetNet: endpoint={endpoint}")
        logger.debug(f"Request: {payment_request}")
        
        response = requests.post(
            endpoint,
            json=payment_request,
            headers=headers,
            timeout=30
        )
        
        logger.info(f"Respuesta PlaceToPay/GetNet: status={response.status_code}")
        
        if response.status_code in [200, 201]:
            try:
                payment_response = response.json()
                
                # PlaceToPay retorna processUrl y requestId
                process_url = payment_response.get('processUrl')
                request_id = payment_response.get('requestId')
                
                if process_url and request_id:
                    logger.info(f"✅ Pago creado: requestId={request_id}")
                    return {
                        'payment_id': request_id,
                        'checkout_url': process_url,
                        'payment_data': payment_response
                    }
                else:
                    logger.error(f"PlaceToPay no retornó processUrl o requestId: {payment_response}")
                    return None
            except ValueError:
                logger.error(f"PlaceToPay retornó respuesta no-JSON: {response.text[:500]}")
                return None
        else:
            logger.error(f"Error PlaceToPay/GetNet: status={response.status_code}")
            logger.error(f"Response: {response.text[:1000]}")
            return None
            
    except Exception as e:
        logger.error(f"Excepción al crear pago PlaceToPay/GetNet: {e}", exc_info=True)
        return None

