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
        Obtiene productos desde la base de datos LOCAL
        """
        try:
            from app.models.product_models import Product
            
            query = Product.query.filter_by(is_active=True)
            
            if category:
                # Búsqueda case-insensitive parcial
                query = query.filter(Product.category.ilike(f"%{category}%"))
            
            products_db = query.limit(limit).all()
            
            products_list = []
            for p in products_db:
                # Formato compatible con el frontend existente
                products_list.append({
                    'item_id': str(p.id),
                    'name': p.name,
                    'category': p.category,
                    'category_normalized': p.category,
                    'category_display': p.category.upper() if p.category else 'GENERAL',
                    'price': float(p.price),
                    'cost_price': float(p.cost_price),
                    'quantity': p.stock_quantity,
                    'is_kit': False, # Por ahora todo es producto simple
                    'description': '',
                    'image_id': None
                })
            
            # Ordenar por categoría
            products_list.sort(key=lambda x: (x.get('category_display') or '').lower())
            
            logger.info(f"✅ Obtenidos {len(products_list)} productos desde BD Local")
            return products_list
            
        except Exception as e:
            logger.error(f"Error al obtener productos locales: {e}")
            return []
    
    def get_product(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene un producto específico desde BD Local"""
        try:
            from app.models.product_models import Product
            p = Product.query.get(int(item_id))
            
            if not p:
                return None
                
            return {
                'item_id': str(p.id),
                'name': p.name,
                'category': p.category,
                'price': float(p.price),
                'cost_price': float(p.cost_price),
                'quantity': p.stock_quantity
            }
        except Exception as e:
            logger.error(f"Error al obtener producto local {item_id}: {e}")
            return None
    
    def get_item_kit(self, kit_id: str) -> Optional[Dict[str, Any]]:
        """Compatibilidad: trata kits como productos normales"""
        return self.get_product(kit_id)
    
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
        Crea una venta LOCALMENTE y actualiza inventario
        """
        try:
            from app.models import db, PosSale, PosSaleItem
            from app.models.product_models import Product
            from app.application.services.service_factory import get_inventory_service
            from datetime import datetime
            
            # Obtener employee_id y register_id de la sesión si no se proporcionan
            if not employee_id:
                employee_id = session.get('bartender_id') or session.get('employee_id')
                # Si es un ID numérico de empleado, intentar obtener el nombre
                if employee_id and employee_id.isdigit():
                    from app.models import Employee
                    emp = Employee.query.get(int(employee_id))
                    employee_name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
                else:
                    employee_name = session.get('pos_employee_name', 'Unknown')
            else:
                employee_name = "Unknown" # Deberíamos buscarlo si tenemos el ID
            
            if not register_id:
                register_id = session.get('register_id', '1')
            
            # Mapear tipos de pago
            payment_type_map = {
                'Cash': 'cash',
                'Efectivo': 'cash',
                'Debit': 'debit',
                'Débito': 'debit',
                'Credit': 'credit',
                'Crédito': 'credit'
            }
            normalized_payment = payment_type_map.get(payment_type, 'cash')
            
            # Crear venta
            sale = PosSale(
                sale_time=datetime.now(),
                customer_id=int(customer_id) if customer_id and customer_id.isdigit() else None,
                employee_id=int(employee_id) if employee_id and employee_id.isdigit() else None,
                employee_name=employee_name,
                register_id=register_id,
                payment_type=normalized_payment,
                total_amount=total,
                payment_cash=total if normalized_payment == 'cash' else 0,
                payment_debit=total if normalized_payment == 'debit' else 0,
                payment_credit=total if normalized_payment == 'credit' else 0,
                status='completed'
            )
            
            # Obtener turno actual para asociar fecha
            from app.application.services.service_factory import get_shift_service
            shift_service = get_shift_service()
            shift_status = shift_service.get_current_shift_status()
            if shift_status.is_open:
                sale.shift_date = shift_status.shift_date
            else:
                sale.shift_date = datetime.now().strftime('%Y-%m-%d')

            db.session.add(sale)
            db.session.flush() # Para obtener ID
            
            # Procesar items
            inventory_service = get_inventory_service()
            
            # Mapeo de nombres de barra para inventario
            # Asumimos que el register_id o nombre nos dice qué barra es
            # Por ahora hardcodeamos una lógica simple o usamos 'Barra Principal' por defecto
            barra_name = session.get('pos_register_name', 'Barra Principal')
            if 'Terraza' in barra_name:
                barra_name = 'Barra Terraza'
            elif 'VIP' in barra_name:
                barra_name = 'Barra VIP'
            else:
                barra_name = 'Barra Principal'

            for item in items:
                item_id = item.get('item_id')
                quantity = float(item.get('quantity', 1))
                price = float(item.get('price', 0))
                
                # Buscar producto para obtener nombre correcto
                product = Product.query.get(int(item_id))
                product_name = product.name if product else f"Item {item_id}"
                
                sale_item = PosSaleItem(
                    sale_id=sale.id,
                    product_id=int(item_id) if item_id and item_id.isdigit() else None,
                    product_name=product_name,
                    quantity=quantity,
                    item_price=price,
                    total_price=quantity * price
                )
                db.session.add(sale_item)
                
                # Actualizar inventario (registrar entrega/consumo)
                # Si el producto es un KIT (tiene receta), descontar sus ingredientes
                if product and product.is_kit and product.recipe_items:
                    for recipe_item in product.recipe_items:
                        # Calcular cantidad a descontar
                        # Si la receta define cantidad en "unidades de botella" (ej: 0.09), usamos eso.
                        # Pero si queremos ser precisos con el volumen:
                        # Asumimos que recipe_item.quantity está en la misma unidad que el inventario (botellas)
                        # O implementamos lógica de conversión si recipe_item.quantity fuera en ML.
                        
                        # Por ahora, mantenemos la lógica de que la receta define FRACCIÓN DE BOTELLA.
                        # Si el usuario definió 0.09 para 90cc de una botella de 1L, está bien.
                        # Si la botella es de 750cc, 90cc sería 0.12.
                        
                        # Si queremos soportar que la receta se defina en ML (ej: 90.0),
                        # entonces: deduction = 90.0 / ingredient.volume_ml
                        
                        qty_in_recipe = float(recipe_item.quantity)
                        
                        # DETECCIÓN AUTOMÁTICA DE UNIDAD DE RECETA:
                        # Si la cantidad es > 1.0 (ej: 90, 200), asumimos que son ML y convertimos a botellas.
                        # Si es <= 1.0 (ej: 0.09), asumimos que ya es fracción de botella.
                        # Excepción: Garnish (unidad), Bebidas (unidad o fracción).
                        
                        deduction = 0.0
                        
                        if ingredient.volume_ml and qty_in_recipe > 5.0 and "unidad" not in (ingredient.unit or "").lower():
                            # Caso: Receta en ML (ej: 90cc), Ingrediente con volumen (ej: 750ml)
                            deduction = (qty_in_recipe / ingredient.volume_ml) * float(quantity)
                        else:
                            # Caso: Receta en fracción o unidades (ej: 1 Garnish, 0.2 Bebida)
                            deduction = qty_in_recipe * float(quantity)
                        
                        # Registrar consumo del ingrediente
                        inventory_service.record_delivery(
                            barra=barra_name,
                            product_name=ingredient.name, 
                            quantity=deduction # Ahora pasamos float
                        )
                        
                        # Actualizar stock del ingrediente
                        ingredient.stock_quantity -= deduction
                else:
                    # Si es producto simple, descontar directamente
                    inventory_service.record_delivery(
                        barra=barra_name,
                        product_name=product_name,
                        quantity=int(quantity)
                    )
                    
                    # Actualizar stock del producto
                    if product:
                        product.stock_quantity -= int(quantity)

            db.session.commit()
            
            logger.info(f"✅ Venta LOCAL creada exitosamente: ID={sale.id}")
            
            return {
                'success': True,
                'sale_id': str(sale.id),
                'receipt_code': f"POS-{sale.id}",
                'receipt_url': None, # No generamos URL externa
                'sale_info': { # Info mínima para el frontend
                    'sale_id': str(sale.id),
                    'date': sale.sale_time.isoformat(),
                    'total': total,
                    'items': items
                },
                'message': 'Venta registrada localmente'
            }
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error inesperado al crear venta local: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}',
                'sale_id': None
            }
    
    def get_registers(self) -> List[Dict[str, Any]]:
        """
        Obtiene lista de cajas locales
        """
        # Por ahora definimos las cajas estáticamente, luego podrían ir a BD
        return [
            {'id': '1', 'name': 'Barra Principal'},
            {'id': '2', 'name': 'Barra Terraza'},
            {'id': '3', 'name': 'Barra VIP'},
            {'id': '4', 'name': 'Barra Exterior'},
            {'id': '5', 'name': 'Caja Entrada'},
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

