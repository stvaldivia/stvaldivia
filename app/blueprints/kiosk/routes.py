"""
Rutas del sistema de Kiosko
"""
from flask import render_template, request, jsonify, redirect, url_for, session, send_file, current_app
from datetime import datetime, timedelta
import logging
import os
from decimal import Decimal
import io
import base64
import barcode
from barcode.writer import ImageWriter
import qrcode

from ...models import db
from ...models.kiosk_models import Pago, PagoItem
from ...infrastructure.external.phppos_kiosk_client import PHPPosKioskClient
from ...infrastructure.external.sumup_client import SumUpClient
from ...infrastructure.external.getnet_client import GetNetClient
from . import kiosk_bp

logger = logging.getLogger(__name__)

# Configuración del kiosko
TICKET_PREFIX = os.environ.get('KIOSK_TICKET_PREFIX', 'B')
KIOSKO_ID = os.environ.get('KIOSKO_ID', 'KIOSKO_1')
PHP_POS_REGISTER_ID = os.environ.get('PHP_POS_REGISTER_ID', '5')

# Inicializar clientes (se inicializan en cada request si es necesario)
def get_phppos_client():
    """Obtiene instancia del cliente PHP POS"""
    return PHPPosKioskClient()

def get_sumup_client():
    """Obtiene instancia del cliente SumUp"""
    return SumUpClient()

def get_getnet_client():
    """Obtiene instancia del cliente GetNet"""
    return GetNetClient()

# Cache de productos (se actualiza periódicamente)
_productos_cache = None
_productos_cache_time = None
CACHE_DURATION = 300  # 5 minutos


def get_productos():
    """Obtiene lista de productos desde PHP POS API"""
    global _productos_cache, _productos_cache_time
    
    # Verificar si el cache es válido
    if _productos_cache and _productos_cache_time:
        if datetime.now() - _productos_cache_time < timedelta(seconds=CACHE_DURATION):
            logger.debug("Usando productos desde cache")
            return _productos_cache
    
    try:
        phppos_client = get_phppos_client()
        items = phppos_client.get_items(limit=1000)
        
        if not items:
            logger.warning("No se obtuvieron productos desde PHP POS. Usando lista de respaldo.")
            return _get_productos_fallback()
        
        # Transformar items de PHP POS al formato esperado por el frontend
        productos = []
        for item in items:
            item_id = str(item.get('item_id') or item.get('id') or '')
            nombre = item.get('name') or item.get('item_name') or 'Producto sin nombre'
            precio = float(item.get('unit_price') or item.get('price') or item.get('cost_price') or 0)
            
            # Obtener categoría y limpiar formato
            categoria_raw = item.get('category') or item.get('category_name') or 'Sin categoría'
            
            # Limpiar categoría: "Barra > Cervezas" -> "Cervezas"
            # También manejar casos como "Ninguno" o categorías sin ">"
            if ' > ' in categoria_raw:
                categoria = categoria_raw.split(' > ')[-1].strip()
            elif categoria_raw == 'Ninguno' or categoria_raw == 'Puerta':
                categoria = 'Otros'
            else:
                categoria = categoria_raw.strip()
            
            # Si no hay categoría válida, usar "Otros"
            if not categoria or categoria == 'Ninguno':
                categoria = 'Otros'
            
            if precio > 0 and item_id:
                productos.append({
                    'id': item_id,
                    'nombre': nombre,
                    'precio': precio,
                    'categoria': categoria
                })
        
        # Actualizar cache (global ya declarado al inicio de la función)
        _productos_cache = productos
        _productos_cache_time = datetime.now()
        
        logger.info(f"✅ Obtenidos {len(productos)} productos desde PHP POS")
        return productos
        
    except Exception as e:
        logger.error(f"Error al obtener productos desde PHP POS: {e}")
        return _get_productos_fallback()


def _get_productos_fallback():
    """Lista de productos de respaldo si falla la conexión con PHP POS"""
    return [
        {'id': '1', 'nombre': 'Piscola', 'precio': 5000, 'categoria': 'Piscolas'},
        {'id': '2', 'nombre': 'Piscola Doble', 'precio': 8000, 'categoria': 'Piscolas'},
        {'id': '3', 'nombre': 'Mojito', 'precio': 6000, 'categoria': 'Cocktails'},
        {'id': '4', 'nombre': 'Piña Colada', 'precio': 7000, 'categoria': 'Cocktails'},
        {'id': '5', 'nombre': 'Cerveza', 'precio': 3000, 'categoria': 'Cervezas'},
        {'id': '6', 'nombre': 'Cerveza Artesanal', 'precio': 5000, 'categoria': 'Cervezas'},
        {'id': '7', 'nombre': 'Agua', 'precio': 2000, 'categoria': 'Sin alcohol'},
        {'id': '8', 'nombre': 'Bebida', 'precio': 2500, 'categoria': 'Sin alcohol'},
    ]


def generate_ticket_code():
    """Genera un código de ticket único (B + sale_id) - Solo usado como respaldo"""
    last_pago = Pago.query.filter(Pago.ticket_code.isnot(None)).order_by(Pago.id.desc()).first()
    
    if last_pago and last_pago.ticket_code:
        try:
            last_num = int(last_pago.ticket_code.replace(TICKET_PREFIX, '').strip())
            next_num = last_num + 1
        except:
            next_num = 1
    else:
        next_num = 1
    
    return f"{TICKET_PREFIX} {next_num}"


# ============================================================================
# RUTAS DEL TÓTEM (Frontend)
# ============================================================================

@kiosk_bp.route('/')
def kiosk_home():
    """Pantalla de inicio del tótem"""
    # Verificar si el kiosko está habilitado
    if not current_app.config.get('KIOSK_ENABLED', False):
        return jsonify({'error': 'El kiosko está desactivado temporalmente'}), 503
    return render_template('kiosk/kiosk_home.html')


@kiosk_bp.route('/products')
def kiosk_products():
    """Pantalla de selección de productos"""
    # Verificar si el kiosko está habilitado
    if not current_app.config.get('KIOSK_ENABLED', False):
        return jsonify({'error': 'El kiosko está desactivado temporalmente'}), 503
    productos = get_productos()
    
    # Agrupar por categorías
    categorias = {}
    for producto in productos:
        cat = producto['categoria']
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append(producto)
    
    # Ordenar categorías de manera lógica
    # Orden preferido: Sin Alcohol primero, luego bebidas alcohólicas, luego otros
    orden_categorias = [
        'Sin Alcohol',
        'Cervezas',
        'Piscos',
        'Vodkas',
        'Rones',
        'Whiskies',
        'Tequilas',
        'Gines',
        'Vermut y Bitters',
        'Vinos y Espumantes',
        'Coctelería',
        'Mocktails',
        'Otros'
    ]
    
    # Crear diccionario ordenado
    categorias_ordenadas = {}
    # Primero agregar categorías en el orden preferido
    for cat in orden_categorias:
        if cat in categorias:
            categorias_ordenadas[cat] = categorias[cat]
    # Luego agregar cualquier categoría que no esté en la lista
    for cat, productos_cat in categorias.items():
        if cat not in categorias_ordenadas:
            categorias_ordenadas[cat] = productos_cat
    
    return render_template('kiosk/kiosk_products.html', categorias=categorias_ordenadas, productos=productos)


@kiosk_bp.route('/checkout', methods=['GET', 'POST'])
def kiosk_checkout():
    """Pantalla de confirmación de pedido"""
    # Verificar si el kiosko está habilitado
    if not current_app.config.get('KIOSK_ENABLED', False):
        return jsonify({'error': 'El kiosko está desactivado temporalmente'}), 503
    if request.method == 'POST':
        carrito_data = request.form.get('carrito')
        if not carrito_data:
            return redirect(url_for('kiosk.kiosk_products'))
        
        session['carrito'] = carrito_data
        return redirect(url_for('kiosk.kiosk_checkout'))
    
    carrito_data = session.get('carrito', '[]')
    return render_template('kiosk/kiosk_checkout.html', carrito_data=carrito_data)


@kiosk_bp.route('/waiting')
def kiosk_waiting():
    """Pantalla de espera de pago"""
    pago_id = request.args.get('pago_id')
    if not pago_id:
        return redirect(url_for('kiosk.kiosk_home'))
    
    return render_template('kiosk/kiosk_waiting_payment.html', pago_id=pago_id)


@kiosk_bp.route('/success')
def kiosk_success():
    """Pantalla de pago aprobado con código/QR y código de barras"""
    pago_id = request.args.get('pago_id')
    if not pago_id:
        return redirect(url_for('kiosk.kiosk_home'))
    
    try:
        pago = Pago.query.get_or_404(int(pago_id))
        
        if pago.estado != 'PAID':
            return redirect(url_for('kiosk.kiosk_waiting', pago_id=pago_id))
        
        return render_template('kiosk/kiosk_success.html', pago=pago)
    except:
        return redirect(url_for('kiosk.kiosk_home'))


@kiosk_bp.route('/api/ticket/barcode/<ticket_code>')
def get_ticket_barcode(ticket_code):
    """Genera una imagen de código de barras para el ticket"""
    try:
        ticket_code_clean = ticket_code.replace(' ', '').replace(TICKET_PREFIX, '').strip()
        
        if ticket_code_clean.startswith(TICKET_PREFIX):
            barcode_text = ticket_code_clean.replace(TICKET_PREFIX, '').strip()
        else:
            barcode_text = ticket_code_clean
        
        logger.debug(f"Generando código de barras: '{barcode_text}' para ticket '{ticket_code}'")
        
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(barcode_text, writer=ImageWriter())
        
        img_buffer = io.BytesIO()
        barcode_instance.write(img_buffer)
        img_buffer.seek(0)
        
        return send_file(img_buffer, mimetype='image/png')
        
    except Exception as e:
        logger.error(f"Error al generar código de barras: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error al generar código de barras: {str(e)}'}), 500


# ============================================================================
# API ENDPOINTS
# ============================================================================

@kiosk_bp.route('/api/pagos/sumup/crear', methods=['POST'])
def api_crear_pago():
    """Crea un nuevo pago"""
    try:
        data = request.get_json()
        
        monto = Decimal(str(data.get('monto', 0)))
        items = data.get('items', [])
        kiosko_id = data.get('kiosko_id', KIOSKO_ID)
        payment_method = data.get('payment_method', 'online')
        
        if monto <= 0:
            return jsonify({'ok': False, 'error': 'Monto inválido'}), 400
        
        if not items:
            return jsonify({'ok': False, 'error': 'No hay items en el pedido'}), 400
        
        pago = Pago(
            monto=monto,
            moneda='CLP',
            estado='PENDING',
            metodo='SUMUP',
            kiosko_id=kiosko_id
        )
        
        db.session.add(pago)
        db.session.flush()
        
        checkout_url = None
        transaction_id = None
        sumup_client = get_sumup_client()
        phppos_client = get_phppos_client()
        
        # Método 1: Terminal Payments
        if payment_method in ['terminal', 'terminal_android', 'terminal_ios']:
            platform = 'ios' if payment_method == 'terminal_ios' else 'android'
            platform_name = "iPhone/iPad" if platform == 'ios' else "Android"
            logger.info(f"Creando pago Terminal (Tap to Pay on {platform_name}) para pago {pago.id}...")
            terminal_result = sumup_client.create_terminal_payment(
                amount=float(monto),
                currency='CLP',
                description=f'Pedido en {kiosko_id}',
                reference=f'KIOSK_{pago.id}',
                platform=platform
            )
            
            if terminal_result.get('success'):
                transaction_id = terminal_result.get('transaction_id')
                pago.sumup_transaction_id = transaction_id
                logger.info(f"✅ Pago Terminal creado: {transaction_id}")
        
        # Método 2: Online Payments
        else:
            checkout_result = sumup_client.create_checkout(
                monto=float(monto),
                moneda='CLP',
                descripcion=f'Pedido en {kiosko_id}',
                checkout_reference=f'KIOSK_{pago.id}',
                enable_apple_pay=True
            )
            
            if checkout_result.get('success'):
                pago.sumup_checkout_id = checkout_result.get('checkout_id')
                checkout_url = checkout_result.get('checkout_url')
                logger.info(f"✅ Checkout SumUp creado: {pago.sumup_checkout_id}")
        
        # Crear items del pago
        for item_data in items:
            item = PagoItem(
                pago_id=pago.id,
                item_id_phppos=str(item_data.get('item_id', '')),
                nombre_item=item_data.get('nombre', ''),
                cantidad=int(item_data.get('cantidad', 1)),
                precio_unitario=Decimal(str(item_data.get('precio', 0))),
                total_linea=Decimal(str(item_data.get('total', 0)))
            )
            db.session.add(item)
        
        db.session.commit()
        
        logger.info(f"Pago creado: ID={pago.id}, Monto={monto}, Método={payment_method}")
        
        return jsonify({
            'ok': True,
            'pago_id': pago.id,
            'checkout_url': checkout_url,
            'transaction_id': transaction_id,
            'payment_method': payment_method
        })
        
    except Exception as e:
        logger.error(f"Error al crear pago: {e}")
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@kiosk_bp.route('/api/pagos/status', methods=['GET'])
def api_pago_status():
    """Obtiene el estado de un pago"""
    try:
        pago_id = request.args.get('pago_id')
        if not pago_id:
            return jsonify({'ok': False, 'error': 'pago_id requerido'}), 400
        
        pago = Pago.query.get_or_404(int(pago_id))
        
        return jsonify({
            'ok': True,
            'estado': pago.estado,
            'ticket_code': pago.ticket_code
        })
        
    except Exception as e:
        logger.error(f"Error al obtener estado de pago: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@kiosk_bp.route('/api/pagos/getnet/crear', methods=['POST'])
def api_crear_pago_getnet():
    """Crea un registro de pago para POS integrado GetNet"""
    # Verificar si GetNet está habilitado
    if not current_app.config.get('GETNET_ENABLED', False):
        return jsonify({'ok': False, 'error': 'GetNet está desactivado temporalmente'}), 503
    try:
        data = request.get_json()
        
        monto = Decimal(str(data.get('monto', 0)))
        items = data.get('items', [])
        kiosko_id = data.get('kiosko_id', KIOSKO_ID)
        
        if monto <= 0:
            return jsonify({'ok': False, 'error': 'Monto inválido'}), 400
        
        if not items:
            return jsonify({'ok': False, 'error': 'No hay items en el pedido'}), 400
        
        # Crear registro de pago (el pago real se procesa en el POS)
        pago = Pago(
            monto=monto,
            moneda='CLP',
            estado='PENDING',
            metodo='GETNET_POS',
            kiosko_id=kiosko_id
        )
        
        db.session.add(pago)
        db.session.flush()
        
        # Agregar items al pago
        for item_data in items:
            cantidad = int(item_data.get('cantidad', 1))
            precio_unitario = Decimal(str(item_data.get('precio', 0)))
            total_linea = precio_unitario * cantidad
            
            pago_item = PagoItem(
                pago_id=pago.id,
                item_id_phppos=str(item_data.get('item_id', '')),
                nombre_item=item_data.get('nombre', ''),
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                total_linea=total_linea
            )
            db.session.add(pago_item)
        
        db.session.commit()
        
        logger.info(f"✅ Registro de pago GetNet POS creado: ID={pago.id}, Monto={monto}")
        
        return jsonify({
            'ok': True,
            'pago_id': pago.id,
            'message': 'Registro creado, esperando respuesta del POS'
        })
            
    except Exception as e:
        logger.error(f"Error al crear registro de pago GetNet: {e}")
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@kiosk_bp.route('/api/pagos/getnet/respuesta', methods=['POST'])
def api_getnet_respuesta_pos():
    """Recibe la respuesta del POS GetNet después de procesar el pago"""
    # Verificar si GetNet está habilitado
    if not current_app.config.get('GETNET_ENABLED', False):
        return jsonify({'ok': False, 'error': 'GetNet está desactivado temporalmente'}), 503
    try:
        data = request.get_json()
        
        pago_id = data.get('pago_id')
        function_code = data.get('function_code')
        response_code = data.get('response_code')
        response_message = data.get('response_message', '')
        voucher_number = data.get('voucher_number')
        success = data.get('success', False)
        
        if not pago_id:
            return jsonify({'ok': False, 'error': 'pago_id requerido'}), 400
        
        pago = Pago.query.get(int(pago_id))
        if not pago:
            return jsonify({'ok': False, 'error': f'Pago {pago_id} no encontrado'}), 404
        
        phppos_client = get_phppos_client()
        
        if success and response_code == 0:
            # Pago aprobado
            pago.estado = 'PAID'
            
            # Guardar información de la transacción
            voucher_number = data.get('voucher_number') or data.get('data', {}).get('Ticket', '')
            authorization_code = data.get('authorization_code') or data.get('data', {}).get('AuthorizationCode', '')
            card_brand = data.get('card_brand') or data.get('data', {}).get('CardBrand', '')
            last4_digits = data.get('last4_digits') or data.get('data', {}).get('Last4Digits', '')
            
            if voucher_number:
                pago.sumup_transaction_id = str(voucher_number)  # Guardar número de ticket/voucher
            
            # Guardar datos adicionales en un campo JSON si existe, o en el log
            logger.info(f"Transacción GetNet - Ticket: {voucher_number}, AuthCode: {authorization_code}, Card: {card_brand}, Last4: {last4_digits}")
            
            pago.updated_at = datetime.utcnow()
            
            # Crear venta en PHP POS
            items_for_phppos = []
            for item in pago.items:
                items_for_phppos.append({
                    'item_id': item.item_id_phppos,
                    'quantity': item.cantidad,
                    'price': float(item.precio_unitario)
                })
            
            logger.info(f"Creando venta en PHP POS para pago {pago.id}...")
            phppos_result = phppos_client.create_sale(
                items=items_for_phppos,
                total=float(pago.monto),
                payment_type='GetNet POS',
                register_id=PHP_POS_REGISTER_ID
            )
            
            logger.info(f"Resultado PHP POS: success={phppos_result.get('success')}, sale_id={phppos_result.get('sale_id')}")
            
            if phppos_result.get('success'):
                sale_id = phppos_result.get('sale_id')
                if sale_id:
                    sale_id = str(sale_id).strip()
                    if sale_id and sale_id != 'None' and sale_id != '' and sale_id != '0':
                        pago.sale_id_phppos = sale_id
                        pago.ticket_code = f"{TICKET_PREFIX} {pago.sale_id_phppos}"
                        logger.info(f"✅ Ticket generado: {pago.ticket_code}")
            
            db.session.commit()
            
            logger.info(f"✅ Pago {pago_id} aprobado - Voucher: {voucher_number}")
            
            return jsonify({
                'ok': True,
                'message': 'Pago procesado exitosamente',
                'ticket_code': pago.ticket_code,
                'voucher_number': voucher_number
            })
        else:
            # Pago rechazado
            pago.estado = 'FAILED'
            pago.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.warning(f"❌ Pago {pago_id} rechazado: {response_message}")
            
            return jsonify({
                'ok': True,
                'message': f'Pago rechazado: {response_message}',
                'rejected': True
            })
            
    except Exception as e:
        logger.error(f"Error al procesar respuesta GetNet POS: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@kiosk_bp.route('/api/pagos/getnet/qr', methods=['POST'])
def api_crear_pago_qr():
    """Crea un pago con QR Code usando GetNet API"""
    # Verificar si GetNet está habilitado
    if not current_app.config.get('GETNET_ENABLED', False):
        return jsonify({'ok': False, 'error': 'GetNet está desactivado temporalmente'}), 503
    try:
        data = request.get_json()
        
        monto = Decimal(str(data.get('monto', 0)))
        items = data.get('items', [])
        kiosko_id = data.get('kiosko_id', KIOSKO_ID)
        
        if monto <= 0:
            return jsonify({'ok': False, 'error': 'Monto inválido'}), 400
        
        if not items:
            return jsonify({'ok': False, 'error': 'No hay items en el pedido'}), 400
        
        # Crear pago con GetNet API
        getnet_client = get_getnet_client()
        
        # Verificar si las credenciales están configuradas
        if not getnet_client.client_id or not getnet_client.client_secret:
            logger.error("Credenciales de GetNet no configuradas")
            return jsonify({
                'ok': False,
                'error': 'Credenciales de GetNet no configuradas. Contacta al administrador.'
            }), 500
        
        order_id = f"KIOSK_{datetime.now().strftime('%Y%m%d%H%M%S')}_{kiosko_id}"
        
        logger.info(f"Creando pago QR GetNet: monto={monto}, order_id={order_id}")
        
        qr_result = getnet_client.create_qr_payment(
            amount=float(monto),
            currency='CLP',
            description='Pago en Club Bimba - Kiosk',
            order_id=order_id,
            customer_data={
                'customer_id': f'KIOSK_{kiosko_id}',
                'first_name': 'Cliente',
                'last_name': 'Kiosk'
            }
        )
        
        if not qr_result.get('success'):
            error_msg = qr_result.get('error', 'Error desconocido al crear pago QR')
            logger.error(f"Error al crear pago QR GetNet: {error_msg}")
            return jsonify({'ok': False, 'error': error_msg}), 500
        
        payment_id = qr_result.get('payment_id')
        qr_data = qr_result.get('qr_data')  # URL para generar QR
        
        if not payment_id:
            return jsonify({'ok': False, 'error': 'No se pudo obtener payment_id de GetNet'}), 500
        
        # Crear registro de pago en la base de datos
        pago = Pago(
            monto=monto,
            moneda='CLP',
            estado='PENDING',
            metodo='GETNET_QR',
            kiosko_id=kiosko_id,
            sumup_transaction_id=str(payment_id)  # Guardar payment_id de GetNet
        )
        
        db.session.add(pago)
        db.session.flush()
        
        # Agregar items al pago
        for item_data in items:
            cantidad = int(item_data.get('cantidad', 1))
            precio_unitario = Decimal(str(item_data.get('precio', 0)))
            total_linea = precio_unitario * cantidad
            
            pago_item = PagoItem(
                pago_id=pago.id,
                item_id_phppos=str(item_data.get('item_id', '')),
                nombre_item=item_data.get('nombre', ''),
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                total_linea=total_linea
            )
            db.session.add(pago_item)
        
        db.session.commit()
        
        logger.info(f"✅ Pago QR GetNet creado: ID={pago.id}, PaymentID={payment_id}")
        
        return jsonify({
            'ok': True,
            'pago_id': pago.id,
            'payment_id': payment_id,
            'qr_data': qr_data,
            'payment_url': qr_result.get('payment_url'),
            'message': 'Pago QR creado exitosamente'
        })
            
    except Exception as e:
        logger.error(f"Error al crear pago QR GetNet: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@kiosk_bp.route('/kiosk/qr-payment/<int:pago_id>')
def kiosk_qr_payment(pago_id):
    """Muestra la pantalla de pago con QR Code"""
    try:
        pago = Pago.query.get_or_404(pago_id)
        
        if pago.metodo != 'GETNET_QR':
            return redirect(url_for('kiosk.kiosk_checkout'))
        
        # Obtener payment_id de GetNet
        payment_id = pago.sumup_transaction_id  # Reutilizamos este campo para payment_id
        
        if not payment_id:
            return redirect(url_for('kiosk.kiosk_checkout'))
        
        # Obtener estado del pago desde GetNet
        getnet_client = get_getnet_client()
        payment_status = getnet_client.get_payment_status(payment_id)
        
        # Generar QR Code
        qr_data = None
        if payment_status.get('success'):
            payment_url = payment_status.get('data', {}).get('payment_url')
            if payment_url:
                qr_data = payment_url
            else:
                # Si no hay payment_url, usar el payment_id para generar QR
                qr_data = f"https://getnet.cl/pay/{payment_id}"
        
        # Generar imagen QR
        qr_image = None
        if qr_data:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convertir a base64 para mostrar en HTML
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            qr_image = base64.b64encode(img_buffer.getvalue()).decode()
        
        return render_template('kiosk/kiosk_qr_payment.html', 
                             pago=pago, 
                             qr_image=qr_image,
                             qr_data=qr_data,
                             payment_id=payment_id)
        
    except Exception as e:
        logger.error(f"Error al mostrar QR payment: {e}")
        return redirect(url_for('kiosk.kiosk_checkout'))


@kiosk_bp.route('/api/pagos/getnet/qr/status/<int:pago_id>', methods=['GET'])
def api_getnet_qr_status(pago_id):
    """Verifica el estado de un pago QR"""
    # Verificar si GetNet está habilitado
    if not current_app.config.get('GETNET_ENABLED', False):
        return jsonify({'ok': False, 'error': 'GetNet está desactivado temporalmente'}), 503
    try:
        pago = Pago.query.get_or_404(pago_id)
        
        if pago.metodo != 'GETNET_QR':
            return jsonify({'ok': False, 'error': 'No es un pago QR'}), 400
        
        payment_id = pago.sumup_transaction_id
        
        if not payment_id:
            return jsonify({'ok': False, 'error': 'Payment ID no encontrado'}), 400
        
        getnet_client = get_getnet_client()
        payment_status = getnet_client.get_payment_status(payment_id)
        
        if not payment_status.get('success'):
            return jsonify({
                'ok': True,
                'status': 'PENDING',
                'paid': False,
                'error': payment_status.get('error')
            })
        
        status = payment_status.get('status', '').upper()
        paid = status in ['PAID', 'APPROVED', 'SUCCESS', 'SUCCESSFUL', 'COMPLETED']
        
        # Si el pago fue aprobado, actualizar en la base de datos
        if paid and pago.estado != 'PAID':
            pago.estado = 'PAID'
            pago.updated_at = datetime.utcnow()
            
            # Crear venta en PHP POS
            phppos_client = get_phppos_client()
            items_for_phppos = []
            for item in pago.items:
                items_for_phppos.append({
                    'item_id': item.item_id_phppos,
                    'quantity': item.cantidad,
                    'price': float(item.precio_unitario)
                })
            
            logger.info(f"Creando venta en PHP POS para pago QR {pago.id}...")
            phppos_result = phppos_client.create_sale(
                items=items_for_phppos,
                total=float(pago.monto),
                payment_type='GetNet QR',
                register_id=PHP_POS_REGISTER_ID
            )
            
            if phppos_result.get('success'):
                sale_id = phppos_result.get('sale_id')
                logger.info(f"✅ Venta creada en PHP POS: {sale_id}")
            
            db.session.commit()
        
        return jsonify({
            'ok': True,
            'status': status,
            'paid': paid,
            'pago_id': pago.id
        })
        
    except Exception as e:
        logger.error(f"Error al verificar estado QR: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@kiosk_bp.route('/api/pagos/getnet/webhook', methods=['POST'])
def api_getnet_webhook():
    """Webhook recibido de GetNet cuando el estado de un pago cambia"""
    # Verificar si GetNet está habilitado
    if not current_app.config.get('GETNET_ENABLED', False):
        return jsonify({'ok': False, 'error': 'GetNet está desactivado temporalmente'}), 503
    try:
        data = request.get_json()
        logger.info(f"Webhook recibido de GetNet: {data}")
        
        getnet_client = get_getnet_client()
        phppos_client = get_phppos_client()
        
        webhook_data = getnet_client.parse_webhook(data)
        
        payment_id = webhook_data.get('payment_id')
        if not payment_id:
            logger.error("payment_id no encontrado en webhook")
            return jsonify({'ok': False, 'error': 'payment_id no encontrado'}), 400
        
        pago = Pago.query.filter_by(sumup_transaction_id=payment_id).first()
        if not pago:
            logger.error(f"Pago no encontrado para payment_id: {payment_id}")
            return jsonify({'ok': False, 'error': f'Pago no encontrado para payment_id: {payment_id}'}), 404
        
        logger.info(f"Verificando estado del pago {payment_id} en GetNet...")
        payment_status = getnet_client.get_payment_status(payment_id)
        
        if not payment_status.get('success'):
            logger.error(f"Error al verificar estado del pago: {payment_status.get('error')}")
            return jsonify({'ok': False, 'error': 'Error al verificar estado del pago'}), 500
        
        status = payment_status.get('status', '').upper()
        transaction_id = payment_status.get('transaction_id')
        
        if status in ['PAID', 'APPROVED', 'SUCCESS', 'SUCCESSFUL', 'COMPLETED']:
            pago.estado = 'PAID'
            if transaction_id:
                pago.sumup_transaction_id = transaction_id
            pago.updated_at = datetime.utcnow()
            
            items_for_phppos = []
            for item in pago.items:
                items_for_phppos.append({
                    'item_id': item.item_id_phppos,
                    'quantity': item.cantidad,
                    'price': float(item.precio_unitario)
                })
            
            logger.info(f"Creando venta en PHP POS para pago {pago.id}...")
            phppos_result = phppos_client.create_sale(
                items=items_for_phppos,
                total=float(pago.monto),
                payment_type='GetNet',
                register_id=PHP_POS_REGISTER_ID
            )
            
            logger.info(f"Resultado PHP POS: success={phppos_result.get('success')}, sale_id={phppos_result.get('sale_id')}")
            
            if phppos_result.get('success'):
                sale_id = phppos_result.get('sale_id')
                if sale_id:
                    sale_id = str(sale_id).strip()
                    if sale_id and sale_id != 'None' and sale_id != '' and sale_id != '0':
                        pago.sale_id_phppos = sale_id
                        pago.ticket_code = f"{TICKET_PREFIX} {pago.sale_id_phppos}"
                        logger.info(f"✅ Ticket generado: {pago.ticket_code}")
            
            db.session.commit()
            return jsonify({'ok': True, 'message': 'Pago procesado', 'ticket_code': pago.ticket_code})
        else:
            pago.estado = 'FAILED'
            pago.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'ok': True, 'message': f'Pago {status}'})
            
    except Exception as e:
        logger.error(f"Error al procesar webhook GetNet: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@kiosk_bp.route('/api/pagos/sumup/webhook', methods=['POST'])
def api_sumup_webhook():
    """Webhook recibido de SumUp cuando el estado de un checkout cambia"""
    try:
        data = request.get_json()
        logger.info(f"Webhook recibido de SumUp: {data}")
        
        sumup_client = get_sumup_client()
        phppos_client = get_phppos_client()
        
        # Verificar si es formato de prueba manual
        if 'pago_id' in data and 'status' in data:
            pago_id = data.get('pago_id')
            status = data.get('status', '').upper()
            transaction_id = data.get('transaction_id')
            
            logger.info(f"Procesando webhook manual: pago_id={pago_id}, status={status}")
            
            pago = Pago.query.get(int(pago_id))
            if not pago:
                return jsonify({'ok': False, 'error': f'Pago {pago_id} no encontrado'}), 404
            
            if status == 'APPROVED':
                pago.estado = 'PAID'
                pago.sumup_transaction_id = transaction_id
                pago.updated_at = datetime.utcnow()
                
                items_for_phppos = []
                for item in pago.items:
                    items_for_phppos.append({
                        'item_id': item.item_id_phppos,
                        'quantity': item.cantidad,
                        'price': float(item.precio_unitario)
                    })
                
                logger.info(f"Creando venta en PHP POS para pago {pago.id}...")
                phppos_result = phppos_client.create_sale(
                    items=items_for_phppos,
                    total=float(pago.monto),
                    payment_type='SumUp',
                    register_id=PHP_POS_REGISTER_ID
                )
                
                logger.info(f"Resultado PHP POS: success={phppos_result.get('success')}, sale_id={phppos_result.get('sale_id')}")
                
                if phppos_result.get('success'):
                    sale_id = phppos_result.get('sale_id')
                    if sale_id:
                        sale_id = str(sale_id).strip()
                        if sale_id and sale_id != 'None' and sale_id != '' and sale_id != '0':
                            pago.sale_id_phppos = sale_id
                            pago.ticket_code = f"{TICKET_PREFIX} {pago.sale_id_phppos}"
                            logger.info(f"✅ Ticket generado: {pago.ticket_code}")
                
                db.session.commit()
                return jsonify({'ok': True, 'message': 'Pago procesado', 'ticket_code': pago.ticket_code})
            else:
                pago.estado = 'FAILED'
                pago.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify({'ok': True, 'message': f'Pago {status}'})
        
        # Formato oficial de SumUp
        webhook_data = sumup_client.parse_webhook(data)
        
        checkout_id = webhook_data.get('checkout_id')
        if not checkout_id:
            logger.error("checkout_id no encontrado en webhook")
            return jsonify({'ok': False, 'error': 'checkout_id no encontrado'}), 400
        
        pago = Pago.query.filter_by(sumup_checkout_id=checkout_id).first()
        if not pago:
            logger.error(f"Pago no encontrado para checkout_id: {checkout_id}")
            return jsonify({'ok': False, 'error': f'Pago no encontrado para checkout_id: {checkout_id}'}), 404
        
        logger.info(f"Verificando estado del checkout {checkout_id} en SumUp...")
        checkout_status = sumup_client.get_checkout_status(checkout_id)
        
        if not checkout_status.get('success'):
            logger.error(f"Error al verificar estado del checkout: {checkout_status.get('error')}")
            return jsonify({'ok': False, 'error': 'Error al verificar estado del checkout'}), 500
        
        status = checkout_status.get('status', '').upper()
        transaction_id = checkout_status.get('transaction_id')
        
        if status in ['PAID', 'APPROVED', 'SUCCESS', 'SUCCESSFUL']:
            pago.estado = 'PAID'
            pago.sumup_transaction_id = transaction_id
            pago.updated_at = datetime.utcnow()
            
            items_for_phppos = []
            for item in pago.items:
                items_for_phppos.append({
                    'item_id': item.item_id_phppos,
                    'quantity': item.cantidad,
                    'price': float(item.precio_unitario)
                })
            
            logger.info(f"Creando venta en PHP POS para pago {pago.id}...")
            phppos_result = phppos_client.create_sale(
                items=items_for_phppos,
                total=float(pago.monto),
                payment_type='SumUp',
                register_id=PHP_POS_REGISTER_ID
            )
            
            logger.info(f"Resultado PHP POS: success={phppos_result.get('success')}, sale_id={phppos_result.get('sale_id')}")
            
            if phppos_result.get('success'):
                sale_id = phppos_result.get('sale_id')
                if sale_id:
                    sale_id = str(sale_id).strip()
                else:
                    sale_id = None
                
                if sale_id and sale_id != 'None' and sale_id != '' and sale_id != '0':
                    pago.sale_id_phppos = sale_id
                    pago.ticket_code = f"{TICKET_PREFIX} {pago.sale_id_phppos}"
                    logger.info(f"✅ Ticket generado: {pago.ticket_code}")
                    
                    try:
                        db.session.commit()
                        logger.info(f"✅ Cambios guardados en BD: sale_id={pago.sale_id_phppos}, ticket_code={pago.ticket_code}")
                    except Exception as commit_error:
                        logger.error(f"❌ Error al guardar cambios en BD: {commit_error}")
                        db.session.rollback()
                        raise
                else:
                    # Usar código secuencial como respaldo
                    max_attempts = 10
                    for attempt in range(max_attempts):
                        temp_code = generate_ticket_code()
                        existing = Pago.query.filter_by(ticket_code=temp_code).first()
                        if not existing:
                            pago.ticket_code = temp_code
                            logger.warning(f"⚠️  Usando código secuencial: {pago.ticket_code}")
                            break
                    else:
                        import time
                        pago.ticket_code = f"{TICKET_PREFIX} {int(time.time())}"
                        logger.error(f"⚠️  Usando código con timestamp: {pago.ticket_code}")
                    
                    try:
                        db.session.commit()
                    except Exception as commit_error:
                        logger.error(f"❌ Error al guardar cambios en BD: {commit_error}")
                        db.session.rollback()
                        raise
            else:
                # Si falla PHP POS, usar código secuencial
                max_attempts = 10
                for attempt in range(max_attempts):
                    temp_code = generate_ticket_code()
                    existing = Pago.query.filter_by(ticket_code=temp_code).first()
                    if not existing:
                        pago.ticket_code = temp_code
                        logger.warning(f"⚠️  Usando código secuencial: {pago.ticket_code}")
                        break
                else:
                    import time
                    pago.ticket_code = f"{TICKET_PREFIX} {int(time.time())}"
                    logger.error(f"⚠️  Usando código con timestamp: {pago.ticket_code}")
                
                try:
                    db.session.commit()
                except Exception as commit_error:
                    logger.error(f"❌ Error al guardar cambios en BD: {commit_error}")
                    db.session.rollback()
                    raise
            
            logger.info(f"✅ Pago aprobado: ID={pago.id}, Ticket={pago.ticket_code}, Sale PHP POS={pago.sale_id_phppos}")
            
            return jsonify({'ok': True, 'message': 'Pago procesado', 'ticket_code': pago.ticket_code, 'sale_id': pago.sale_id_phppos})
        
        elif status in ['FAILED', 'CANCELLED', 'EXPIRED', 'DECLINED']:
            pago.estado = 'FAILED'
            pago.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Pago rechazado: ID={pago.id}, Status={status}")
            return jsonify({'ok': True, 'message': f'Pago rechazado: {status}'})
        
        else:
            logger.info(f"Checkout {checkout_id} en estado pendiente: {status}")
            return jsonify({'ok': True, 'message': f'Estado pendiente: {status}'})
        
    except Exception as e:
        logger.error(f"Error al procesar webhook: {e}")
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@kiosk_bp.route('/api/productos', methods=['GET'])
def api_productos():
    """API para obtener lista de productos"""
    productos = get_productos()
    return jsonify({'ok': True, 'productos': productos})

