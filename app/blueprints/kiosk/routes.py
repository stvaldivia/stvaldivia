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




@kiosk_bp.route('/api/productos', methods=['GET'])
def api_productos():
    """API para obtener lista de productos"""
    productos = get_productos()
    return jsonify({'ok': True, 'productos': productos})

