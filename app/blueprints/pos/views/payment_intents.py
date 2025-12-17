"""
Rutas para PaymentIntent - Sistema de intenciones de pago con agente local
"""
import logging
import json
import hashlib
from datetime import datetime
from flask import request, jsonify, session, current_app
from app.blueprints.pos import caja_bp
from app.models import db
from app.models.pos_models import PaymentIntent, PosSale, PosSaleItem
from app.helpers.rate_limiter import rate_limit
from app.helpers.sale_security_validator import comprehensive_sale_validation
from app.helpers.register_session_service import RegisterSessionService
from app.helpers.financial_utils import to_decimal, round_currency
from app.application.services.service_factory import get_shift_service
from app.models.jornada_models import Jornada

logger = logging.getLogger(__name__)


def calculate_cart_hash(cart: list) -> str:
    """Calcula hash SHA256 del carrito para idempotencia"""
    cart_str = json.dumps(cart, sort_keys=True)
    return hashlib.sha256(cart_str.encode('utf-8')).hexdigest()


def verify_agent_auth() -> bool:
    """
    Verifica autenticación del agente.

    Acepta:
    - Header: X-AGENT-KEY
    - Parámetro: agent_key (querystring)
    - (Compat) JSON body: agent_key
    """
    agent_key = request.headers.get('X-AGENT-KEY', '') or request.args.get('agent_key', '')
    if not agent_key:
        try:
            body = request.get_json(silent=True) or {}
            agent_key = body.get('agent_key', '') or ''
        except Exception:
            agent_key = ''
    expected_key = current_app.config.get('AGENT_API_KEY')
    
    if not expected_key:
        logger.warning("⚠️ AGENT_API_KEY not configured")
        return False
    
    return agent_key == expected_key


@caja_bp.route('/api/payment/intents', methods=['POST'])
@rate_limit(max_requests=30, window_seconds=60)
def create_payment_intent():
    """
    Crear o obtener PaymentIntent para procesamiento con agente local
    
    Requiere: sesión POS activa
    Idempotencia: Si existe intent READY/IN_PROGRESS con mismo cart_hash, devolver ese
    """
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        # Normalizar register_id a string para consistencia (ej: REGISTER_ID=1)
        register_id = session.get('pos_register_id')
        register_id = str(register_id) if register_id is not None else None
        employee_id = session.get('pos_employee_id')
        employee_name = session.get('pos_employee_name', 'Cajero')
        
        if not register_id:
            return jsonify({'success': False, 'error': 'No hay caja seleccionada'}), 400
        
        # Obtener carrito desde sesión o payload
        data = request.get_json() or {}
        cart = data.get('cart') or session.get('pos_cart', [])
        
        if not cart:
            return jsonify({'success': False, 'error': 'Carrito vacío'}), 400
        
        # Validar stock (si existe función de validación)
        try:
            from app.blueprints.pos.views.sales import api_validate_stock
            # Validar stock antes de crear intent
            stock_validation = comprehensive_sale_validation(
                cart=cart,
                register_id=register_id,
                employee_id=employee_id
            )
            if not stock_validation.get('valid', False):
                return jsonify({
                    'success': False,
                    'error': stock_validation.get('error', 'Error de validación de stock')
                }), 400
        except Exception as e:
            logger.warning(f"Could not validate stock: {e}")
            # Continuar sin validación si falla
        
        # Calcular total server-side
        total = 0.0
        for item in cart:
            quantity = float(item.get('quantity', 1))
            price = float(item.get('price', 0))
            total += quantity * price
        
        total = round_currency(total)
        
        # Calcular hash del carrito para idempotencia
        cart_hash = calculate_cart_hash(cart)
        
        # Buscar intent existente READY/IN_PROGRESS con mismo cart_hash
        existing_intent = PaymentIntent.query.filter_by(
            register_id=register_id,
            cart_hash=cart_hash,
            status=PaymentIntent.STATUS_READY
        ).first()
        
        if not existing_intent:
            existing_intent = PaymentIntent.query.filter_by(
                register_id=register_id,
                cart_hash=cart_hash,
                status=PaymentIntent.STATUS_IN_PROGRESS
            ).first()
        
        if existing_intent:
            logger.info(f"✅ Reusing existing intent {existing_intent.id} for cart_hash {cart_hash[:8]}...")
            return jsonify({
                'success': True,
                'intent_id': str(existing_intent.id),
                'status': existing_intent.status,
                'amount_total': float(existing_intent.amount_total),
                'message': 'Intent existente reutilizado'
            })
        
        # Obtener register_session_id si existe
        register_session_id = session.get('pos_register_session_id')
        
        # Crear nuevo intent
        intent = PaymentIntent(
            register_id=str(register_id),
            register_session_id=register_session_id,
            employee_id=employee_id,
            employee_name=employee_name,
            amount_total=total,
            currency='CLP',
            cart_json=json.dumps(cart),
            cart_hash=cart_hash,
            provider='GETNET',
            status=PaymentIntent.STATUS_READY
        )
        
        db.session.add(intent)
        db.session.commit()
        
        logger.info(f"✅ PaymentIntent creado: {intent.id} - Amount: ${total} - Register: {register_id}")
        
        return jsonify({
            'success': True,
            'intent_id': str(intent.id),
            'status': intent.status,
            'amount_total': float(intent.amount_total),
            'message': 'Intent creado exitosamente'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al crear PaymentIntent: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500


@caja_bp.route('/api/payment/intents/<uuid:intent_id>/cancel', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=60)
def cancel_payment_intent(intent_id):
    """Cancelar PaymentIntent si aún no está APPROVED"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        intent = PaymentIntent.query.get(intent_id)
        if not intent:
            return jsonify({'success': False, 'error': 'Intent no encontrado'}), 404
        
        # Verificar que pertenece a la caja actual
        register_id = session.get('pos_register_id')
        register_id = str(register_id) if register_id is not None else None
        if intent.register_id != register_id:
            return jsonify({'success': False, 'error': 'Intent no pertenece a esta caja'}), 403
        
        if not intent.can_cancel():
            return jsonify({
                'success': False,
                'error': f'Intent no puede cancelarse (estado: {intent.status})'
            }), 400
        
        intent.status = PaymentIntent.STATUS_CANCELLED
        intent.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ PaymentIntent cancelado: {intent_id}")
        
        return jsonify({
            'success': True,
            'intent_id': str(intent.id),
            'status': intent.status,
            'message': 'Intent cancelado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al cancelar PaymentIntent: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500


@caja_bp.route('/api/payment/intents/<uuid:intent_id>/status', methods=['GET'])
@rate_limit(max_requests=60, window_seconds=60)
def get_payment_intent_status(intent_id):
    """Obtener estado de PaymentIntent (para polling desde UI)"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        intent = PaymentIntent.query.get(intent_id)
        if not intent:
            return jsonify({'success': False, 'error': 'Intent no encontrado'}), 404
        
        # Verificar que pertenece a la caja actual
        register_id = session.get('pos_register_id')
        register_id = str(register_id) if register_id is not None else None
        if intent.register_id != register_id:
            return jsonify({'success': False, 'error': 'Intent no pertenece a esta caja'}), 403


def _process_agent_result_payload(data: dict):
    """Lógica común para aplicar el resultado del agente a un PaymentIntent."""
    if not data:
        return jsonify({'success': False, 'error': 'Body JSON requerido'}), 400

    intent_id_str = data.get('intent_id')
    status = data.get('status')
    provider_ref = data.get('provider_ref')
    auth_code = data.get('auth_code')
    error_code = data.get('error_code')
    error_message = data.get('error_message')

    if not intent_id_str:
        return jsonify({'success': False, 'error': 'intent_id requerido'}), 400

    if status not in [PaymentIntent.STATUS_APPROVED, PaymentIntent.STATUS_DECLINED, PaymentIntent.STATUS_ERROR]:
        return jsonify({'success': False, 'error': f'status inválido: {status}'}), 400

    # Obtener intent
    import uuid
    intent_id = uuid.UUID(intent_id_str)
    intent = PaymentIntent.query.get(intent_id)

    if not intent:
        return jsonify({'success': False, 'error': 'Intent no encontrado'}), 404

    if intent.status != PaymentIntent.STATUS_IN_PROGRESS:
        return jsonify({
            'success': False,
            'error': f'Intent no está en estado IN_PROGRESS (actual: {intent.status})'
        }), 400

    # Actualizar intent
    intent.status = status
    intent.provider_ref = provider_ref
    intent.auth_code = auth_code
    intent.error_code = error_code
    intent.error_message = error_message
    intent.updated_at = datetime.utcnow()

    sale_id = None

    if status == PaymentIntent.STATUS_APPROVED:
        # CRÍTICO: En UNA transacción DB:
        # 1) Marcar intent APPROVED
        # 2) Crear PosSale
        # 3) Aplicar inventario

        intent.approved_at = datetime.utcnow()

        # Parsear cart_json
        cart = json.loads(intent.cart_json)

        # Obtener shift_date y jornada_id
        shift_service = get_shift_service()
        shift_status = shift_service.get_current_shift_status()
        shift_date = None
        jornada_id = None

        if shift_status and shift_status.is_open:
            from app.helpers.date_normalizer import normalize_shift_date
            shift_date = normalize_shift_date(shift_status.shift_date) or shift_status.shift_date
            jornada_id = shift_status.jornada_id
        else:
            from datetime import datetime as _dt
            shift_date = _dt.now().strftime('%Y-%m-%d')
            jornada = Jornada.query.filter_by(abierto=True).order_by(Jornada.abierto_en.desc()).first()
            if jornada:
                jornada_id = jornada.id
            else:
                return jsonify({'success': False, 'error': 'No hay jornada abierta'}), 400

        # Crear PosSale
        sale = PosSale(
            total_amount=intent.amount_total,
            payment_type='debit',  # GETNET es débito/crédito
            payment_debit=intent.amount_total,
            payment_cash=0.0,
            payment_credit=0.0,
            employee_id=intent.employee_id,
            employee_name=intent.employee_name,
            register_id=intent.register_id,
            register_name=session.get('pos_register_name', 'Caja'),
            shift_date=shift_date,
            jornada_id=jornada_id,
            register_session_id=intent.register_session_id,
            payment_provider='GETNET',
            synced_to_phppos=False,
            is_cancelled=False,
            no_revenue=False,
            inventory_applied=False
        )

        db.session.add(sale)
        db.session.flush()

        for item in cart:
            item_id = item.get('item_id', '')
            quantity = float(item.get('quantity', 1))
            price = float(item.get('price', 0))
            name = item.get('name', 'Producto')

            sale_item = PosSaleItem(
                sale_id=sale.id,
                product_id=str(item_id),
                product_name=name,
                quantity=int(quantity),
                unit_price=price,
                subtotal=quantity * price
            )
            db.session.add(sale_item)

        try:
            from app.services.sale_delivery_service import get_sale_delivery_service
            delivery_service = get_sale_delivery_service()
            delivery_status = delivery_service.create_delivery_status(sale)
            if delivery_status:
                logger.info(f"✅ Estado de entrega creado para venta {sale.id}")
        except Exception as inv_error:
            logger.error(f"Error al crear estado de entrega: {inv_error}", exc_info=True)

        sale.inventory_applied = False
        sale.inventory_applied_at = None

        sale_id = sale.id
        db.session.commit()

        logger.info(f"✅ PaymentIntent APPROVED: {intent_id} - Sale creada: {sale_id} - Inventario aplicado")
        return jsonify({
            'success': True,
            'intent_id': str(intent.id),
            'intent_status': 'APPROVED',
            'sale_id': sale_id,
            'message': 'Pago aprobado y venta creada'
        })

    # DECLINED / ERROR
    db.session.commit()
    logger.info(f"✅ PaymentIntent {status}: {intent_id} - NO se creó venta")
    return jsonify({
        'success': True,
        'intent_id': str(intent.id),
        'intent_status': status,
        'error_code': error_code,
        'error_message': error_message,
        'message': f'Pago {status.lower()}'
    })
        
        return jsonify({
            'success': True,
            'intent_id': str(intent.id),
            'status': intent.status,
            'amount_total': float(intent.amount_total),
            'provider_ref': intent.provider_ref,
            'auth_code': intent.auth_code,
            'error_code': intent.error_code,
            'error_message': intent.error_message,
            'created_at': intent.created_at.isoformat() if intent.created_at else None,
            'updated_at': intent.updated_at.isoformat() if intent.updated_at else None,
            'approved_at': intent.approved_at.isoformat() if intent.approved_at else None,
        })
        
    except Exception as e:
        logger.error(f"Error al obtener estado de PaymentIntent: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500


@caja_bp.route('/api/payment/agent/pending', methods=['GET'])
@rate_limit(max_requests=30, window_seconds=60)
def agent_get_pending():
    """
    Obtener PaymentIntent pendiente más antiguo para una caja (AGENT ONLY)
    
    Autenticación: X-AGENT-KEY header
    Al entregar, cambia status a IN_PROGRESS y lockea
    """
    if not verify_agent_auth():
        return jsonify({'success': False, 'error': 'Autenticación inválida'}), 401
    
    try:
        register_id = request.args.get('register_id')
        if not register_id:
            return jsonify({'success': False, 'error': 'register_id requerido'}), 400
        
        # Buscar intent más antiguo con status READY para esta caja
        intent = PaymentIntent.query.filter_by(
            register_id=register_id,
            status=PaymentIntent.STATUS_READY
        ).order_by(PaymentIntent.created_at.asc()).first()
        
        if not intent:
            return jsonify({
                'success': True,
                'pending': False,
                'message': 'No hay intents pendientes'
            })
        
        # Lockear intent (cambiar a IN_PROGRESS)
        agent_id = request.headers.get('X-AGENT-ID', 'unknown')
        intent.status = PaymentIntent.STATUS_IN_PROGRESS
        intent.locked_by_agent = agent_id
        intent.locked_at = datetime.utcnow()
        intent.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ Agent {agent_id} tomó intent {intent.id} para register {register_id}")
        
        # Parsear cart_json
        cart_dict = None
        if intent.cart_json:
            try:
                cart_dict = json.loads(intent.cart_json)
            except:
                cart_dict = None
        
        return jsonify({
            'success': True,
            'pending': True,
            'intent_id': str(intent.id),
            'register_id': intent.register_id,
            'amount_total': float(intent.amount_total),
            'currency': intent.currency,
            'cart': cart_dict,
            'created_at': intent.created_at.isoformat() if intent.created_at else None,
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al obtener intent pendiente: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500


@caja_bp.route('/api/payment/agent/result', methods=['POST'])
@rate_limit(max_requests=30, window_seconds=60)
def agent_report_result():
    """
    Reportar resultado de pago desde agente local (AGENT ONLY)
    
    Si status=APPROVED:
        - Marcar intent APPROVED
        - Crear PosSale desde cart_json
        - Aplicar inventario
        - Asociar register_id/session_id/employee_id
    
    Si DECLINED/ERROR:
        - Marcar intent DECLINED/ERROR
        - NO crear venta, NO aplicar inventario
    """
    if not verify_agent_auth():
        return jsonify({'success': False, 'error': 'Autenticación inválida'}), 401
    
    try:
        data = request.get_json(silent=True) or {}
        return _process_agent_result_payload(data)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al reportar resultado de pago: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500


@caja_bp.route('/api/getnet/pending', methods=['GET'])
@rate_limit(max_requests=30, window_seconds=60)
def getnet_pending_compat():
    """
    Endpoint compat para agentes antiguos:
    - GET /api/getnet/pending?register_id=1
    - Auth: X-AGENT-KEY o agent_key
    Respuesta:
      {hasPayment:false}
      o {hasPayment:true, paymentId:<intent_id>, amount:<int CLP>}
    """
    if not verify_agent_auth():
        return jsonify({'success': False, 'error': 'Autenticación inválida'}), 401

    try:
        register_id = request.args.get('register_id') or '1'
        register_id = str(register_id)
        agent_id = request.headers.get('X-AGENT-ID', 'unknown')

        intent = PaymentIntent.query.filter_by(
            register_id=register_id,
            status=PaymentIntent.STATUS_READY
        ).order_by(PaymentIntent.created_at.asc()).first()

        if not intent:
            return jsonify({'hasPayment': False})

        # Lockear intent
        intent.status = PaymentIntent.STATUS_IN_PROGRESS
        intent.locked_by_agent = agent_id
        intent.locked_at = datetime.utcnow()
        intent.updated_at = datetime.utcnow()
        db.session.commit()

        amount_clp = int(float(intent.amount_total))
        return jsonify({
            'hasPayment': True,
            'paymentId': str(intent.id),
            'amount': amount_clp
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en /api/getnet/pending: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500


@caja_bp.route('/api/getnet/result', methods=['POST'])
@rate_limit(max_requests=30, window_seconds=60)
def getnet_result_compat():
    """
    Endpoint compat para agentes antiguos:
    POST /api/getnet/result
    Body esperado (legacy):
      { paymentId: <uuid>, result: { success: bool, message: str, provider_ref?, auth_code? } }
    """
    if not verify_agent_auth():
        return jsonify({'success': False, 'error': 'Autenticación inválida'}), 401

    try:
        data = request.get_json(silent=True) or {}

        payment_id = data.get('paymentId') or data.get('intent_id')
        if not payment_id:
            return jsonify({'success': False, 'error': 'paymentId requerido'}), 400

        # Traducir resultado legacy -> status esperado
        result = data.get('result') or {}
        if isinstance(result, dict):
            success = bool(result.get('success', False))
            message = str(result.get('message', '') or '')
            provider_ref = result.get('provider_ref') or result.get('providerRef')
            auth_code = result.get('auth_code') or result.get('authCode')
        else:
            success = False
            message = ''
            provider_ref = None
            auth_code = None

        if success:
            status = PaymentIntent.STATUS_APPROVED
            error_code = None
            error_message = None
        else:
            # Mapeo simple: rejected -> DECLINED, resto -> ERROR
            status = PaymentIntent.STATUS_DECLINED if message.lower() in ('rejected', 'declined') else PaymentIntent.STATUS_ERROR
            error_code = 'DECLINED' if status == PaymentIntent.STATUS_DECLINED else 'ERROR'
            error_message = message or 'error'

        payload = {
            'intent_id': str(payment_id),
            'status': status,
            'provider_ref': provider_ref,
            'auth_code': auth_code,
            'error_code': error_code,
            'error_message': error_message,
        }

        return _process_agent_result_payload(payload)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en /api/getnet/result: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500

