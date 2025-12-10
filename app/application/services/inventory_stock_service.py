"""
Servicio de Gestión de Inventario de Stock
Maneja toda la lógica de negocio para el inventario de ingredientes:
- Entradas de stock (compras/reposición)
- Salidas por ventas (consumo automático)
- Ajustes y mermas
- Control de ubicaciones (barras, bodega)
"""
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
from decimal import Decimal
from flask import current_app

from app.models import db
from app.models.inventory_stock_models import (
    Ingredient, IngredientStock, Recipe, RecipeIngredient,
    InventoryMovement, IngredientCategory
)
from app.models.product_models import Product
from app.models.pos_models import PosSale, PosSaleItem


class InventoryStockService:
    """
    Servicio principal de gestión de inventario de stock.
    Encapsula toda la lógica de negocio relacionada con ingredientes, recetas y movimientos.
    """
    
    def __init__(self):
        """Inicializa el servicio"""
        pass
    
    # ==========================================
    # GESTIÓN DE INGREDIENTES
    # ==========================================
    
    def create_ingredient(
        self,
        name: str,
        base_unit: str = 'ml',
        category_id: Optional[int] = None,
        package_size: Optional[float] = None,
        package_unit: Optional[str] = None,
        cost_per_unit: float = 0.0,
        description: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Ingredient]]:
        """
        Crea un nuevo ingrediente.
        
        Returns:
            Tuple[bool, str, Optional[Ingredient]]: (éxito, mensaje, ingrediente)
        """
        try:
            # Validar que no exista
            existing = Ingredient.query.filter_by(name=name).first()
            if existing:
                return False, f"Ya existe un ingrediente con el nombre '{name}'", None
            
            ingredient = Ingredient(
                name=name,
                base_unit=base_unit,
                category_id=category_id,
                package_size=Decimal(str(package_size)) if package_size else None,
                package_unit=package_unit,
                cost_per_unit=Decimal(str(cost_per_unit)),
                description=description,
                is_active=True
            )
            
            db.session.add(ingredient)
            db.session.commit()
            
            current_app.logger.info(f"✅ Ingrediente creado: {name} ({base_unit})")
            return True, f"Ingrediente '{name}' creado exitosamente", ingredient
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al crear ingrediente: {e}", exc_info=True)
            return False, f"Error al crear ingrediente: {str(e)}", None
    
    # ==========================================
    # GESTIÓN DE STOCK POR UBICACIÓN
    # ==========================================
    
    def get_stock(self, ingredient_id: int, location: str) -> Optional[IngredientStock]:
        """
        Obtiene el stock de un ingrediente en una ubicación específica.
        Si no existe, retorna None (no crea automáticamente).
        """
        return IngredientStock.query.filter_by(
            ingredient_id=ingredient_id,
            location=location
        ).first()
    
    def get_or_create_stock(self, ingredient_id: int, location: str) -> IngredientStock:
        """
        Obtiene el stock de un ingrediente en una ubicación.
        Si no existe, lo crea con cantidad 0.
        """
        stock = self.get_stock(ingredient_id, location)
        if not stock:
            stock = IngredientStock(
                ingredient_id=ingredient_id,
                location=location,
                quantity=Decimal('0.0')
            )
            db.session.add(stock)
            db.session.flush()
        return stock
    
    def get_all_stock_by_location(self, location: str) -> List[IngredientStock]:
        """Obtiene todo el stock de una ubicación"""
        return IngredientStock.query.filter_by(location=location).all()
    
    # ==========================================
    # ENTRADAS DE STOCK (COMPRAS/REPOSICIÓN)
    # ==========================================
    
    def register_stock_entry(
        self,
        ingredient_id: int,
        location: str,
        quantity: float,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        reason: Optional[str] = None,
        batch_number: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Registra una entrada de stock (compra, reposición).
        
        Args:
            ingredient_id: ID del ingrediente
            location: Ubicación donde entra el stock
            quantity: Cantidad que entra (en unidad base)
            user_id: ID del usuario que registra
            user_name: Nombre del usuario
            reference_type: Tipo de referencia ('purchase', 'transfer', etc.)
            reference_id: ID de la referencia
            reason: Motivo de la entrada
            batch_number: Número de lote/botella (opcional)
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Validar ingrediente
            ingredient = Ingredient.query.get(ingredient_id)
            if not ingredient:
                return False, f"Ingrediente {ingredient_id} no encontrado"
            
            if quantity <= 0:
                return False, "La cantidad debe ser mayor a 0"
            
            # Obtener o crear stock
            stock = self.get_or_create_stock(ingredient_id, location)
            
            # Actualizar cantidad
            stock.quantity += Decimal(str(quantity))
            if batch_number:
                stock.batch_number = batch_number
            
            # Registrar movimiento
            movement = InventoryMovement(
                ingredient_id=ingredient_id,
                location=location,
                movement_type=InventoryMovement.TYPE_ENTRY,
                quantity=Decimal(str(quantity)),
                reference_type=reference_type,
                reference_id=reference_id,
                user_id=user_id,
                user_name=user_name,
                reason=reason or "Entrada de stock"
            )
            db.session.add(movement)
            
            db.session.commit()
            
            current_app.logger.info(
                f"✅ Entrada de stock: {ingredient.name} +{quantity} {ingredient.base_unit} @ {location}"
            )
            return True, f"Entrada de {quantity} {ingredient.base_unit} de {ingredient.name} registrada"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al registrar entrada de stock: {e}", exc_info=True)
            return False, f"Error al registrar entrada: {str(e)}"
    
    # ==========================================
    # CONSUMO POR VENTAS (AUTOMÁTICO)
    # ==========================================
    
    def apply_inventory_for_sale(
        self,
        sale: PosSale,
        location: Optional[str] = None
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Aplica el consumo de inventario para una venta.
        Este es el método principal que se llama cuando se confirma una venta.
        
        Args:
            sale: Objeto PosSale con sus items
            location: Ubicación de donde se descuenta (ej: "barra_principal")
                     Si no se proporciona, se intenta inferir del register_id
        
        Returns:
            Tuple[bool, str, List[Dict]]: (éxito, mensaje, lista de consumos aplicados)
        """
        try:
            if not location:
                # Intentar inferir ubicación del register_id
                location = self._infer_location_from_register(sale.register_id)
            
            if not location:
                return False, "No se pudo determinar la ubicación para descontar inventario", []
            
            consumos_aplicados = []
            
            # Procesar cada item de la venta
            for sale_item in sale.items:
                product_id = sale_item.product_id
                quantity_sold = sale_item.quantity
                
                # Buscar producto
                try:
                    product_id_int = int(product_id)
                except (ValueError, TypeError):
                    # Si no es numérico, buscar por nombre
                    product = Product.query.filter_by(name=sale_item.product_name).first()
                else:
                    product = Product.query.get(product_id_int)
                
                if not product:
                    current_app.logger.warning(
                        f"⚠️ Producto {product_id} ({sale_item.product_name}) no encontrado - saltando inventario"
                    )
                    continue
                
                # Verificar si el producto tiene receta
                recipe = Recipe.query.filter_by(product_id=product.id, is_active=True).first()
                
                if not recipe:
                    # Producto sin receta (ej: entradas) - no afecta inventario
                    continue
                
                # Procesar cada ingrediente de la receta
                recipe_ingredients = RecipeIngredient.query.filter_by(
                    recipe_id=recipe.id
                ).all()
                
                for recipe_ingredient in recipe_ingredients:
                    ingredient_id = recipe_ingredient.ingredient_id
                    quantity_per_portion = recipe_ingredient.quantity_per_portion
                    
                    # Calcular consumo total: cantidad por porción * cantidad vendida
                    total_consumption = float(quantity_per_portion) * quantity_sold
                    
                    # Descontar del stock
                    success, message = self._consume_ingredient(
                        ingredient_id=ingredient_id,
                        location=location,
                        quantity=total_consumption,
                        reference_type='sale',
                        reference_id=str(sale.id),
                        user_id=sale.employee_id,
                        user_name=sale.employee_name,
                        reason=f"Venta #{sale.id}: {quantity_sold}x {product.name}"
                    )
                    
                    if success:
                        consumos_aplicados.append({
                            'ingredient_id': ingredient_id,
                            'ingredient_name': recipe_ingredient.ingredient.name if recipe_ingredient.ingredient else '?',
                            'quantity_consumed': total_consumption,
                            'unit': recipe_ingredient.ingredient.base_unit if recipe_ingredient.ingredient else 'ml',
                            'product_name': product.name,
                            'quantity_sold': quantity_sold
                        })
                    else:
                        current_app.logger.warning(
                            f"⚠️ No se pudo descontar {total_consumption} de ingrediente {ingredient_id}: {message}"
                        )
            
            if consumos_aplicados:
                current_app.logger.info(
                    f"✅ Inventario aplicado para venta #{sale.id}: {len(consumos_aplicados)} consumos"
                )
                return True, f"Inventario aplicado: {len(consumos_aplicados)} ingredientes consumidos", consumos_aplicados
            else:
                return True, "Venta procesada (producto sin receta o sin ingredientes)", []
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al aplicar inventario para venta: {e}", exc_info=True)
            return False, f"Error al aplicar inventario: {str(e)}", []
    
    def _consume_ingredient(
        self,
        ingredient_id: int,
        location: str,
        quantity: float,
        reference_type: str,
        reference_id: str,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Descuenta una cantidad de un ingrediente en una ubicación.
        Método interno usado por apply_inventory_for_sale.
        """
        try:
            # Validar ingrediente
            ingredient = Ingredient.query.get(ingredient_id)
            if not ingredient:
                return False, f"Ingrediente {ingredient_id} no encontrado"
            
            if quantity <= 0:
                return False, "La cantidad debe ser mayor a 0"
            
            # Obtener stock
            stock = self.get_stock(ingredient_id, location)
            if not stock:
                # Si no hay stock registrado, crear con cantidad 0 y permitir negativo
                # (esto permite registrar ventas aunque no haya stock inicial)
                stock = IngredientStock(
                    ingredient_id=ingredient_id,
                    location=location,
                    quantity=Decimal('0.0')
                )
                db.session.add(stock)
                db.session.flush()
                current_app.logger.warning(
                    f"⚠️ Stock no existía para {ingredient.name} @ {location}, creado con 0"
                )
            
            # Descontar (permitir negativo para control de fugas)
            stock.quantity -= Decimal(str(quantity))
            
            # Registrar movimiento negativo
            movement = InventoryMovement(
                ingredient_id=ingredient_id,
                location=location,
                movement_type=InventoryMovement.TYPE_SALE,
                quantity=Decimal(str(-quantity)),  # Negativo = salida
                reference_type=reference_type,
                reference_id=reference_id,
                user_id=user_id,
                user_name=user_name,
                reason=reason or "Consumo por venta"
            )
            db.session.add(movement)
            
            db.session.commit()
            
            return True, "Consumo registrado"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al consumir ingrediente: {e}", exc_info=True)
            return False, f"Error: {str(e)}"
    
    def _infer_location_from_register(self, register_id: str) -> Optional[str]:
        """
        Infiere la ubicación (barra) desde el ID de caja.
        Mapeo: register_id -> location
        """
        # Mapeo básico - se puede extender según necesidad
        location_map = {
            '1': 'barra_principal',
            '2': 'barra_terraza',
            '3': 'barra_vip',
            '4': 'barra_exterior',
        }
        
        # Intentar mapeo directo
        if register_id in location_map:
            return location_map[register_id]
        
        # Si el register_id contiene palabras clave
        register_lower = register_id.lower()
        if 'principal' in register_lower or 'main' in register_lower:
            return 'barra_principal'
        elif 'terraza' in register_lower:
            return 'barra_terraza'
        elif 'vip' in register_lower:
            return 'barra_vip'
        elif 'exterior' in register_lower:
            return 'barra_exterior'
        
        # Por defecto, usar barra principal
        return 'barra_principal'
    
    # ==========================================
    # AJUSTES Y MERMAS
    # ==========================================
    
    def register_adjustment(
        self,
        ingredient_id: int,
        location: str,
        actual_quantity: float,
        user_id: str,
        user_name: str,
        reason: Optional[str] = None,
        movement_type: str = InventoryMovement.TYPE_ADJUSTMENT
    ) -> Tuple[bool, str]:
        """
        Registra un ajuste de inventario (conteo físico).
        
        Args:
            ingredient_id: ID del ingrediente
            location: Ubicación
            actual_quantity: Cantidad física contada
            user_id: Usuario que hace el ajuste
            user_name: Nombre del usuario
            reason: Motivo del ajuste
            movement_type: Tipo de movimiento ('ajuste' o 'merma')
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Obtener stock actual
            stock = self.get_or_create_stock(ingredient_id, location)
            theoretical_quantity = float(stock.quantity)
            
            # Calcular diferencia
            difference = actual_quantity - theoretical_quantity
            
            if abs(difference) < 0.001:  # Prácticamente igual
                return True, "No hay diferencia entre teórico y físico"
            
            # Actualizar stock a cantidad física
            stock.quantity = Decimal(str(actual_quantity))
            
            # Registrar movimiento
            movement = InventoryMovement(
                ingredient_id=ingredient_id,
                location=location,
                movement_type=movement_type,
                quantity=Decimal(str(difference)),  # Positivo si sobra, negativo si falta
                reference_type='count',
                reference_id=None,
                user_id=user_id,
                user_name=user_name,
                reason=reason or f"Ajuste: teórico {theoretical_quantity:.3f} → físico {actual_quantity:.3f}"
            )
            db.session.add(movement)
            
            db.session.commit()
            
            ingredient = Ingredient.query.get(ingredient_id)
            current_app.logger.info(
                f"✅ Ajuste registrado: {ingredient.name if ingredient else '?'} "
                f"@ {location}: {difference:+.3f}"
            )
            
            return True, f"Ajuste registrado: diferencia {difference:+.3f}"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al registrar ajuste: {e}", exc_info=True)
            return False, f"Error al registrar ajuste: {str(e)}"
    
    # ==========================================
    # CONSULTAS Y REPORTES
    # ==========================================
    
    def get_theoretical_consumption(
        self,
        ingredient_id: int,
        location: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> float:
        """
        Calcula el consumo teórico de un ingrediente en un período.
        Suma todos los movimientos de tipo 'venta' (negativos).
        """
        query = db.session.query(
            db.func.sum(InventoryMovement.quantity)
        ).filter_by(
            ingredient_id=ingredient_id,
            location=location,
            movement_type=InventoryMovement.TYPE_SALE
        )
        
        if start_date:
            query = query.filter(InventoryMovement.created_at >= start_date)
        if end_date:
            query = query.filter(InventoryMovement.created_at <= end_date)
        
        result = query.scalar()
        return abs(float(result)) if result else 0.0  # Valor absoluto (son negativos)
    
    def get_stock_summary(self, location: str) -> Dict[str, Any]:
        """
        Obtiene un resumen del stock de una ubicación.
        """
        stocks = self.get_all_stock_by_location(location)
        
        summary = {
            'location': location,
            'total_ingredients': len(stocks),
            'ingredients': []
        }
        
        for stock in stocks:
            ingredient = stock.ingredient
            summary['ingredients'].append({
                'ingredient_id': stock.ingredient_id,
                'ingredient_name': ingredient.name if ingredient else '?',
                'quantity': float(stock.quantity) if stock.quantity else 0.0,
                'unit': ingredient.base_unit if ingredient else 'ml',
                'is_negative': float(stock.quantity) < 0
            })
        
        return summary















