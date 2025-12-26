"""
Rutas para el sistema de Ecommerce - Venta de Entradas Express con GetNet
"""
import logging
import json
from datetime import datetime, timedelta
from flask import render_template, request, jsonify, redirect, url_for, session, flash, current_app
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from flask import Response
from decimal import Decimal
from . import ecommerce_bp
from app.models import db
from app.models.ecommerce_models import Entrada, CheckoutSession
from app.helpers.getnet_web_helper import (
    create_getnet_payment,
    get_getnet_payment_status,
    is_payment_approved,
    extract_payment_info
)
# Intentar también con helper PlaceToPay (GetNet usa PlaceToPay como base)
try:
    from app.helpers.getnet_placepay_helper import create_getnet_payment_placetopay
except ImportError:
    create_getnet_payment_placetopay = None
from app.helpers.rut_validator import validate_rut, format_rut, clean_rut
from app.helpers.email_ticket_helper import send_ticket_email

logger = logging.getLogger(__name__)

# Decorador para eximir funciones de CSRF
# Este decorador marca la función para que sea eximida cuando se registre
def exempt_from_csrf(func):
    """Decorador para marcar función como exenta de CSRF"""
    # Marcar la función para que sea eximida después del registro
    func._csrf_exempt = True
    return func

# Importar rutas de debug (solo en desarrollo)
try:
    from . import debug_routes
except ImportError:
    pass


@ecommerce_bp.route('/')
def index():
    """Página principal de venta de entradas - Muestra eventos disponibles"""
    try:
        from app.models.programacion_models import ProgramacionEvento
        from datetime import date, datetime, timedelta
        
        # Obtener eventos públicos y futuros
        hoy = date.today()
        
        # Buscar eventos publicados y futuros
        eventos = ProgramacionEvento.query.filter(
            ProgramacionEvento.estado_publico == 'publicado',
            ProgramacionEvento.fecha >= hoy,
            ProgramacionEvento.eliminado_en.is_(None)
        ).order_by(ProgramacionEvento.fecha.asc()).limit(20).all()
        
        # Preparar datos de eventos para el template
        eventos_data = []
        for evento in eventos:
            # Obtener precio (usar el primer tier o precio por defecto)
            tiers = evento.get_tiers_precios()
            precio = 10000  # Precio por defecto
            if tiers and len(tiers) > 0:
                # Usar el precio del primer tier o el más bajo
                precios = [t.get('precio', 10000) for t in tiers if t.get('precio')]
                if precios:
                    precio = min(precios)
            
            # Combinar fecha y hora
            evento_fecha = None
            if evento.fecha:
                if evento.horario_apertura_publico:
                    evento_fecha = datetime.combine(evento.fecha, evento.horario_apertura_publico)
                else:
                    evento_fecha = datetime.combine(evento.fecha, datetime.min.time())
            
            eventos_data.append({
                'id': evento.id,
                'nombre': evento.nombre_evento,
                'fecha': evento_fecha,
                'fecha_str': evento.fecha.strftime('%Y-%m-%d') if evento.fecha else '',
                'fecha_display': evento.fecha.strftime('%d/%m/%Y') if evento.fecha else 'Fecha por confirmar',
                'hora': evento.horario_apertura_publico.strftime('%H:%M') if evento.horario_apertura_publico else '20:00',
                'lugar': 'BIMBA' if not evento.descripcion_corta else evento.descripcion_corta[:50],
                'precio': precio,
                'dj_principal': evento.dj_principal,
                'tipo_noche': evento.tipo_noche,
                'descripcion': evento.descripcion_corta or evento.copy_ig_corto or '',
            })
        
        return render_template('ecommerce/index.html', eventos=eventos_data)
        
    except Exception as e:
        logger.error(f"Error al cargar eventos: {e}", exc_info=True)
        # Si hay error, mostrar página sin eventos
        return render_template('ecommerce/index.html', eventos=[])


@ecommerce_bp.route('/checkout', methods=['GET', 'POST'])
@exempt_from_csrf
def checkout():
    """
    Checkout express para venta de entradas
    
    GET: Muestra formulario de checkout
    POST: Procesa datos y crea sesión de checkout
    """
    if request.method == 'GET':
        # Obtener parámetros de la URL (evento, cantidad, precio)
        evento_nombre = request.args.get('evento', 'Evento')
        evento_fecha_str = request.args.get('fecha')
        evento_lugar = request.args.get('lugar', '')
        cantidad = int(request.args.get('cantidad', 1))
        precio_unitario = float(request.args.get('precio', 0))
        
        # Parsear fecha
        evento_fecha = None
        if evento_fecha_str:
            try:
                evento_fecha = datetime.fromisoformat(evento_fecha_str.replace('Z', '+00:00'))
            except:
                evento_fecha = datetime.now() + timedelta(days=7)
        else:
            evento_fecha = datetime.now() + timedelta(days=7)
        
        precio_total = cantidad * precio_unitario
        
        return render_template('ecommerce/checkout.html',
                             evento_nombre=evento_nombre,
                             evento_fecha=evento_fecha,
                             evento_lugar=evento_lugar,
                             cantidad=cantidad,
                             precio_unitario=precio_unitario,
                             precio_total=precio_total)
    
    # POST: Procesar datos del formulario
    try:
        data = request.form
        
        # Validar datos requeridos
        comprador_nombre = data.get('nombre', '').strip()
        comprador_email = data.get('email', '').strip()
        comprador_rut = data.get('rut', '').strip()
        comprador_telefono = data.get('telefono', '').strip()
        evento_nombre = data.get('evento_nombre', '').strip()
        evento_fecha_str = data.get('evento_fecha')
        evento_lugar = data.get('evento_lugar', '').strip()
        cantidad = int(data.get('cantidad', 1))
        precio_unitario = Decimal(data.get('precio_unitario', 0))
        precio_total = Decimal(data.get('precio_total', 0))
        
        # Validaciones básicas (desactivadas temporalmente)
        # if not comprador_nombre or not comprador_email:
        #     flash('Nombre y email son requeridos', 'error')
        #     return redirect(url_for('ecommerce.checkout'))
        
        # Valores por defecto si están vacíos
        if not comprador_nombre:
            comprador_nombre = 'Cliente'
        if not comprador_email:
            comprador_email = 'cliente@ejemplo.com'
        
        if cantidad <= 0 or precio_total <= 0:
            flash('Cantidad y precio deben ser mayores a 0', 'error')
            return redirect(url_for('ecommerce.checkout'))
        
        # Validar RUT si se proporcionó (validación desactivada, solo guardar tal cual)
        # if comprador_rut:
        #     rut_valido, rut_error = validate_rut(comprador_rut)
        #     if not rut_valido:
        #         flash(f'RUT inválido: {rut_error}', 'error')
        #         return redirect(url_for('ecommerce.checkout'))
        # Formatear RUT (desactivado - guardar tal cual se ingresa)
        # comprador_rut = format_rut(clean_rut(comprador_rut))
        
        # Parsear fecha
        try:
            evento_fecha = datetime.fromisoformat(evento_fecha_str.replace('Z', '+00:00'))
        except:
            evento_fecha = datetime.now() + timedelta(days=7)
        
        # Crear sesión de checkout
        checkout_session = CheckoutSession(
            session_id=CheckoutSession.generate_session_id(),
            evento_nombre=evento_nombre,
            evento_fecha=evento_fecha,
            evento_lugar=evento_lugar,
            comprador_nombre=comprador_nombre,
            comprador_email=comprador_email,
            comprador_rut=comprador_rut,
            comprador_telefono=comprador_telefono,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            precio_total=precio_total,
            estado='iniciado',
            expires_at=datetime.utcnow() + timedelta(minutes=30)  # Expira en 30 minutos
        )
        
        db.session.add(checkout_session)
        db.session.commit()
        
        # Guardar session_id en la sesión del usuario
        session['checkout_session_id'] = checkout_session.session_id
        
        # Redirigir a procesamiento de pago
        return redirect(url_for('ecommerce.process_payment', session_id=checkout_session.session_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en checkout: {e}", exc_info=True)
        flash('Error al procesar el checkout. Por favor intenta nuevamente.', 'error')
        return redirect(url_for('ecommerce.checkout'))


@ecommerce_bp.route('/payment/<session_id>', methods=['GET', 'POST'])
def process_payment(session_id):
    """
    Procesa el pago usando GetNet Web Checkout
    
    GET: Redirige a GetNet Web Checkout
    POST: Callback desde GetNet (no usado aquí, se maneja en payment_callback)
    """
    checkout_session = CheckoutSession.query.filter_by(session_id=session_id).first()
    
    if not checkout_session:
        flash('Sesión de checkout no encontrada', 'error')
        return redirect(url_for('ecommerce.index'))
    
    if checkout_session.is_expired():
        checkout_session.estado = 'expirado'
        db.session.commit()
        flash('La sesión de checkout expiró. Por favor inicia nuevamente.', 'error')
        return redirect(url_for('ecommerce.index'))
    
    if checkout_session.estado == 'completado':
        # Ya está completado, redirigir a confirmación
        if checkout_session.entrada_id:
            entrada = Entrada.query.get(checkout_session.entrada_id)
            if entrada:
                return redirect(url_for('ecommerce.confirmation', ticket_code=entrada.ticket_code))
        flash('Error: Sesión completada pero entrada no encontrada', 'error')
        return redirect(url_for('ecommerce.index'))
    
    # Si ya tiene payment_intent_id, verificar estado
    if checkout_session.payment_intent_id:
        payment_status = get_getnet_payment_status(checkout_session.payment_intent_id)
        if payment_status and is_payment_approved(payment_status):
            # Pago ya aprobado, procesar
            return _process_approved_payment(checkout_session, payment_status)
    
    # Crear nuevo payment en GetNet
    try:
        # Preparar datos del cliente
        nombre_parts = checkout_session.comprador_nombre.split(maxsplit=1)
        customer_data = {
            'first_name': nombre_parts[0] if nombre_parts else '',
            'last_name': nombre_parts[1] if len(nombre_parts) > 1 else '',
            'email': checkout_session.comprador_email,
            'phone_number': checkout_session.comprador_telefono or '',
            'document_number': clean_rut(checkout_session.comprador_rut) if checkout_session.comprador_rut else '',
            'city': 'Santiago',
        }
        
        # URLs de callback (GetNet necesita URLs públicas accesibles desde internet)
        public_base_url = current_app.config.get('PUBLIC_BASE_URL')
        if public_base_url:
            # Usar URL pública configurada
            return_url = f"{public_base_url.rstrip('/')}{url_for('ecommerce.payment_callback', session_id=session_id)}"
            cancel_url = f"{public_base_url.rstrip('/')}{url_for('ecommerce.payment_cancelled', session_id=session_id)}"
        else:
            # Fallback a _external=True (puede no funcionar en desarrollo local)
            return_url = url_for('ecommerce.payment_callback', session_id=session_id, _external=True)
            cancel_url = url_for('ecommerce.payment_cancelled', session_id=session_id, _external=True)
        
        logger.info(f"Return URL: {return_url}")
        logger.info(f"Cancel URL: {cancel_url}")
        
        # Metadata adicional
        metadata = {
            'evento_nombre': checkout_session.evento_nombre,
            'evento_fecha': checkout_session.evento_fecha.isoformat() if checkout_session.evento_fecha else '',
        }
        
        # Crear pago en GetNet
        logger.info(f"Intentando crear pago en GetNet para sesión: {session_id}")
        logger.info(f"Monto: {checkout_session.precio_total}, Currency: CLP")
        
        # Intentar primero con método PlaceToPay (estándar de GetNet)
        payment_result = None
        if create_getnet_payment_placetopay:
            try:
                logger.info("Intentando crear pago con método PlaceToPay/GetNet estándar")
                payment_result = create_getnet_payment_placetopay(
                    amount=float(checkout_session.precio_total),
                    currency='CLP',
                    order_id=checkout_session.session_id,
                    customer_data=customer_data,
                    return_url=return_url,
                    cancel_url=cancel_url,
                    metadata=metadata
                )
            except Exception as e:
                logger.warning(f"Error con método PlaceToPay, intentando método alternativo: {e}")
        
        # Si PlaceToPay falla, intentar método alternativo
        if not payment_result:
            try:
                logger.info("Intentando crear pago con método alternativo")
                payment_result = create_getnet_payment(
                    amount=float(checkout_session.precio_total),
                    currency='CLP',
                    order_id=checkout_session.session_id,
                    customer_data=customer_data,
                    return_url=return_url,
                    cancel_url=cancel_url,
                    metadata=metadata
                )
            except Exception as e:
                logger.error(f"Excepción al crear pago en GetNet: {e}", exc_info=True)
                flash('Error al conectar con el sistema de pagos. Por favor intenta más tarde.', 'error')
                return redirect(url_for('ecommerce.checkout',
                    evento=checkout_session.evento_nombre,
                    fecha=checkout_session.evento_fecha.isoformat() if checkout_session.evento_fecha else '',
                    lugar=checkout_session.evento_lugar or '',
                    cantidad=checkout_session.cantidad,
                    precio=float(checkout_session.precio_unitario)))
        
        if not payment_result:
            # Obtener información de configuración para debug
            from app.helpers.getnet_web_helper import get_getnet_config, get_getnet_auth_headers
            config = get_getnet_config()
            headers = get_getnet_auth_headers()
            
            error_details = {
                'session_id': checkout_session.session_id,
                'amount': float(checkout_session.precio_total),
                'api_base_url': config.get('api_base_url'),
                'login_configured': bool(config.get('login')),
                'trankey_configured': bool(config.get('trankey')),
                'headers_obtained': bool(headers),
            }
            
            logger.error("No se pudo crear pago en GetNet - payment_result es None")
            logger.error(f"Checkout session: {checkout_session.session_id}, amount: {checkout_session.precio_total}")
            logger.error(f"Return URL: {return_url}")
            logger.error(f"Cancel URL: {cancel_url}")
            logger.error(f"Config GetNet: api_base_url={config.get('api_base_url')}, login={bool(config.get('login'))}, trankey={bool(config.get('trankey'))}")
            logger.error(f"Headers obtenidos: {bool(headers)}")
            
            # Mensaje de error más descriptivo
            error_msg = 'Error al conectar con el sistema de pagos. '
            if not config.get('login') or not config.get('trankey'):
                error_msg += 'Credenciales de GetNet no configuradas. '
            elif not headers:
                error_msg += 'No se pudieron obtener headers de autenticación. '
            else:
                error_msg += 'Por favor intenta más tarde. '
            
            if current_app.config.get('DEBUG', False):
                error_msg += f' (Debug: {error_details})'
            
            flash(error_msg, 'error')
            
            # Redirigir de vuelta al checkout con los datos
            return redirect(url_for('ecommerce.checkout',
                evento=checkout_session.evento_nombre,
                fecha=checkout_session.evento_fecha.isoformat() if checkout_session.evento_fecha else '',
                lugar=checkout_session.evento_lugar or '',
                cantidad=checkout_session.cantidad,
                precio=float(checkout_session.precio_unitario)))
        
        # Guardar payment_intent_id
        checkout_session.payment_intent_id = payment_result.get('payment_id')
        db.session.commit()
        
        # Redirigir a GetNet Web Checkout
        checkout_url = payment_result.get('checkout_url')
        
        if checkout_url:
            logger.info(f"Redirigiendo a GetNet Web Checkout: session_id={session_id}, payment_id={checkout_session.payment_intent_id}")
            return redirect(checkout_url)
        else:
            flash('Error: No se recibió URL de checkout de GetNet', 'error')
            logger.error(f"GetNet no retornó checkout_url: {payment_result}")
            return redirect(url_for('ecommerce.checkout'))
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al procesar pago con GetNet: {e}", exc_info=True)
        flash('Error al procesar el pago. Por favor intenta más tarde.', 'error')
        return redirect(url_for('ecommerce.checkout'))


def _process_approved_payment(checkout_session: CheckoutSession, payment_status: dict):
    """
    Procesa un pago aprobado: crea la entrada y redirige a confirmación
    
    Args:
        checkout_session: Sesión de checkout
        payment_status: Estado del pago de GetNet
        
    Returns:
        Redirect a confirmación
    """
    try:
        payment_info = extract_payment_info(payment_status)
        
        # Crear entrada
        entrada = Entrada(
            ticket_code=Entrada.generate_ticket_code(),
            evento_nombre=checkout_session.evento_nombre,
            evento_fecha=checkout_session.evento_fecha,
            evento_lugar=checkout_session.evento_lugar,
            comprador_nombre=checkout_session.comprador_nombre,
            comprador_email=checkout_session.comprador_email,
            comprador_rut=checkout_session.comprador_rut,
            comprador_telefono=checkout_session.comprador_telefono,
            cantidad=checkout_session.cantidad,
            precio_unitario=checkout_session.precio_unitario,
            precio_total=checkout_session.precio_total,
            estado_pago='pagado',
            metodo_pago='getnet_web',
            getnet_payment_id=payment_info.get('payment_id'),
            getnet_transaction_id=payment_info.get('transaction_id'),
            getnet_auth_code=payment_info.get('auth_code'),
            paid_at=datetime.utcnow()
        )
        
        db.session.add(entrada)
        db.session.flush()
        
        # Actualizar checkout session
        checkout_session.estado = 'completado'
        checkout_session.completed_at = datetime.utcnow()
        checkout_session.entrada_id = entrada.id
        db.session.commit()
        
        # Enviar email con ticket
        try:
            send_ticket_email(entrada)
        except Exception as email_error:
            logger.warning(f"No se pudo enviar email de ticket: {email_error}")
        
        # Redirigir a confirmación
        return redirect(url_for('ecommerce.confirmation', ticket_code=entrada.ticket_code))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al procesar pago aprobado: {e}", exc_info=True)
        flash('Error al procesar el pago. Por favor contacta con soporte.', 'error')
        return redirect(url_for('ecommerce.index'))


@ecommerce_bp.route('/payment/callback/<session_id>', methods=['GET', 'POST'])
@exempt_from_csrf
def payment_callback(session_id):
    """
    Callback desde GetNet después del pago
    """
    checkout_session = CheckoutSession.query.filter_by(session_id=session_id).first()
    
    if not checkout_session:
        flash('Sesión no encontrada', 'error')
        return redirect(url_for('ecommerce.index'))
    
    # Obtener payment_id de parámetros o usar el guardado
    payment_id = (
        request.args.get('payment_id') or 
        request.form.get('payment_id') or 
        request.args.get('paymentId') or
        checkout_session.payment_intent_id
    )
    
    if not payment_id:
        logger.error(f"Callback sin payment_id: session_id={session_id}")
        flash('Error: No se recibió información del pago', 'error')
        return redirect(url_for('ecommerce.index'))
    
    # Verificar estado del pago con GetNet
    payment_status = get_getnet_payment_status(payment_id)
    
    if not payment_status:
        logger.error(f"No se pudo obtener estado de pago: payment_id={payment_id}")
        flash('Error al verificar el pago. Por favor contacta con soporte.', 'error')
        return redirect(url_for('ecommerce.index'))
    
    # Verificar si el pago está aprobado
    if is_payment_approved(payment_status):
        # Pago aprobado - procesar
        logger.info(f"Pago aprobado: payment_id={payment_id}, session_id={session_id}")
        return _process_approved_payment(checkout_session, payment_status)
    else:
        # Pago rechazado o error
        payment_info = extract_payment_info(payment_status)
        status = payment_info.get('status', 'UNKNOWN')
        
        logger.warning(f"Pago rechazado: payment_id={payment_id}, status={status}")
        
        checkout_session.estado = 'expirado'  # Marcar como expirado para no reutilizar
        db.session.commit()
        
        flash(f'El pago fue {status.lower()}. Por favor intenta nuevamente.', 'error')
        return redirect(url_for('ecommerce.checkout'))


@ecommerce_bp.route('/payment/cancelled/<session_id>')
def payment_cancelled(session_id):
    """Usuario canceló el pago"""
    checkout_session = CheckoutSession.query.filter_by(session_id=session_id).first()
    
    if checkout_session:
        checkout_session.estado = 'expirado'
        db.session.commit()
    
    flash('Pago cancelado', 'info')
    return redirect(url_for('ecommerce.index'))


@ecommerce_bp.route('/confirmation/<ticket_code>')
def confirmation(ticket_code):
    """Página de confirmación con el ticket"""
    entrada = Entrada.query.filter_by(ticket_code=ticket_code).first()
    
    if not entrada:
        flash('Ticket no encontrado', 'error')
        return redirect(url_for('ecommerce.index'))
    
    if entrada.estado_pago != 'pagado':
        flash('Este ticket no está pagado', 'error')
        return redirect(url_for('ecommerce.index'))
    
    # Generar QR code para el ticket
    from app.helpers.qr_ticket_helper import generate_ticket_qr_url
    qr_code = generate_ticket_qr_url(ticket_code)
    
    return render_template('ecommerce/confirmation.html', entrada=entrada, qr_code=qr_code)


@ecommerce_bp.route('/ticket/<ticket_code>')
def view_ticket(ticket_code):
    """Ver ticket (público, para validación)"""
    entrada = Entrada.query.filter_by(ticket_code=ticket_code).first()
    
    if not entrada:
        return jsonify({'error': 'Ticket no encontrado'}), 404
    
    # Generar QR code para el ticket
    from app.helpers.qr_ticket_helper import generate_ticket_qr_url
    qr_code = generate_ticket_qr_url(ticket_code)
    
    return render_template('ecommerce/ticket.html', entrada=entrada, qr_code=qr_code)


@ecommerce_bp.route('/webhook/getnet', methods=['POST'])
@exempt_from_csrf
def getnet_webhook():
    """
    Webhook para recibir notificaciones de GetNet sobre cambios en pagos
    NOTA: Implementar según documentación de GetNet
    """
    try:
        data = request.get_json(silent=True) or {}
        
        # Verificar autenticación del webhook (implementar según GetNet)
        # Por ejemplo: verificar firma, token, etc.
        
        payment_id = data.get('payment_id') or data.get('id')
        event_type = data.get('event_type') or data.get('type')
        status = data.get('status')
        
        logger.info(f"Webhook GetNet recibido: payment_id={payment_id}, event_type={event_type}, status={status}")
        
        if not payment_id:
            logger.warning("Webhook sin payment_id")
            return jsonify({'success': False, 'error': 'payment_id requerido'}), 400
        
        # Buscar checkout session por payment_id
        checkout_session = CheckoutSession.query.filter_by(payment_intent_id=payment_id).first()
        
        if not checkout_session:
            logger.warning(f"Checkout session no encontrada para payment_id={payment_id}")
            return jsonify({'success': False, 'error': 'Sesión no encontrada'}), 404
        
        # Si el pago fue aprobado y aún no está procesado
        if status and is_payment_approved({'status': status}):
            if checkout_session.estado != 'completado':
                payment_status = get_getnet_payment_status(payment_id)
                if payment_status and is_payment_approved(payment_status):
                    _process_approved_payment(checkout_session, payment_status)
                    logger.info(f"Pago procesado desde webhook: payment_id={payment_id}")
        
        return jsonify({'success': True, 'message': 'Webhook procesado'})
        
    except Exception as e:
        logger.error(f"Error en webhook GetNet: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

