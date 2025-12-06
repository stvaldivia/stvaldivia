"""
Servicio para el POS propio
Gestiona ventas usando la API de PHP Point of Sale
"""
import logging
from typing import Dict, List, Optional, Any
from flask import current_app, session
from app.infrastructure.external.phppos_kiosk_client import PHPPosKioskClient
from app.helpers.cache import cached

logger = logging.getLogger(__name__)


class PosService:
    """Servicio para gestionar el POS"""
    
    def __init__(self):
        self.php_pos_client = PHPPosKioskClient()
    
    def get_products(self, category: Optional[str] = None, limit: int = 1000, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Obtiene Item Kits desde PHP POS API (con cache optimizado)
        
        Args:
            category: Categoría a filtrar (opcional)
            limit: Límite de resultados
            use_cache: Si usar cache (default: True)
            
        Returns:
            Lista de Item Kits
        """
        if use_cache:
            from app.helpers.cache import cached
            
            # Usar cache con clave única
            cache_key = f"pos_products|{category}|{limit}"
            from app.helpers.cache import get_cache_key, _cache, _cache_config
            import time
            
            cache_full_key = get_cache_key('pos_products', category, limit)
            cache_ttl = _cache_config.get('pos_products', 300)
            
            # Verificar cache
            if cache_full_key in _cache:
                cached_value, cached_time = _cache[cache_full_key]
                if time.time() - cached_time < cache_ttl:
                    logger.debug("✅ Usando productos desde cache")
                    return cached_value
        
        return self._fetch_products(category, limit)
    
    def _fetch_products(self, category: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Obtiene productos directamente desde la API (sin cache)
        """
        try:
            # Intentar obtener Item Kits desde endpoint específico
            item_kits = self.php_pos_client.get_item_kits(limit=limit)
            
            if item_kits:
                # Normalizar categorías: eliminar prefijos como "Barra >" y usar solo la categoría principal
                for product in item_kits:
                    category = product.get('category_name') or product.get('category') or ''
                    # Si tiene ">", tomar solo la última parte (categoría principal)
                    if '>' in category:
                        category = category.split('>')[-1].strip()
                    # Eliminar "Barra" si está al inicio
                    if category.lower().startswith('barra'):
                        category = category.replace('Barra', '').replace('barra', '').strip()
                        if category.startswith('>'):
                            category = category[1:].strip()
                    # Guardar categoría normalizada
                    product['category_normalized'] = category
                    product['category_display'] = category.upper()  # Para mostrar en mayúsculas
                
                # Ordenar por categoría normalizada
                item_kits.sort(key=lambda x: (x.get('category_normalized') or x.get('category_name') or x.get('category') or '').lower())
                
                logger.info(f"✅ Obtenidos {len(item_kits)} Item Kits desde PHP POS")
                return item_kits
            
            # Si no hay endpoint de Item Kits, buscar en items normales
            # que tengan características de kits (variaciones, paquetes, etc.)
            logger.warning("⚠️  No se encontró endpoint de Item Kits. Buscando en items normales...")
            all_products = self.php_pos_client.get_items(limit=limit, category=category)
            
            # Filtrar items que puedan ser kits (tienen variaciones o son paquetes)
            kits_products = []
            for product in all_products:
                variations = product.get('variations', [])
                unit_variations = product.get('unit_variations', [])
                is_series_package = product.get('is_series_package', False)
                
                # Si tiene variaciones o es un paquete, considerarlo un kit
                if variations or unit_variations or is_series_package:
                    kits_products.append(product)
            
            # Si aún no hay nada, mostrar todos (temporal)
            if not kits_products:
                logger.warning(f"⚠️  No se encontraron Item Kits. Mostrando todos los productos ({len(all_products)} totales)")
                kits_products = all_products
            
            # Normalizar categorías: eliminar prefijos como "Barra >" y usar solo la categoría principal
            for product in kits_products:
                category = product.get('category_name') or product.get('category') or ''
                # Si tiene ">", tomar solo la última parte (categoría principal)
                if '>' in category:
                    category = category.split('>')[-1].strip()
                # Eliminar "Barra" si está al inicio
                if category.lower().startswith('barra'):
                    category = category.replace('Barra', '').replace('barra', '').strip()
                    if category.startswith('>'):
                        category = category[1:].strip()
                # Guardar categoría normalizada
                product['category_normalized'] = category
                product['category_display'] = category.upper()  # Para mostrar en mayúsculas
            
            # Ordenar por categoría normalizada
            kits_products.sort(key=lambda x: (x.get('category_normalized') or x.get('category_name') or x.get('category') or '').lower())
            
            logger.info(f"✅ Obtenidos {len(kits_products)} productos desde PHP POS")
            return kits_products
        except Exception as e:
            logger.error(f"Error al obtener productos: {e}")
            return []
    
    def get_product(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un producto específico desde PHP POS API
        
        Args:
            item_id: ID del producto
            
        Returns:
            Información del producto o None
        """
        try:
            product = self.php_pos_client.get_item(item_id)
            return product
        except Exception as e:
            logger.error(f"Error al obtener producto {item_id}: {e}")
            return None
    
    def get_item_kit(self, kit_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un Item Kit específico desde PHP POS API
        
        Args:
            kit_id: ID del item kit
            
        Returns:
            Información del item kit o None
        """
        try:
            all_kits = self.php_pos_client.get_item_kits(limit=10000)
            for kit in all_kits:
                if str(kit.get('item_kit_id')) == str(kit_id):
                    return kit
            return None
        except Exception as e:
            logger.error(f"Error al obtener item kit {kit_id}: {e}")
            return None
    
    def create_sale(
        self,
        items: List[Dict[str, Any]],
        total: float,
        payment_type: str,
        employee_id: Optional[str] = None,
        register_id: Optional[str] = None,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crea una venta en PHP POS
        
        Args:
            items: Lista de items con formato:
                [
                    {
                        'item_id': '123',
                        'quantity': 2,
                        'price': 5000.0
                    },
                    ...
                ]
            total: Total de la venta
            payment_type: Tipo de pago ('Cash', 'Debit', 'Credit')
            employee_id: ID del empleado
            register_id: ID de la caja
            customer_id: ID del cliente (opcional)
            
        Returns:
            Dict con 'success', 'sale_id', 'error', etc.
        """
        try:
            # Mapear tipos de pago a formato PHP POS
            payment_type_map = {
                'Cash': 'Cash',
                'Efectivo': 'Cash',
                'Debit': 'Debit',
                'Débito': 'Debit',
                'Credit': 'Credit',
                'Crédito': 'Credit'
            }
            
            php_payment_type = payment_type_map.get(payment_type, payment_type)
            
            # Obtener employee_id y register_id de la sesión si no se proporcionan
            if not employee_id:
                employee_id = session.get('bartender_id') or session.get('employee_id')
            
            if not register_id:
                register_id = session.get('register_id')
            
            logger.info(f"Creando venta: total={total}, payment_type={php_payment_type}, items={len(items)}")
            
            # Crear venta en PHP POS
            result = self.php_pos_client.create_sale(
                items=items,
                total=total,
                payment_type=php_payment_type,
                employee_id=employee_id,
                register_id=register_id,
                customer_id=customer_id
            )
            
            if result.get('success'):
                sale_id = result.get('sale_id')
                logger.info(f"✅ Venta creada exitosamente en PHP POS: sale_id={sale_id}")
                
                # Obtener información completa de la venta para impresión
                sale_info = self.php_pos_client.get_sale(sale_id)
                
                return {
                    'success': True,
                    'sale_id': sale_id,
                    'receipt_code': result.get('receipt_code'),
                    'receipt_url': result.get('receipt_url'),
                    'sale_info': sale_info,
                    'message': 'Venta creada exitosamente'
                }
            else:
                error = result.get('error', 'Error desconocido')
                logger.error(f"❌ Error al crear venta: {error}")
                return {
                    'success': False,
                    'error': error,
                    'sale_id': None
                }
                
        except Exception as e:
            logger.error(f"Error inesperado al crear venta: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}',
                'sale_id': None
            }
    
    def get_registers(self) -> List[Dict[str, Any]]:
        """
        Obtiene lista de cajas/registers desde PHP POS API (con cache de 30 minutos)
        
        Returns:
            Lista de registers con 'id' y 'name'
        """
        try:
            api_key = current_app.config.get('API_KEY')
            base_url = current_app.config.get('BASE_API_URL')
            
            if not api_key:
                logger.warning("API_KEY no configurada para obtener registers")
                return []
            
            # Asegurar que base_url no termine en /
            base_url = base_url.rstrip('/')
            url = f"{base_url}/registers"
            headers = {
                "x-api-key": api_key,
                "accept": "application/json"
            }
            
            import requests
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # La API puede devolver un objeto con una lista o directamente una lista
            if isinstance(data, dict):
                registers = data.get('registers', data.get('data', []))
            else:
                registers = data
            
            # Formatear registers para el template
            formatted_registers = []
            for reg in registers:
                if isinstance(reg, dict):
                    reg_id = reg.get('register_id') or reg.get('id')
                    name = reg.get('name') or reg.get('register_name') or f'Caja {reg_id}'
                    # Filtrar solo registros activos (no eliminados)
                    deleted = reg.get('deleted', '0')
                    if deleted == '0' or not deleted:
                        formatted_registers.append({
                            'id': str(reg_id),
                            'name': name
                        })
            
            # Ordenar por ID
            formatted_registers.sort(key=lambda x: int(x['id']) if x['id'].isdigit() else 999)
            
            logger.info(f"✅ Obtenidos {len(formatted_registers)} registers desde PHP POS")
            return formatted_registers
            
        except Exception as e:
            logger.error(f"Error al obtener registers desde PHP POS: {e}")
            # Fallback a lista básica si falla la API
            return [
                {'id': '1', 'name': 'Caja 1'},
                {'id': '2', 'name': 'Caja 2'},
                {'id': '3', 'name': 'Caja 3'},
                {'id': '4', 'name': 'Caja 4'},
            ]
    
    def calculate_total(self, items: List[Dict[str, Any]]) -> float:
        """
        Calcula el total de los items
        
        Args:
            items: Lista de items con 'quantity' y 'price'
            
        Returns:
            Total calculado
        """
        total = 0.0
        for item in items:
            try:
                quantity = float(item.get('quantity', 1))
                price = float(item.get('price', 0))
                total += quantity * price
            except (ValueError, TypeError):
                # Si hay error al convertir, usar subtotal si existe
                try:
                    subtotal = float(item.get('subtotal', 0))
                    total += subtotal
                except (ValueError, TypeError):
                    continue
        return round(total, 2)

