"""
Cliente para la API de SumUp
Conectado con la API real de SumUp
"""
import logging
import requests
import base64
from datetime import datetime, timedelta
from flask import current_app

logger = logging.getLogger(__name__)


class SumUpClient:
    """Cliente para interactuar con SumUp API"""
    
    def __init__(self, client_id=None, client_secret=None):
        if client_id and client_secret:
            self.client_id = client_id
            self.client_secret = client_secret
        else:
            # Intentar obtener desde configuración de Flask
            try:
                self.client_id = current_app.config.get('SUMUP_CLIENT_ID') or os.environ.get('SUMUP_CLIENT_ID')
                self.client_secret = current_app.config.get('SUMUP_CLIENT_SECRET') or os.environ.get('SUMUP_CLIENT_SECRET')
            except:
                self.client_id = os.environ.get('SUMUP_CLIENT_ID')
                self.client_secret = os.environ.get('SUMUP_CLIENT_SECRET')
        
        import os
        self.api_base_url = os.environ.get('SUMUP_API_BASE_URL', 'https://api.sumup.com')
        self.access_token = None
        self.token_expires_at = None
        
        if not self.client_id or not self.client_secret:
            logger.warning("⚠️  Credenciales de SumUp no configuradas")
    
    def _get_access_token(self):
        """
        Obtiene un token de acceso OAuth2 de SumUp
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
            
            endpoints_to_try = [
                f"{self.api_base_url}/token",
                f"{self.api_base_url}/v0.1/token",
                f"{self.api_base_url}/oauth/token"
            ]
            
            for url in endpoints_to_try:
                try:
                    headers = {
                        'Authorization': f'Basic {encoded_credentials}',
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                    
                    data = {
                        'grant_type': 'client_credentials'
                    }
                    
                    logger.debug(f"Intentando obtener token de: {url}")
                    response = requests.post(url, headers=headers, data=data, timeout=10)
                    
                    if response.status_code == 200:
                        token_data = response.json()
                        self.access_token = token_data.get('access_token')
                        
                        if self.access_token:
                            expires_in = token_data.get('expires_in', 3600)
                            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                            logger.info("✅ Token de acceso SumUp obtenido")
                            return self.access_token
                    else:
                        logger.debug(f"Endpoint {url} retornó {response.status_code}: {response.text}")
                        
                except requests.exceptions.RequestException as e:
                    logger.debug(f"Error al intentar {url}: {e}")
                    continue
            
            logger.warning("⚠️  No se pudo obtener token OAuth2 de ningún endpoint")
            return None
            
        except Exception as e:
            logger.warning(f"⚠️  Error al obtener token: {e}")
            return None
    
    def _get_headers(self):
        """Obtiene headers con autenticación para peticiones a SumUp"""
        token = self._get_access_token()
        
        if token:
            return {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        
        logger.warning("⚠️  No se pudo obtener token OAuth2, intentando métodos alternativos")
        
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json'
        }
        
        logger.debug("Usando Basic Auth con credenciales")
        return headers
    
    def create_checkout(self, monto, moneda='CLP', descripcion='Pago en Club Bimba', checkout_reference=None, enable_apple_pay=True):
        """Crea un checkout en SumUp"""
        if not self.client_id or not self.client_secret:
            return {
                'success': False,
                'error': 'Credenciales de SumUp no configuradas'
            }
        
        try:
            amount = float(monto)
            
            if moneda == 'CLP':
                amount_formatted = int(amount)
            else:
                amount_formatted = int(amount * 100)
            
            url = f"{self.api_base_url}/v0.1/checkouts"
            
            payload = {
                'amount': amount_formatted,
                'currency': moneda,
                'description': descripcion
            }
            
            if checkout_reference:
                payload['checkout_reference'] = str(checkout_reference)
            
            if enable_apple_pay:
                try:
                    payload['payment_methods'] = ['card', 'apple_pay', 'google_pay']
                except:
                    pass
            
            import os
            sandbox_code = os.environ.get('SUMUP_SANDBOX_CODE')
            if sandbox_code:
                payload['merchant_code'] = sandbox_code
                logger.info(f"Usando sandbox code: {sandbox_code}")
            
            logger.info(f"Creando checkout SumUp: {amount} {moneda} - {descripcion}")
            
            headers = self._get_headers()
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=15
            )
            
            logger.info(f"SumUp Response Status: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"SumUp Response Error: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            
            checkout_id = data.get('id') or data.get('checkout_id')
            checkout_url = data.get('redirect_url') or data.get('checkout_url') or data.get('url')
            
            if not checkout_url and checkout_id:
                checkout_url = f"https://me.sumup.com/checkout/{checkout_id}"
            
            if checkout_id:
                logger.info(f"✅ Checkout creado exitosamente: {checkout_id}")
                return {
                    'success': True,
                    'checkout_id': str(checkout_id),
                    'checkout_url': checkout_url,
                    'data': data
                }
            else:
                logger.warning(f"⚠️  Checkout creado pero no se encontró ID en respuesta: {data}")
                return {
                    'success': True,
                    'checkout_id': None,
                    'checkout_url': checkout_url,
                    'data': data,
                    'message': 'Checkout creado pero ID no disponible'
                }
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"Error HTTP al crear checkout SumUp: {e}"
            if hasattr(e.response, 'text'):
                error_msg += f" - Respuesta: {e.response.text}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'status_code': e.response.status_code if hasattr(e, 'response') else None
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red al crear checkout SumUp: {e}")
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Error inesperado al crear checkout SumUp: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def parse_webhook(self, request_data):
        """Parsea el webhook recibido de SumUp"""
        try:
            if isinstance(request_data, dict):
                data = request_data
            else:
                data = request_data.get_json() if hasattr(request_data, 'get_json') else {}
            
            event_type = data.get('event_type')
            checkout_id = data.get('id')
            
            logger.info(f"Webhook recibido: event_type={event_type}, checkout_id={checkout_id}")
            
            return {
                'checkout_id': checkout_id,
                'event_type': event_type
            }
            
        except Exception as e:
            logger.error(f"Error al parsear webhook de SumUp: {e}")
            return {
                'checkout_id': None,
                'event_type': None
            }
    
    def get_checkout_status(self, checkout_id):
        """Obtiene el estado de un checkout desde la API de SumUp"""
        if not checkout_id:
            return {'success': False, 'error': 'checkout_id requerido'}
        
        try:
            url = f"{self.api_base_url}/v0.1/checkouts/{checkout_id}"
            
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            data = response.json()
            
            status = data.get('status') or data.get('checkout_status')
            transaction_id = data.get('transaction_id') or data.get('id')
            
            logger.info(f"Estado del checkout {checkout_id}: {status}")
            
            return {
                'success': True,
                'status': status,
                'transaction_id': transaction_id,
                'data': data
            }
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"Error HTTP al obtener estado del checkout: {e}"
            if hasattr(e.response, 'text'):
                error_msg += f" - Respuesta: {e.response.text}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'status_code': e.response.status_code if hasattr(e, 'response') else None
            }
        except Exception as e:
            logger.error(f"Error al obtener estado del checkout: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_terminal_payment(self, amount, currency='CLP', description='Pago en Club Bimba', reference=None, platform='android'):
        """Crea un pago usando Terminal Payments API (Tap to Pay)"""
        if not self.client_id or not self.client_secret:
            return {
                'success': False,
                'error': 'Credenciales de SumUp no configuradas'
            }
        
        try:
            amount_float = float(amount)
            if currency == 'CLP':
                amount_formatted = int(amount_float)
            else:
                amount_formatted = int(amount_float * 100)
            
            url = f"{self.api_base_url}/v0.1/me/transactions"
            
            payload = {
                'amount': amount_formatted,
                'currency': currency,
                'description': description
            }
            
            if reference:
                payload['reference'] = str(reference)
            
            import os
            sandbox_code = os.environ.get('SUMUP_SANDBOX_CODE')
            if sandbox_code:
                payload['merchant_code'] = sandbox_code
            
            platform_name = "iPhone/iPad" if platform == 'ios' else "Android"
            logger.info(f"Creando pago Terminal (Tap to Pay on {platform_name}): {amount} {currency} - {description}")
            
            headers = self._get_headers()
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            logger.info(f"Terminal Payment Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                transaction_id = data.get('id') or data.get('transaction_id')
                
                if transaction_id:
                    logger.info(f"✅ Pago Terminal creado: {transaction_id}")
                    return {
                        'success': True,
                        'transaction_id': str(transaction_id),
                        'status': data.get('status', 'PENDING'),
                        'data': data
                    }
                else:
                    logger.warning("⚠️  Pago creado pero transaction_id no disponible")
                    return {
                        'success': True,
                        'transaction_id': None,
                        'status': data.get('status', 'PENDING'),
                        'data': data
                    }
            else:
                error_msg = f"Error HTTP al crear pago Terminal: {response.status_code}"
                if hasattr(response, 'text'):
                    error_msg += f" - Respuesta: {response.text}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red al crear pago Terminal: {e}")
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Error inesperado al crear pago Terminal: {e}")
            return {
                'success': False,
                'error': str(e)
            }





