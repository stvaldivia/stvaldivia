import logging
from datetime import datetime, timedelta
import uuid
from flask import render_template, request, jsonify, session, redirect, url_for, flash, current_app
from app import CHILE_TZ
from app.blueprints.pos import caja_bp
from app.blueprints.pos.services import pos_service
from app.infrastructure.services.ticket_printer_service import TicketPrinterService
from app.models import PosSale, PosSaleItem, RegisterClose, db
from app.helpers.rate_limiter import rate_limit
from app.helpers.sale_security_validator import (
    validate_session_active, comprehensive_sale_validation,
    validate_payment_type, validate_quantities_reasonable, MAX_QUANTITY_PER_ITEM
)
from app.helpers.sale_audit_logger import SaleAuditLogger
from app.helpers.session_manager import update_session_activity
from app.helpers.shift_manager_compat import get_shift_status
from app.helpers.register_lock_db import is_register_locked, get_register_lock
from app.infrastructure.external.phppos_kiosk_client import PHPPosKioskClient
from app.application.services.service_factory import get_shift_service
from app import socketio

logger = logging.getLogger(__name__)

@caja_bp.route('/ventas', methods=['GET'])
def sales():
    """Pantalla principal del POS - ventas"""
    if not session.get('pos_logged_in'):
        flash("Por favor, inicia sesión primero.", "info")
        return redirect(url_for('caja.login'))
    
    if not session.get('pos_register_id'):
        flash("Por favor, selecciona una caja primero.", "info")
        return redirect(url_for('caja.register'))
    
    # Verificar que la caja esté bloqueada por este cajero
    register_id = session.get('pos_register_id')
    employee_id = session.get('pos_employee_id')
    
    if register_id and employee_id:
        # Normalizar employee_id a string para comparación consistente
        employee_id = str(employee_id) if employee_id else None
        
        if not is_register_locked(register_id):
            flash("La caja no está bloqueada. Por favor, selecciona la caja nuevamente.", "error")
            return redirect(url_for('caja.register'))
        
        lock_info = get_register_lock(register_id)
        if lock_info:
            # Normalizar employee_id del lock para comparación
            lock_employee_id = str(lock_info.get('employee_id', '')) if lock_info.get('employee_id') else ''
            if lock_employee_id != employee_id:
                logger.warning(f"⚠️  Caja {register_id} bloqueada por {lock_employee_id}, pero sesión tiene {employee_id}")
                flash(f"Esta caja está siendo usada por {lock_info.get('employee_name', 'otro cajero')}. Por favor, selecciona otra caja.", "error")
                return redirect(url_for('caja.register'))
    
    # Obtener nombre del cajero para filtrar categorías
    employee_name = session.get('pos_employee_name', '')
    is_david = employee_name and 'David' in employee_name
    
    # Obtener Item Kits desde PHP POS
    products = pos_service.get_products()
    
    # Si el cajero es David, también obtener items normales (no solo kits) de ENTRADAS
    if is_david:
        try:
            php_pos_client = PHPPosKioskClient()
            normal_items = php_pos_client.get_items(limit=1000)
            
            # Normalizar y agregar items normales que sean de ENTRADAS
            for item in normal_items:
                category_raw = item.get('category') or item.get('category_name') or ''
                
                # Normalizar categoría
                if '>' in category_raw:
                    category = category_raw.split('>')[-1].strip()
                elif category_raw.lower() == 'puerta':
                    category = 'Entradas'  # Mapear "Puerta" a "Entradas"
                else:
                    category = category_raw.strip()
                
                # Normalizar: eliminar "Barra" si está al inicio
                if category.lower().startswith('barra'):
                    category = category.replace('Barra', '').replace('barra', '').strip()
                    if category.startswith('>'):
                        category = category[1:].strip()
                
                category_upper = category.upper()
                
                # Solo agregar si es ENTRADAS (o variaciones)
                if category_upper in ['ENTRADAS', 'ENTRADA'] or 'entrada' in category.lower():
                    # Verificar si ya existe en products (para evitar duplicados)
                    item_id = str(item.get('item_id') or item.get('id') or '')
                    exists = False
                    for existing_product in products:
                        existing_id = str(existing_product.get('item_id') or existing_product.get('item_kit_id') or '')
                        if existing_id == item_id:
                            exists = True
                            break
                    
                    if not exists and item_id:
                        # Normalizar categoría y agregar
                        item['category_normalized'] = 'Entradas'
                        item['category_display'] = 'ENTRADAS'
                        item['is_kit'] = False
                        products.append(item)
            
            logger.info(f"✅ Agregados items normales de ENTRADAS para David ({len([p for p in products if not p.get('is_kit', False)])} items)")
        except Exception as e:
            logger.error(f"Error al obtener items normales para David: {e}")
    
    # Asegurar que los precios sean números y normalizar IDs
    for product in products:
        price = product.get('unit_price') or product.get('price') or 0
        try:
            product['price'] = float(price) if price else 0.0
        except (ValueError, TypeError):
            product['price'] = 0.0
        
        # Normalizar ID: usar item_kit_id si existe, sino item_id
        if 'item_kit_id' in product:
            product['item_id'] = str(product['item_kit_id'])  # Para compatibilidad con el carrito
            product['is_kit'] = True
        elif 'item_id' in product:
            product['item_id'] = str(product['item_id'])
            if 'is_kit' not in product:
                product['is_kit'] = False
    
    # Agrupar productos por categoría normalizada
    categorized_products = {}
    for product in products:
        # Usar categoría normalizada si existe, sino normalizar aquí
        category = product.get('category_normalized') or product.get('category_display')
        if not category:
            category = product.get('category_name') or product.get('category') or 'Sin categoría'
            # Normalizar: eliminar "Barra >" y tomar solo la categoría principal
            if '>' in category:
                category = category.split('>')[-1].strip()
            if category.lower().startswith('barra'):
                category = category.replace('Barra', '').replace('barra', '').strip()
                if category.startswith('>'):
                    category = category[1:].strip()
            
            # Mapear "Puerta" a "Entradas"
            if category.lower() == 'puerta':
                category = 'Entradas'
            
            category = category.upper()  # Mostrar en mayúsculas
        
        # Si el cajero es David, solo mostrar productos de la categoría "ENTRADAS"
        if is_david:
            category_upper = category.upper()
            if category_upper not in ['ENTRADAS', 'ENTRADA'] and 'entrada' not in category.lower():
                continue  # Saltar productos que no sean de ENTRADAS
        
        if category not in categorized_products:
            categorized_products[category] = []
        categorized_products[category].append(product)
    
    # Ordenar categorías alfabéticamente
    sorted_categories = sorted(categorized_products.items())
    
    # Obtener carrito de la sesión
    cart = session.get('pos_cart', [])
    
    # Asegurar que los subtotales del carrito sean números
    for item in cart:
        if 'subtotal' in item:
            try:
                item['subtotal'] = float(item['subtotal'])
            except (ValueError, TypeError):
                item['subtotal'] = float(item.get('quantity', 1)) * float(item.get('price', 0))
    
    # Calcular total
    total = pos_service.calculate_total(cart)
    
    # Contar ventas del cajero desde que abrió la caja (usando locked_at)
    employee_sales_count = 0
    try:
        shift_status = get_shift_status()
        shift_date = shift_status.get('shift_date') if shift_status.get('is_open') else None
        
        if employee_id and shift_date and register_id:
            # Normalizar employee_id a string para comparación
            employee_id_str = str(employee_id)
            
            # Obtener información del bloqueo para saber desde cuándo contar
            lock_info = get_register_lock(register_id)
            locked_at = None
            
            if lock_info and lock_info.get('locked_at'):
                try:
                    # locked_at viene en formato ISO string, convertir a datetime
                    locked_at_str = lock_info['locked_at']
                    if isinstance(locked_at_str, str):
                        # Si termina en Z, quitarlo y agregar UTC
                        if locked_at_str.endswith('Z'):
                            locked_at_str = locked_at_str[:-1] + '+00:00'
                        elif '+' not in locked_at_str and 'T' in locked_at_str:
                            locked_at_str = locked_at_str + '+00:00'
                        locked_at = datetime.fromisoformat(locked_at_str)
                        # Convertir a datetime naive para comparación con created_at de la BD
                        if locked_at.tzinfo:
                            locked_at = locked_at.replace(tzinfo=None)
                except Exception as e:
                    logger.warning(f"Error al parsear locked_at: {e}, contando todas las ventas del turno")
                    locked_at = None
            
            # Contar ventas del empleado desde que abrió la caja
            query = PosSale.query.filter(
                PosSale.employee_id == employee_id_str,
                PosSale.shift_date == shift_date,
                PosSale.register_id == str(register_id)
            )
            
            # Si tenemos locked_at, filtrar solo ventas posteriores
            if locked_at:
                query = query.filter(PosSale.created_at >= locked_at)
            
            sales_count = query.count()
            employee_sales_count = sales_count
            
            logger.debug(
                f"Ventas del cajero {employee_id_str} en turno {shift_date} "
                f"desde {locked_at or 'inicio del turno'}: {sales_count}"
            )
    except Exception as e:
        logger.error(f"Error al contar ventas del cajero: {e}", exc_info=True)
        employee_sales_count = 0
    
    return render_template(
        'pos/sales.html',
        categorized_products=sorted_categories,  # Pasar productos agrupados por categoría
        cart=cart,
        total=total,
        employee_name=session.get('pos_employee_name', 'Usuario'),
        register_name=session.get('pos_register_name', 'Caja'),
        employee_sales_count=employee_sales_count
    )


@caja_bp.route('/api/cart/add', methods=['POST'])
def api_add_to_cart():
    """API: Agregar producto al carrito con validaciones de seguridad"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        # Validar sesión activa
        is_valid, error = validate_session_active()
        if not is_valid:
            return jsonify({'success': False, 'error': error}), 401
        
        data = request.get_json()
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 1))
        
        if not item_id:
            return jsonify({'success': False, 'error': 'item_id requerido'}), 400
        
        # Validar cantidad razonable
        if quantity <= 0:
            return jsonify({'success': False, 'error': 'La cantidad debe ser mayor a 0'}), 400
        
        if quantity > MAX_QUANTITY_PER_ITEM:
            return jsonify({
                'success': False,
                'error': f'Cantidad excesiva. Máximo permitido: {MAX_QUANTITY_PER_ITEM}'
            }), 400
        
        # Obtener información del producto desde PHP POS
        # Puede ser un item normal o un item kit
        product = pos_service.get_product(item_id)
        is_kit = False
        
        if not product:
            # Intentar buscar como item kit
            product = pos_service.get_item_kit(item_id)
            is_kit = product is not None
        
        if not product:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        # Obtener precio
        price = float(product.get('unit_price', 0) or product.get('price', 0))
        
        # Normalizar ID y determinar si es kit
        if 'item_kit_id' in product:
            product_id = str(product['item_kit_id'])
            product['item_id'] = product_id  # Para compatibilidad
            is_kit = True
        else:
            product_id = str(product.get('item_id', item_id))
            is_kit = False
        
        # Obtener carrito actual
        cart = session.get('pos_cart', [])
        
        # Verificar si el producto ya está en el carrito - normalizar IDs para comparación
        item_found = False
        item_id_str = str(item_id) if item_id else None
        product_id_str = str(product_id) if product_id else None
        
        for item in cart:
            item_cart_id = str(item.get('item_id', '')) if item.get('item_id') else None
            # Comparar ambos IDs normalizados
            if (item_cart_id and item_cart_id == item_id_str) or (item_cart_id and item_cart_id == product_id_str):
                item['quantity'] += quantity
                item['subtotal'] = item['quantity'] * item.get('price', price)
                # Asegurar que el precio esté actualizado
                if 'price' not in item or not item.get('price'):
                    item['price'] = price
                item_found = True
                break
        
        # Si no está, agregarlo
        if not item_found:
            cart.append({
                'item_id': product_id,  # Usar el ID normalizado
                'name': product.get('name', 'Producto'),
                'quantity': quantity,
                'price': price,
                'subtotal': quantity * price,
                'is_kit': is_kit  # Marcar si es kit
            })
        
        # Guardar carrito en sesión
        session['pos_cart'] = cart
        
        # Calcular nuevo total
        total = pos_service.calculate_total(cart)
        
        return jsonify({
            'success': True,
            'cart': cart,
            'total': total,
            'message': 'Producto agregado al carrito'
        })
        
    except Exception as e:
        logger.error(f"Error al agregar al carrito: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@caja_bp.route('/api/cart/remove', methods=['POST'])
def api_remove_from_cart():
    """API: Remover producto del carrito"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 1))
        
        if not item_id:
            return jsonify({'success': False, 'error': 'item_id requerido'}), 400
        
        cart = session.get('pos_cart', [])
        
        # Buscar y actualizar/remover item - normalizar IDs para comparación
        new_cart = []
        item_id_str = str(item_id) if item_id else None
        
        for item in cart:
            # Normalizar ambos IDs a string para comparación
            item_id_from_cart = str(item.get('item_id', '')) if item.get('item_id') else None
            
            if item_id_from_cart == item_id_str:
                if item.get('quantity', 0) > quantity:
                    item['quantity'] -= quantity
                    item['subtotal'] = item['quantity'] * item.get('price', 0)
                    new_cart.append(item)
                # Si quantity >= item['quantity'], no agregar (remover completamente)
            else:
                new_cart.append(item)
        
        session['pos_cart'] = new_cart
        
        total = pos_service.calculate_total(new_cart)
        
        return jsonify({
            'success': True,
            'cart': new_cart,
            'total': total,
            'message': 'Producto removido del carrito'
        })
        
    except Exception as e:
        logger.error(f"Error al remover del carrito: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@caja_bp.route('/api/cart/clear', methods=['POST'])
def api_clear_cart():
    """API: Limpiar carrito - FORZAR limpieza completa"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    # Forzar limpieza completa del carro
    session['pos_cart'] = []
    session.modified = True  # Asegurar que la sesión se guarde
    
    logger.info(f"🧹 Carro limpiado completamente por API")
    
    return jsonify({
        'success': True,
        'cart': [],
        'total': 0,
        'message': 'Carrito limpiado'
    })


@caja_bp.route('/api/cart', methods=['GET'])
def api_get_cart():
    """API: Obtener carrito actual"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        cart = session.get('pos_cart', [])
        total = pos_service.calculate_total(cart)
        
        return jsonify({
            'success': True,
            'cart': cart,
            'total': total
        })
    except Exception as e:
        logger.error(f"Error al obtener carrito: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@caja_bp.route('/api/sale/create', methods=['POST'])
@rate_limit(max_requests=30, window_seconds=60)  # 30 ventas por minuto
def api_create_sale():
    """API: Crear venta con validaciones de seguridad completas"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    print_status = "no_intentado"
    
    try:
        # Obtener datos de sesión
        register_id = session.get('pos_register_id')
        employee_id = session.get('pos_employee_id')
        employee_name = session.get('pos_employee_name', 'Cajero')
        
        if not register_id or not employee_id:
            return jsonify({'success': False, 'error': 'No hay caja seleccionada. Por favor, selecciona una caja.'}), 400
        
        # Normalizar employee_id a string
        employee_id = str(employee_id) if employee_id else None
        
        # ==========================================
        # VALIDACIONES DE SEGURIDAD COMPLETAS
        # ==========================================
        data = request.get_json()
        payment_type = data.get('payment_type')
        cart = session.get('pos_cart', [])
        
        # Calcular total
        total = pos_service.calculate_total(cart)
        
        # Validación completa de seguridad
        is_valid, error_message, validated_items = comprehensive_sale_validation(
            items=cart,
            total=total,
            payment_type=payment_type,
            employee_id=employee_id,
            register_id=register_id,
            pos_service=pos_service
        )
        
        if not is_valid:
            # Registrar evento de seguridad
            SaleAuditLogger.log_security_event(
                event_type='sale_validation_failed',
                employee_id=employee_id,
                employee_name=employee_name,
                register_id=register_id,
                details={
                    'error': error_message,
                    'cart_size': len(cart),
                    'total': total,
                    'payment_type': payment_type
                },
                severity='warning'
            )
            
            logger.warning(f"⚠️ Validación de seguridad falló: {error_message}")
            
            # Si hay items corregidos (precios actualizados), devolverlos
            if validated_items:
                return jsonify({
                    'success': False,
                    'error': error_message,
                    'cart_updated': True,
                    'corrected_cart': validated_items,
                    'corrected_total': pos_service.calculate_total(validated_items)
                }), 400
            
            return jsonify({'success': False, 'error': error_message}), 400
        
        # Usar items validados (con precios actualizados si fue necesario)
        if validated_items:
            cart = validated_items
            total = pos_service.calculate_total(cart)
        
        # Normalizar tipo de pago (ya validado por comprehensive_sale_validation)
        _, _, payment_type_normalized = validate_payment_type(payment_type)
        
        # Validar que la caja no esté cerrada
        recent_close = RegisterClose.query.filter(
            RegisterClose.register_id == register_id,
            RegisterClose.closed_at >= datetime.now(CHILE_TZ) - timedelta(hours=2)
        ).order_by(RegisterClose.closed_at.desc()).first()
        
        if recent_close:
            shift_service = get_shift_service()
            current_shift = shift_service.get_current_shift()
            
            if current_shift and recent_close.shift_date == current_shift.shift_date:
                return jsonify({
                    'success': False,
                    'error': f'Esta caja fue cerrada el {recent_close.closed_at.strftime("%Y-%m-%d %H:%M")}. No se pueden hacer más ventas en esta caja durante este turno.'
                }), 400
        
        # ==========================================
        # CREAR VENTA CON TRANSACCIÓN ATÓMICA
        # ==========================================
        # Generar ID de venta local único
        from app import CHILE_TZ
        local_sale_id = f"BMB-{datetime.now(CHILE_TZ).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        print_status = "no_intentado"
        
        # Actualizar actividad de sesión
        update_session_activity()
        
        # Guardar venta localmente en base de datos con transacción atómica
        try:
            # Verificar bloqueo antes de crear la venta
            if not is_register_locked(register_id):
                raise Exception("La caja ya no está bloqueada")
            
            lock_info = get_register_lock(register_id)
            if lock_info:
                lock_employee_id = str(lock_info.get('employee_id', '')) if lock_info.get('employee_id') else ''
                if lock_employee_id != employee_id:
                    raise Exception(f"La caja está siendo usada por {lock_info.get('employee_name', 'otro cajero')}")
            
            # Obtener fecha del turno desde Jornada (sistema único)
            from app.models.jornada_models import Jornada
            
            fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
            jornada_actual = Jornada.query.filter_by(
                fecha_jornada=fecha_hoy,
                estado_apertura='abierto'
            ).first()
            
            if jornada_actual and jornada_actual.abierto_en:
                shift_date = jornada_actual.fecha_jornada
                logger.debug(f"✅ Turno encontrado: {shift_date} (abierto en {jornada_actual.abierto_en})")
            else:
                logger.warning(f"⚠️ No hay turno abierto para hoy ({fecha_hoy}) - la venta se guardará sin shift_date")
                shift_date = None
            
            # Calcular montos por método de pago
            payment_cash = float(total) if payment_type_normalized == 'Efectivo' else 0.0
            payment_debit = float(total) if payment_type_normalized == 'Débito' else 0.0
            payment_credit = float(total) if payment_type_normalized == 'Crédito' else 0.0
            
            # Preparar items para la venta
            sale_items_data = []
            for item in cart:
                sale_items_data.append({
                    'product_id': str(item.get('item_id', '')),
                    'product_name': item.get('name', 'Producto'),
                    'quantity': int(item.get('quantity', 1)),
                    'unit_price': float(item.get('price', 0)),
                    'subtotal': float(item.get('subtotal', 0))
                })
            
            # Crear venta local
            local_sale = PosSale(
                sale_id_phppos=None,
                total_amount=float(total),
                payment_type=payment_type_normalized,
                payment_cash=payment_cash,
                payment_debit=payment_debit,
                payment_credit=payment_credit,
                employee_id=employee_id,
                employee_name=employee_name,
                register_id=register_id,
                register_name=session.get('pos_register_name', 'Caja'),
                shift_date=shift_date,
                synced_to_phppos=False
            )
            db.session.add(local_sale)
            db.session.flush()  # Para obtener el ID
            
            # Agregar items
            for item_data in sale_items_data:
                sale_item = PosSaleItem(
                    sale_id=local_sale.id,
                    product_id=item_data['product_id'],
                    product_name=item_data['product_name'],
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    subtotal=item_data['subtotal']
                )
                db.session.add(sale_item)
            
            # Commit de la transacción
            db.session.commit()
            
            # Si llegamos aquí, la transacción fue exitosa
            logger.info(f"✅ Venta guardada localmente (ID local: {local_sale.id}, ID venta: {local_sale_id})")
            
            # Registrar auditoría
            sale_data_for_audit = {
                'total_amount': float(total),
                'payment_type': payment_type_normalized,
                'items': sale_items_data
            }
            SaleAuditLogger.log_sale_created(
                sale_id=local_sale.id,
                sale_data=sale_data_for_audit,
                employee_id=employee_id,
                employee_name=employee_name,
                register_id=register_id
            )
            
            # Auto-imprimir ticket
            try:
                printer_service = TicketPrinterService()
                
                # Si es pago en efectivo, abrir cajón de dinero
                if payment_type_normalized == 'Efectivo':
                    try:
                        drawer_opened = printer_service.open_cash_drawer()
                        if drawer_opened:
                            logger.info(f"✅ Cajón de dinero abierto para venta {local_sale.id} (pago en efectivo)")
                        else:
                            logger.warning(f"⚠️  No se pudo abrir cajón de dinero para venta {local_sale.id}")
                    except Exception as drawer_error:
                        logger.error(f"Error al abrir cajón de dinero: {drawer_error}")
                
                # Preparar datos de venta para impresión
                sale_data = {
                    'sale_id': local_sale_id,
                    'total': float(total),
                    'items': cart,
                    'payment_type': payment_type_normalized,
                    'register_name': session.get('pos_register_name', 'POS'),
                    'employee_name': employee_name
                }
                
                # Imprimir ticket automáticamente
                print_result = printer_service.print_ticket(
                    sale_id=local_sale_id,
                    sale_data=sale_data,
                    items=cart,
                    register_name=session.get('pos_register_name', 'POS'),
                    employee_name=employee_name
                )
                if print_result:
                    logger.info(f"✅ Ticket impreso automáticamente para venta {local_sale.id}")
                    print_status = "impreso"
                else:
                    logger.warning(f"⚠️  No se pudo imprimir ticket para venta {local_sale.id}")
                    print_status = "error_impresion"
            except Exception as e:
                logger.error(f"❌ Error al imprimir ticket automáticamente: {e}", exc_info=True)
                print_status = "error_impresion"
            
            # Notificar en tiempo real al dashboard
            try:
                socketio.emit('pos_sale_created', {
                    'sale': local_sale.to_dict(),
                    'register_id': register_id,
                    'register_name': session.get('pos_register_name')
                }, namespace='/admin')
            except Exception as e:
                logger.warning(f"Error al enviar notificación de venta: {e}")
            
            # Limpiar carrito
            session['pos_cart'] = []
            session.modified = True
            
            return jsonify({
                'success': True,
                'sale_id': local_sale_id,
                'sale_id_local': local_sale.id,
                'message': 'Venta creada exitosamente',
                'ticket_printed': print_status
            })
                    
        except Exception as e:
            logger.error(f"Error al guardar venta localmente: {e}", exc_info=True)
            db.session.rollback()
            
            # Registrar evento de seguridad
            SaleAuditLogger.log_security_event(
                event_type='sale_creation_failed',
                employee_id=employee_id,
                employee_name=employee_name,
                register_id=register_id,
                details={'error': str(e)},
                severity='error'
            )
            
            return jsonify({
                'success': False,
                'error': f'Error al guardar venta: {str(e)}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error al crear venta: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
