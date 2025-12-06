"""
Cliente para la API de GetNet
Integración con GetNet para procesamiento de pagos
"""
import logging
import requests
import base64
from datetime import datetime, timedelta
from flask import current_app
import os

logger = logging.getLogger(__name__)


class GetNetClient:
    """Cliente para interactuar con GetNet API"""
    
    def __init__(self, client_id=None, client_secret=None, merchant_id=None):
        if client_id and client_secret:
            self.client_id = client_id
            self.client_secret = client_secret
            self.merchant_id = merchant_id
        else:
            # Intentar obtener desde configuración de Flask
            try:
                self.client_id = current_app.config.get('GETNET_CLIENT_ID') or os.environ.get('GETNET_CLIENT_ID')
                self.client_secret = current_app.config.get('GETNET_CLIENT_SECRET') or os.environ.get('GETNET_CLIENT_SECRET')
                self.merchant_id = current_app.config.get('GETNET_MERCHANT_ID') or os.environ.get('GETNET_MERCHANT_ID')
            except:
                self.client_id = os.environ.get('GETNET_CLIENT_ID')
                self.client_secret = os.environ.get('GETNET_CLIENT_SECRET')
                self.merchant_id = os.environ.get('GETNET_MERCHANT_ID')
        
        # URLs de API GetNet (pueden variar según región)
        self.api_base_url = os.environ.get('GETNET_API_BASE_URL', 'https://api.getnet.com.br')
        self.sandbox_url = os.environ.get('GETNET_SANDBOX_URL', 'https://api-sandbox.getnet.com.br')
        self.use_sandbox = os.environ.get('GETNET_USE_SANDBOX', 'false').lower() == 'true'
        
        if self.use_sandbox:
            self.base_url = self.sandbox_url
        else:
            self.base_url = self.api_base_url
        
        self.access_token = None
        self.token_expires_at = None
        
        if not self.client_id or not self.client_secret:
            logger.warning("⚠️  Credenciales de GetNet no configuradas")
    
    def _get_access_token(self):
        """
        Obtiene un token de acceso OAuth2 de GetNet
        """
        # Si tenemos un token válido, usarlo
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                logger.debug("Usando token de acceso existente")
                return self.access_token
        
        # Intentar obtener token OAuth2
        try:
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            url = f"{self.base_url}/auth/oauth/v2/token"
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'scope': 'oob',
                'grant_type': 'client_credentials'
            }
            
            logger.debug(f"Intentando obtener token de GetNet: {url}")
            response = requests.post(url, headers=headers, data=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                
                if self.access_token:
                    expires_in = token_data.get('expires_in', 3600)
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                    logger.info("✅ Token de acceso GetNet obtenido")
                    return self.access_token
            else:
                logger.error(f"Error al obtener token: {response.status_code} - {response.text}")
            
            logger.warning("⚠️  No se pudo obtener token OAuth2 de GetNet")
            return None
            
        except Exception as e:
            logger.warning(f"⚠️  Error al obtener token: {e}")
            return None
    
    def _get_headers(self):
        """Obtiene headers con autenticación para peticiones a GetNet"""
        token = self._get_access_token()
        
        if token:
            return {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        
        logger.warning("⚠️  No se pudo obtener token OAuth2")
        return {
            'Content-Type': 'application/json'
        }
    
    def create_payment(self, amount, currency='CLP', description='Pago en Club Bimba', order_id=None, customer_data=None):
        """
        Crea un pago en GetNet
        
        Args:
            amount: Monto del pago
            currency: Moneda (CLP, USD, etc.)
            description: Descripción del pago
            order_id: ID único de la orden
            customer_data: Datos del cliente (opcional)
        
        Returns:
            dict: {'success': True, 'payment_id': '...', 'payment_url': '...'} o {'success': False, 'error': '...'}
        """
        if not self.client_id or not self.client_secret:
            return {
                'success': False,
                'error': 'Credenciales de GetNet no configuradas'
            }
        
        try:
            amount_float = float(amount)
            
            # GetNet espera el monto en centavos (o mínima unidad de moneda)
            if currency == 'CLP':
                amount_formatted = int(amount_float)
            else:
                amount_formatted = int(amount_float * 100)
            
            url = f"{self.base_url}/v1/payments/credit"
            
            payload = {
                'seller_id': self.merchant_id or self.client_id,
                'amount': amount_formatted,
                'currency': currency,
                'order': {
                    'order_id': order_id or f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'sales_tax': 0,
                    'product_type': 'service'
                },
                'customer': customer_data or {
                    'customer_id': 'KIOSK_CUSTOMER',
                    'first_name': 'Cliente',
                    'last_name': 'Kiosk'
                }
            }
            
            logger.info(f"Creando pago GetNet: {amount} {currency} - {description}")
            
            headers = self._get_headers()
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            logger.info(f"GetNet Response Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                payment_id = data.get('payment_id') or data.get('id')
                payment_url = data.get('payment_url') or data.get('redirect_url')
                
                if payment_id:
                    logger.info(f"✅ Pago GetNet creado exitosamente: {payment_id}")
                    return {
                        'success': True,
                        'payment_id': str(payment_id),
                        'payment_url': payment_url,
                        'status': data.get('status', 'PENDING'),
                        'data': data
                    }
                else:
                    logger.warning(f"⚠️  Pago creado pero payment_id no disponible: {data}")
                    return {
                        'success': True,
                        'payment_id': None,
                        'payment_url': payment_url,
                        'status': data.get('status', 'PENDING'),
                        'data': data
                    }
            else:
                error_msg = f"Error HTTP al crear pago GetNet: {response.status_code}"
                if hasattr(response, 'text'):
                    error_msg += f" - Respuesta: {response.text}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"Error HTTP al crear pago GetNet: {e}"
            if hasattr(e.response, 'text'):
                error_msg += f" - Respuesta: {e.response.text}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'status_code': e.response.status_code if hasattr(e, 'response') else None
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red al crear pago GetNet: {e}")
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Error inesperado al crear pago GetNet: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_payment_status(self, payment_id):
        """Obtiene el estado de un pago desde la API de GetNet"""
        if not payment_id:
            return {'success': False, 'error': 'payment_id requerido'}
        
        try:
            url = f"{self.base_url}/v1/payments/{payment_id}"
            
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            data = response.json()
            
            status = data.get('status') or data.get('payment_status')
            transaction_id = data.get('transaction_id') or data.get('id')
            
            logger.info(f"Estado del pago {payment_id}: {status}")
            
            return {
                'success': True,
                'status': status,
                'transaction_id': transaction_id,
                'data': data
            }
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"Error HTTP al obtener estado del pago: {e}"
            if hasattr(e.response, 'text'):
                error_msg += f" - Respuesta: {e.response.text}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'status_code': e.response.status_code if hasattr(e, 'response') else None
            }
        except Exception as e:
            logger.error(f"Error al obtener estado del pago: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_qr_payment(self, amount, currency='CLP', description='Pago en Club Bimba', order_id=None, customer_data=None):
        """
        Crea un pago con QR Code en GetNet
        
        Args:
            amount: Monto del pago
            currency: Moneda (CLP, USD, etc.)
            description: Descripción del pago
            order_id: ID único de la orden
            customer_data: Datos del cliente (opcional)
        
        Returns:
            dict: {'success': True, 'payment_id': '...', 'qr_data': '...', 'payment_url': '...'} o {'success': False, 'error': '...'}
        """
        if not self.client_id or not self.client_secret:
            return {
                'success': False,
                'error': 'Credenciales de GetNet no configuradas'
            }
        
        try:
            # Crear pago usando el método existente
            payment_result = self.create_payment(
                amount=amount,
                currency=currency,
                description=description,
                order_id=order_id,
                customer_data=customer_data
            )
            
            if not payment_result.get('success'):
                return payment_result
            
            # Obtener payment_url para generar QR
            payment_url = payment_result.get('payment_url')
            payment_id = payment_result.get('payment_id')
            
            if not payment_url:
                # Si no hay payment_url, intentar obtenerlo del estado del pago
                if payment_id:
                    status_result = self.get_payment_status(payment_id)
                    if status_result.get('success'):
                        payment_url = status_result.get('data', {}).get('payment_url')
            
            if payment_url:
                logger.info(f"✅ Pago QR GetNet creado: {payment_id}")
                return {
                    'success': True,
                    'payment_id': payment_id,
                    'qr_data': payment_url,  # URL para generar QR
                    'payment_url': payment_url,
                    'status': payment_result.get('status', 'PENDING'),
                    'data': payment_result.get('data', {})
                }
            else:
                logger.warning("⚠️  Pago creado pero no hay payment_url para QR")
                return {
                    'success': True,
                    'payment_id': payment_id,
                    'qr_data': None,
                    'payment_url': None,
                    'status': payment_result.get('status', 'PENDING'),
                    'data': payment_result.get('data', {})
                }
            
        except Exception as e:
            logger.error(f"Error al crear pago QR GetNet: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def parse_webhook(self, request_data):
        """Parsea el webhook recibido de GetNet"""
        try:
            if isinstance(request_data, dict):
                data = request_data
            else:
                data = request_data.get_json() if hasattr(request_data, 'get_json') else {}
            
            event_type = data.get('event_type') or data.get('type')
            payment_id = data.get('payment_id') or data.get('id')
            
            logger.info(f"Webhook recibido: event_type={event_type}, payment_id={payment_id}")
            
            return {
                'payment_id': payment_id,
                'event_type': event_type,
                'data': data
            }
            
        except Exception as e:
            logger.error(f"Error al parsear webhook de GetNet: {e}")
            return {
                'payment_id': None,
                'event_type': None,
                'data': {}
            }


