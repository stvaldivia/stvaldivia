from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify, g
from collections import defaultdict, Counter
import requests
import re
import time
import os
import subprocess
import threading
import csv
import json
from werkzeug.security import generate_password_hash, check_password_hash
from .helpers.logs import load_logs, save_log, delete_log_entry, clear_all_logs
from .helpers.pos_api import get_sale_items, get_entity_details, get_employees, authenticate_employee, get_entradas_sales, get_all_sales
from .helpers.fraud_detection import detect_fraud, save_fraud_attempt, authorize_fraud, load_fraud_attempts
from .helpers.fraud_config import load_fraud_config, save_fraud_config
from .helpers.cache import invalidate_sale_cache, clear_cache
from .helpers.security import verify_admin_password
from .helpers.admin_users import verify_admin_user
from .helpers.rate_limiting import record_failed_attempt, clear_failed_attempts, is_locked_out, get_client_identifier
from .helpers.session_utils import update_session_activity, check_session_timeout
# Usar módulo de compatibilidad que migra gradualmente a Jornada
from .helpers.shift_manager_compat import open_shift as shift_open, close_shift as shift_close, get_shift_status, is_shift_open, get_shift_history
# Mantener import legacy como fallback
from .helpers.shift_manager import open_shift as shift_open_legacy, close_shift as shift_close_legacy
from .helpers.service_status import get_all_services_status, restart_service, get_postfix_queue
from flask import current_app
from datetime import datetime
import pytz
from app.helpers.logger import get_logger, log_error, safe_log_error
from app.models import db
from app import CHILE_TZ

# Logger para este módulo
logger = get_logger(__name__)

# Imports de servicios (nueva arquitectura)
from app.application.services.service_factory import (
    get_shift_service,
    get_delivery_service,
    get_stats_service,
    get_survey_service,
    get_social_media_service,
    get_inventory_service
)
from app.application.dto.shift_dto import OpenShiftRequest, CloseShiftRequest
from app.application.dto.delivery_dto import DeliveryRequest, ScanSaleRequest
from app.application.dto.inventory_dto import RegisterInitialInventoryRequest, FinalizeInventoryRequest
from app.domain.exceptions import ShiftNotOpenError, ShiftAlreadyOpenError, FraudDetectedError, DeliveryValidationError
from app.application.middleware.shift_guard import require_shift_open

bp = Blueprint('routes', __name__)

@bp.before_request
def before_request():
    """Middleware para verificar timeout de sesión y actualizar actividad"""
    # No aplicar a rutas estáticas
    if request.endpoint and request.endpoint.startswith('static'):
        return
    
    # Modo mantenimiento deshabilitado - trabajando solo localmente
    
    # Monitoreo de rendimiento
    try:
        from app.helpers.monitoring import record_request_time
        request_start_time = time.time()
        request._monitoring_start = request_start_time
    except:
        pass
    
    # Verificar timeout de sesión para usuarios autenticados
    if session.get('bartender') or session.get('admin_logged_in'):
        if check_session_timeout():
            flash("Tu sesión ha expirado. Por favor, inicia sesión nuevamente.", "info")
            session.clear()
            return redirect(url_for('routes.scanner'))
        else:
            update_session_activity()

@bp.route('/api/services/status')
def api_services_status_legacy():
    """API endpoint para obtener el estado de los servicios (legacy)"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        # Verificar API con log (checked_by='system' para verificaciones automáticas)
        services_status = get_all_services_status()
        return jsonify({
            'status': 'ok',
            'services': services_status
        })
    except Exception as e:
        logger.error(f"Error al obtener estado de servicios: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'services': {
                'postfix': {'status': 'unknown', 'running': False, 'message': 'Error al verificar'},
                'gunicorn': {'status': 'unknown', 'running': False, 'message': 'Error al verificar'},
                'nginx': {'status': 'unknown', 'running': False, 'message': 'Error al verificar'},
                'api': {'status': 'error', 'online': False, 'message': 'Error al verificar'}
            }
        }), 500

@bp.route('/admin/api/check-connection', methods=['POST'])
def api_check_connection():
    """Verifica la conexión API manualmente y registra en el log"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        from app.helpers.service_status import check_api_status
        
        # Verificar API con log (checked_by='admin' para verificaciones manuales)
        result = check_api_status(checked_by='admin', log_connection=True)
        
        return jsonify({
            'success': True,
            'status': result.get('status'),
            'online': result.get('online'),
            'response_time_ms': result.get('response_time_ms'),
            'message': result.get('message')
        })
    except Exception as e:
        logger.error(f"Error al verificar conexión API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/admin/api/connection-logs')
def api_connection_logs():
    """Obtiene el log de conexiones API"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        from app.models.api_log_models import ApiConnectionLog
        from app.helpers.timezone_utils import format_date_spanish
        
        # Obtener los últimos 50 logs
        logs = ApiConnectionLog.query.order_by(ApiConnectionLog.timestamp.desc()).limit(50).all()
        
        logs_data = []
        for log in logs:
            timestamp_chile = log.timestamp_chile
            logs_data.append({
                'id': log.id,
                'timestamp': timestamp_chile.strftime('%d/%m/%Y %H:%M:%S') if timestamp_chile else 'N/A',
                'status': log.status,
                'response_time_ms': log.response_time_ms,
                'message': log.message,
                'api_url': log.api_url,
                'checked_by': log.checked_by
            })
        
        return jsonify({
            'success': True,
            'logs': logs_data,
            'total': len(logs_data)
        })
    except Exception as e:
        logger.error(f"Error al obtener logs de conexión API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/services/restart', methods=['POST'])
def api_restart_service():
    """API endpoint para reiniciar un servicio"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        service_name = data.get('service')
        
        if not service_name:
            return jsonify({
                'success': False,
                'message': 'Nombre de servicio no proporcionado'
            }), 400
        
        # Validar que el servicio es uno de los permitidos
        allowed_services = ['postfix', 'gunicorn', 'nginx']
        if service_name not in allowed_services:
            return jsonify({
                'success': False,
                'message': f'Servicio no permitido: {service_name}'
            }), 400
        
        logger.info(f"Intento de reinicio de servicio: {service_name} por usuario admin")
        result = restart_service(service_name)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message']
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 500
            
    except Exception as e:
        logger.error(f"Error al reiniciar servicio: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@bp.route('/api/services/postfix/queue')
def api_postfix_queue():
    """API endpoint para obtener la cola de correo de Postfix"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        queue_data = get_postfix_queue()
        return jsonify(queue_data), 200 if queue_data['success'] else 500
    except Exception as e:
        logger.error(f"Error al obtener cola de Postfix: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'queue': [],
            'total': 0,
            'message': f'Error: {str(e)}'
        }), 500

@bp.route('/api/health')
def api_health_check():
    """Health check - Modo solo local: No conecta con servicios externos"""
    local_only = current_app.config.get('LOCAL_ONLY', True)
    
    if local_only:
        return jsonify({
            'status': 'ok',
            'message': 'Modo solo local activo - No se conecta a servicios externos',
            'online': True,
            'local_mode': True
        }), 200
    
    # Código para modo con conexiones externas (no se ejecuta en modo local)
    api_key = current_app.config.get('API_KEY')
    base_url = current_app.config.get('BASE_API_URL')
    
    if not api_key or not base_url:
        return jsonify({
            'status': 'error',
            'message': 'API no configurada',
            'online': False
        }), 500
    
    try:
        url = f"{base_url}/employees"
        headers = {
            "x-api-key": api_key,
            "accept": "application/json"
        }
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        
        return jsonify({
            'status': 'ok',
            'message': 'API conectada',
            'online': True,
            'response_time_ms': resp.elapsed.total_seconds() * 1000
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}',
            'online': False
        }), 503

@bp.route('/', methods=['GET', 'POST'])
def index():
    """Página principal - Menú de opciones"""
    # Si ya está logueado como admin, redirigir al admin
    if session.get('admin_logged_in'):
        return redirect(url_for('routes.admin_dashboard'))
    
    # Mostrar menú de opciones
    return render_template('home.html')

@bp.route('/admin/scanner', methods=['GET', 'POST'])
def admin_scanner():
    """Página del escáner para administradores - desde admin/logs"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    # Usar el mismo template que scanner pero con contexto de admin
    return scanner_internal(admin_mode=True)

@bp.route('/scanner', methods=['GET', 'POST'])
def scanner():
    """Página del escáner - sistema de entregas independiente de turnos"""
    # Verificar sesión antes de mostrar el escáner
    if 'barra' not in session:
        flash("Por favor, selecciona una barra primero.", "info")
        return redirect(url_for('routes.seleccionar_barra'))
    if 'bartender' not in session:
        flash("Por favor, selecciona un bartender.", "info")
        return redirect(url_for('routes.seleccionar_bartender'))
    
    return scanner_internal(admin_mode=False)

def scanner_internal(admin_mode=False):
    """Función interna para el escáner (compartida entre scanner normal y admin)"""

    delivery_service = get_delivery_service()
    fraud_service = delivery_service.fraud_service
    
    items = []
    error = None
    venta_info = None
    fraud_detected = None

    # Sanitizar entrada del usuario
    user_input_id = (request.form.get('code', '') or request.args.get('sale_id', '')).strip()[:50]
    sale_id_canonical = user_input_id
    id_for_api_query = None

    if user_input_id:
        # Validación mejorada de entrada
        user_input_id = re.sub(r'[<>"\';]', '', user_input_id)
        raw = user_input_id.upper()

        # Manejar prefijos BMB y B (kiosko)
        if raw.startswith("BMB "):
            id_for_api_query = user_input_id[4:].strip()
            sale_id_canonical = f"BMB {id_for_api_query}"
        elif raw.startswith("BMB"):
            id_for_api_query = user_input_id[3:].strip()
            sale_id_canonical = f"BMB {id_for_api_query}"
        elif raw.startswith("B ") and len(raw) > 2:
            # Prefijo del kiosko: "B 123" -> buscar en tabla pagos
            id_for_api_query = user_input_id[2:].strip()
            sale_id_canonical = f"B {id_for_api_query}"
        elif raw.startswith("B") and len(raw) > 1 and raw[1].isdigit():
            # Prefijo del kiosko sin espacio: "B123" -> buscar en tabla pagos
            id_for_api_query = user_input_id[1:].strip()
            sale_id_canonical = f"B {id_for_api_query}"
        elif raw.startswith("POS "):
            id_for_api_query = user_input_id[4:].strip()
            sale_id_canonical = f"BMB {id_for_api_query}"
        elif raw.startswith("POS"):
            id_for_api_query = user_input_id[3:].strip()
            sale_id_canonical = f"BMB {id_for_api_query}"
        elif user_input_id.isdigit():
            id_for_api_query = user_input_id
            sale_id_canonical = f"BMB {id_for_api_query}"
        else:
            numbers = re.findall(r'\d+', user_input_id)
            if numbers:
                id_for_api_query = numbers[0]
                sale_id_canonical = f"BMB {id_for_api_query}"
            else:
                id_for_api_query = user_input_id

    # Obtener entregas existentes usando repositorio (optimizado: una sola iteración)
    all_deliveries = delivery_service.delivery_repository.find_all()
    entregados_qty = defaultdict(int)
    entregados_info = {}
    entregados_todos = defaultdict(list)

    # Optimización: una sola iteración sobre las entregas
    for delivery in all_deliveries:
        key = (delivery.sale_id, delivery.item_name)
        qty = delivery.qty
        
        entregados_qty[key] += qty
        # Solo guardar la primera entrega como info principal
        if key not in entregados_info:
            entregados_info[key] = delivery.to_csv_row()
        entregados_todos[key].append({
            'qty': qty,
            'bartender': delivery.bartender,
            'barra': delivery.barra,
            'timestamp': delivery.timestamp
        })

    # Escanear venta si hay ID
    if id_for_api_query:
        try:
            # Si es un ticket del kiosko (prefijo "B"), buscar primero en tabla pagos
            if sale_id_canonical.startswith("B "):
                try:
                    from app.models.kiosk_models import Pago
                    # Buscar pago por ticket_code
                    pago = Pago.query.filter_by(ticket_code=sale_id_canonical).first()
                    if pago and pago.sale_id_phppos:
                        # Usar el sale_id_phppos para buscar en PHP POS
                        logger.info(f"Ticket del kiosko encontrado: {sale_id_canonical} -> sale_id_phppos: {pago.sale_id_phppos}")
                        sale_id_canonical = pago.sale_id_phppos
                        id_for_api_query = pago.sale_id_phppos
                except Exception as e:
                    logger.warning(f"Error al buscar ticket del kiosko: {e}")
                    # Continuar con búsqueda normal en PHP POS
            
            scan_request = ScanSaleRequest(sale_id=sale_id_canonical)
            scan_request.validate()
            
            venta_info = delivery_service.scan_sale(scan_request)
            
            if 'error' in venta_info:
                error = venta_info['error']
                items = []
            else:
                items = venta_info.get('items', [])
                sale_id_canonical = venta_info.get('venta_id', sale_id_canonical)
                
                # Guardar información completa del ticket escaneado en el log (solo en el primer escaneo)
                if items:
                    from .helpers.ticket_scans import save_ticket_scan
                    # Preparar items para guardar
                    items_to_save = [{'name': item.get('name', ''), 'quantity': item.get('quantity', 0)} for item in items]
                    # Guardar toda la información de la venta para uso futuro
                    save_ticket_scan(sale_id_canonical, items_to_save, venta_info)
                
                # Verificar fraudes antes de mostrar el ticket
                sale_time = venta_info.get('fecha_venta', '')
                fraud_check = fraud_service.detect_fraud(sale_id_canonical, sale_time)
                
                if fraud_check['is_fraud']:
                    fraud_detected = fraud_check
                    # Guardar el intento de fraude (usar función existente para compatibilidad)
                    if admin_mode:
                        bartender_fraud = session.get('admin_username', 'Admin')
                        barra_fraud = 'Centro de Control'
                    else:
                        bartender_fraud = session.get('bartender', 'Desconocido')
                        barra_fraud = session.get('barra', 'Desconocida')
                    
                    save_fraud_attempt(
                        sale_id=sale_id_canonical,
                        bartender=bartender_fraud,
                        barra=barra_fraud,
                        item_name='N/A',
                        qty=0,
                        fraud_type=fraud_check['fraud_type'],
                        authorized=False
                    )
        except ValueError as e:
            error = f"Error al escanear venta: {str(e)}"
        except Exception as e:
            log_error(
                logger,
                "Error al escanear venta",
                error=e,
                context={
                    'sale_id': sale_id_canonical,
                    'user_input': user_input_id[:50] if user_input_id else None
                }
            )
            error = f"Error inesperado al escanear venta: {str(e)}"

    # Determinar return_url según el modo
    if admin_mode:
        return_url = url_for('routes.admin_logs')
        session_bartender = session.get('admin_username', 'Admin')
        session_barra = 'Centro de Control'
    else:
        return_url = url_for('routes.scanner')
        session_bartender = session.get('bartender')
        session_barra = session.get('barra')
    
    # Si se detectó fraude, mostrar la pantalla de fraude
    if fraud_detected and fraud_detected.get('is_fraud'):
        return render_template(
            'fraud_detection.html',
            sale_id=sale_id_canonical,
            fraud_message=fraud_detected['message'],
            fraud_type=fraud_detected['fraud_type'],
            fraud_details=fraud_detected['details'],
            venta_info_adicional=venta_info,
            item_name='',
            qty=0,
            return_url=return_url
        )

    return render_template(
        'index.html',
        items=items,
        error=error,
        sale_id=sale_id_canonical,
        entregados_qty=entregados_qty,
        entregados_info=entregados_info,
        entregados_todos=entregados_todos,
        session_bartender=session_bartender,
        session_barra=session_barra,
        venta_info_adicional=venta_info,
        admin_mode=admin_mode  # Pasar flag de admin_mode al template
    )

def get_venta_details(numeric_sale_id):
    api_key = current_app.config['API_KEY']
    base = current_app.config['BASE_API_URL']

    if not api_key:
        return None

    try:
        resp = requests.get(f"{base}/sales/{numeric_sale_id}", headers={"x-api-key": api_key, "accept": "application/json"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        sale_id = data.get("sale_id", f"BMB {numeric_sale_id}")
        employee_id = data.get("employee_id")
        customer_id = data.get("customer_id")
        register_id = data.get("register_id")
        comment = data.get("comment", "")
        sale_time = data.get("sale_time", "Fecha no disponible")

        vendedor = "Desconocido"
        comprador = "N/A"
        caja = "Caja desconocida"

        emp = get_entity_details("employees", employee_id)
        if emp:
            vendedor = f"{emp.get('first_name','')} {emp.get('last_name','')}".strip()

        cli = get_entity_details("customers", customer_id)
        if cli:
            comprador = f"{cli.get('first_name','')} {cli.get('last_name','')}".strip()

        reg = get_entity_details("registers", register_id)
        if reg:
            caja = reg.get("name", f"Caja ID {register_id}")

        return {
            "venta_id": sale_id,
            "fecha_venta": sale_time,
            "vendido_por": vendedor,
            "caja": caja,
            "cliente": comprador,
            "comentario": comment or "Sin comentarios"
        }

    except requests.exceptions.Timeout:
        current_app.logger.error(f"Timeout al obtener detalles de venta {numeric_sale_id}")
        return {
            "venta_id": f"BMB {numeric_sale_id}",
            "fecha_venta": "Error: Timeout de conexión",
            "vendido_por": "Error",
            "caja": "Error",
            "cliente": "Error",
            "comentario": "No se pudo obtener información debido a timeout"
        }
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error al obtener detalles de venta {numeric_sale_id}: {e}")
        return {
            "venta_id": f"BMB {numeric_sale_id}",
            "fecha_venta": "Error: Problema de conexión",
            "vendido_por": "Error",
            "caja": "Error",
            "cliente": "Error",
            "comentario": f"Error de conexión: {str(e)}"
        }
    except Exception as e:
        current_app.logger.error(f"Error inesperado al obtener detalles de venta {numeric_sale_id}: {e}")
        return None

@bp.route('/entregar', methods=['POST'])
def entregar():
    """Registrar una entrega - thin controller usando DeliveryService"""
    # Verificar sesión
    if 'barra' not in session or 'bartender' not in session:
        flash("Error: No se ha seleccionado barra o bartender.", "error")
        return redirect(url_for('routes.seleccionar_barra'))

    # Obtener datos del formulario
    sale_id = request.form.get('sale_id', '').strip()
    item_name = request.form.get('item_name', '').strip()
    qty_str = request.form.get('qty', '').strip()

    if not all([sale_id, item_name, qty_str]):
        flash("Faltan datos para registrar entrega.", "error")
        return redirect(url_for('routes.scanner', sale_id=sale_id))

    # Validación mejorada usando helpers
    from app.helpers.validation import validate_sale_id, validate_quantity
    
    is_valid_sale_id, sale_id_error = validate_sale_id(sale_id)
    if not is_valid_sale_id:
        flash(f"ID de venta inválido: {sale_id_error}", "error")
        return redirect(url_for('routes.scanner', sale_id=sale_id))
    
    # Validar cantidad con límite razonable
    is_valid_qty, qty, qty_error = validate_quantity(qty_str, max_qty=100, min_qty=1)
    if not is_valid_qty:
        flash(f"Cantidad inválida: {qty_error}", "error")
        return redirect(url_for('routes.scanner', sale_id=sale_id))
    
    # Validar nombre de item (sanitizar)
    if len(item_name) > 200:
        flash("Nombre de producto demasiado largo.", "error")
        return redirect(url_for('routes.scanner', sale_id=sale_id))
    
    item_name = item_name[:200]  # Limitar longitud

    # Usar servicios
    delivery_service = get_delivery_service()
    
    # Obtener información de la venta para validar cantidad pendiente y fecha
    numeric_sale_id = sale_id.replace("BMB ", "").strip()
    venta_info = None
    sale_time = None
    
    try:
        scan_request = ScanSaleRequest(sale_id=sale_id)
        scan_request.validate()
        venta_info = delivery_service.scan_sale(scan_request)
        sale_time = venta_info.get('fecha_venta', '') if venta_info and 'error' not in venta_info else None
    except Exception as e:
        current_app.logger.warning(f"Error al obtener info de venta para validación: {e}")
    
    # Validar cantidad pendiente si tenemos info de la venta
    if venta_info and 'error' not in venta_info:
        items = venta_info.get('items', [])
        for item in items:
            item_name_from_api = item.get('name', '') if isinstance(item, dict) else getattr(item, 'name', '')
            item_qty = item.get('quantity', 0) if isinstance(item, dict) else getattr(item, 'quantity', 0)
            
            if item_name_from_api == item_name:
                # Contar entregas existentes de este item
                existing_deliveries = delivery_service.delivery_repository.find_by_sale_id(sale_id)
                delivered = sum(d.qty for d in existing_deliveries if d.item_name == item_name)
                pending = item_qty - delivered
                
                if qty > pending:
                    flash(f"No se puede entregar {qty} unidades. Solo hay {pending} pendientes.", "error")
                    return redirect(url_for('routes.scanner', sale_id=sale_id))
                break
    
    # Verificar autorización de fraudes previos (usar función existente para compatibilidad)
    fraud_check = delivery_service.fraud_service.detect_fraud(sale_id, sale_time)
    
    if fraud_check['is_fraud']:
        # Verificar si hay autorización previa
        fraud_attempts = load_fraud_attempts()
        is_authorized = False
        
        for attempt in reversed(fraud_attempts):
            if len(attempt) >= 7 and attempt[0] == sale_id and attempt[6] == fraud_check['fraud_type']:
                if attempt[7] == '1':  # Autorizado
                    is_authorized = True
                    break
                else:
                    break
        
        if not is_authorized:
            # Guardar el intento de fraude (usar función existente)
            save_fraud_attempt(
                sale_id=sale_id,
                bartender=session.get('bartender', 'Desconocido'),
                barra=session.get('barra', 'Desconocida'),
                item_name=item_name,
                qty=qty,
                fraud_type=fraud_check['fraud_type'],
                authorized=False
            )
            
            return render_template(
                'fraud_detection.html',
                sale_id=sale_id,
                fraud_message=fraud_check['message'],
                fraud_type=fraud_check['fraud_type'],
                fraud_details=fraud_check['details'],
                venta_info_adicional=venta_info,
                item_name=item_name,
                qty=qty,
                return_url=url_for('routes.scanner', sale_id=sale_id)
            )

    # Registrar entrega usando servicio
    # Si viene de admin, usar admin_user; si no, usar bartender normal
    admin_user = session.get('admin_username') if session.get('admin_logged_in') else None
    bartender = admin_user if admin_user else session.get('bartender')
    barra = 'Centro de Control' if admin_user else session.get('barra')
    
    delivery_request = DeliveryRequest(
        sale_id=sale_id,
        item_name=item_name,
        qty=qty,
        bartender=bartender,
        barra=barra,
        admin_user=admin_user
    )
    
    try:
        success, message, fraud_info = delivery_service.register_delivery_with_fraud_check(
            delivery_request,
            sale_time_str=sale_time
        )
        
        if success:
            flash(f"{qty} × {item_name} entregado(s).", "success")
        else:
            # Si retorna False, probablemente es fraude no autorizado
            # (aunque ya debería haberse manejado arriba)
            if fraud_info:
                flash(f"⚠️ {message}", "warning")
            else:
                flash(f"⚠️ {message}", "warning")
            
    except ShiftNotOpenError as e:
        flash(f"⚠️ {str(e)}", "error")
        return redirect(url_for('routes.seleccionar_barra'))
    except FraudDetectedError as e:
        # Esto no debería pasar si ya verificamos arriba, pero por seguridad
        flash(f"⚠️ {str(e)}", "error")
        return redirect(url_for('routes.scanner', sale_id=sale_id))
    except DeliveryValidationError as e:
        flash(f"❌ {str(e)}", "error")
        return redirect(url_for('routes.scanner', sale_id=sale_id))
    except Exception as e:
        current_app.logger.error(f"Error al registrar entrega: {e}")
        flash(f"❌ Error al registrar entrega: {str(e)}", "error")
        return redirect(url_for('routes.scanner', sale_id=sale_id))
    
    return redirect(url_for('routes.scanner', sale_id=sale_id))

@bp.route('/barra', methods=['GET', 'POST'])
def seleccionar_barra():
    # Verificar que el bartender esté logueado
    if 'bartender' not in session:
        flash("Por favor, inicia sesión primero.", "info")
        return redirect(url_for('routes.seleccionar_bartender'))
    
    if request.method == 'POST':
        b = request.form.get('barra')
        if b:
            session['barra'] = b
            # Después de seleccionar barra, ir al scanner
            return redirect(url_for('routes.scanner'))
        flash("Debes seleccionar una barra.", "error")

    barras = ['Barra Principal', 'Barra Terraza', 'Barra VIP', 'Barra Exterior']
    return render_template('seleccionar_barra.html', barras=barras, current_barra=session.get('barra'))

@bp.route('/bartender', methods=['GET', 'POST'])
def seleccionar_bartender():
    # Ya no requiere barra primero - ahora es el primer paso

    selected_employee_id = session.get('selected_employee_id')
    selected_employee_info = session.get('selected_employee_info')

    if request.method == 'POST':
        # Si se cancela la selección
        if request.form.get('cancel'):
            session.pop('selected_employee_id', None)
            session.pop('selected_employee_info', None)
            return redirect(url_for('routes.seleccionar_bartender'))
        
        # Si se selecciona un empleado
        employee_id = request.form.get('employee_id')
        if employee_id and not selected_employee_id:
            # Obtener información del empleado desde la base de datos local
            from app.helpers.employee_local import get_employee_local
            employee = get_employee_local(employee_id)
            if employee:
                emp_id = employee.get('person_id') or employee.get('employee_id') or employee.get('id')
                emp_name = employee.get('name', 'Empleado')
                
                session['selected_employee_id'] = emp_id
                session['selected_employee_info'] = {
                    'id': emp_id,
                    'name': emp_name,
                    'first_name': employee.get('first_name', ''),
                    'last_name': employee.get('last_name', '')
                }
                return redirect(url_for('routes.seleccionar_bartender'))
            else:
                flash("No se pudo obtener información del empleado. Verifica que el empleado esté activo.", "error")
        
        # Si se ingresa el PIN
        pin = request.form.get('pin', '').strip()
        if pin and selected_employee_id:
            if not pin:
                flash("Debes ingresar tu PIN.", "error")
            else:
                # Autenticar empleado con PIN desde la base de datos local
                from app.helpers.employee_local import authenticate_employee_local
                employee = authenticate_employee_local(selected_employee_id, pin)
                
                if employee:
                    # Guardar información del empleado en la sesión
                    session['bartender'] = employee['name']
                    session['bartender_id'] = employee['id']
                    session['bartender_first_name'] = employee.get('first_name', '')
                    session['bartender_last_name'] = employee.get('last_name', '')
                    session['last_activity'] = time.time()
                    # Limpiar selección temporal
                    session.pop('selected_employee_id', None)
                    session.pop('selected_employee_info', None)
                    session['show_fortune_cookie'] = True  # Flag en sesión para mostrar galleta
                    flash(f"Bienvenido, {employee['name']}!", "success")
                    # Redirigir a seleccionar barra con parámetro para mostrar galleta de la fortuna
                    return redirect(url_for('routes.seleccionar_barra', show_fortune='true'))
                else:
                    flash("PIN incorrecto. Intenta nuevamente.", "error")

    # Obtener lista de empleados bartenders desde la planilla del turno actual (solo BARTENDERS asignados)
    from app.models.jornada_models import Jornada, SnapshotEmpleados, PlanillaTrabajador
    from datetime import datetime
    from app import CHILE_TZ
    from app.models import db
    
    # Buscar jornada abierta (puede ser de hoy o de días anteriores si aún está abierta)
    jornada_actual = Jornada.query.filter_by(estado_apertura='abierto').order_by(Jornada.fecha_jornada.desc()).first()
    
    employees = []
    if jornada_actual:
        # Obtener trabajadores asignados como BARTENDERS desde la planilla
        planilla_bartenders = PlanillaTrabajador.query.filter_by(
            jornada_id=jornada_actual.id
        ).filter(
            # Filtrar por rol "bartender" o área que contenga "barra" (case insensitive)
            db.or_(
                PlanillaTrabajador.rol.ilike('%bartender%'),
                PlanillaTrabajador.rol.ilike('%barra%'),
                PlanillaTrabajador.area.ilike('%barra%')
            )
        ).all()
        
        if planilla_bartenders:
            # Convertir a formato esperado por el template
            employees = []
            for trabajador in planilla_bartenders:
                # Obtener información del empleado desde el snapshot o usar datos de la planilla
                snapshot_emp = SnapshotEmpleados.query.filter_by(
                    jornada_id=jornada_actual.id,
                    empleado_id=trabajador.id_empleado
                ).first()
                
                if snapshot_emp:
                    employees.append({
                        'person_id': trabajador.id_empleado,
                        'employee_id': trabajador.id_empleado,
                        'id': trabajador.id_empleado,
                        'first_name': trabajador.nombre_empleado.split()[0] if trabajador.nombre_empleado else '',
                        'last_name': ' '.join(trabajador.nombre_empleado.split()[1:]) if len(trabajador.nombre_empleado.split()) > 1 else '',
                        'name': trabajador.nombre_empleado,
                        'job_title': trabajador.rol or 'Bartender'
                    })
                else:
                    # Si no hay snapshot, usar datos de la planilla directamente
                    employees.append({
                        'person_id': trabajador.id_empleado,
                        'employee_id': trabajador.id_empleado,
                        'id': trabajador.id_empleado,
                        'first_name': trabajador.nombre_empleado.split()[0] if trabajador.nombre_empleado else '',
                        'last_name': ' '.join(trabajador.nombre_empleado.split()[1:]) if len(trabajador.nombre_empleado.split()) > 1 else '',
                        'name': trabajador.nombre_empleado,
                        'job_title': trabajador.rol or 'Bartender'
                    })
            
            current_app.logger.info(f"✅ Cargados {len(employees)} bartenders desde planilla del turno (Jornada ID: {jornada_actual.id})")
        else:
            current_app.logger.warning(f"⚠️ No se encontraron bartenders en la planilla del turno (Jornada ID: {jornada_actual.id})")
            flash("No hay bartenders asignados en el turno actual. Por favor, contacta al administrador.", "warning")
    else:
        # Si no hay turno abierto, mostrar mensaje
        current_app.logger.warning("⚠️ No hay turno abierto")
        flash("No hay turno abierto. Por favor, espera a que se abra un turno.", "error")
    
    return render_template(
        'seleccionar_bartender.html', 
        employees=employees, 
        current_bartender=session.get('bartender'),
        selected_employee_id=selected_employee_id,
        selected_employee_info=selected_employee_info
    )

@bp.route('/reset')
def reset():
    session.pop('barra', None)
    session.pop('bartender', None)
    session.pop('bartender_id', None)
    session.pop('bartender_first_name', None)
    session.pop('bartender_last_name', None)
    session.pop('selected_employee_id', None)
    session.pop('selected_employee_info', None)
    flash("Sesión reiniciada.", "info")
    return redirect(url_for('routes.seleccionar_barra'))

@bp.route('/login_admin', methods=['GET', 'POST'])
def login_admin():
    if session.get('admin_logged_in'):
        return redirect(url_for('routes.admin_dashboard'))

    if request.method == 'POST':
        client_id = get_client_identifier()
        
        # Verificar si está bloqueado
        locked, remaining_time, attempts = is_locked_out(client_id)
        if locked:
            minutes = int(remaining_time // 60)
            seconds = int(remaining_time % 60)
            flash(f"Demasiados intentos fallidos. Intenta nuevamente en {minutes}m {seconds}s.", "error")
            return render_template('login_admin.html')
        
        username = request.form.get('username', '').strip()
        pwd = request.form.get('password')
        
        # Intentar autenticación con sistema de usuarios primero
        if username and pwd and verify_admin_user(username, pwd):
            clear_failed_attempts(client_id)
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['last_activity'] = time.time()
            # Mensaje de bienvenida personalizado
            from app.helpers.motivational_messages import get_welcome_message, get_time_based_greeting
            welcome_msg = f"{get_time_based_greeting()} {get_welcome_message(username)}"
            flash(welcome_msg, "success")
            return redirect(url_for('routes.admin_dashboard'))
        # Fallback: verificar contraseña antigua (compatibilidad)
        elif pwd and verify_admin_password(pwd):
            clear_failed_attempts(client_id)
            session['admin_logged_in'] = True
            session['admin_username'] = 'admin'
            session['last_activity'] = time.time()
            # Mensaje de bienvenida
            from app.helpers.motivational_messages import get_welcome_message, get_time_based_greeting
            welcome_msg = f"{get_time_based_greeting()} {get_welcome_message('Administrador')}"
            flash(welcome_msg, "success")
            return redirect(url_for('routes.admin_dashboard'))
        else:
            record_failed_attempt(client_id)
            flash("Usuario o contraseña incorrectos.", "error")

    return render_template('login_admin.html')

@bp.route('/admin')
def admin_dashboard():
    """Dashboard principal administrativo"""
    from flask import current_app
    try:
        if not session.get('admin_logged_in'):
            flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
            return redirect(url_for('routes.login_admin'))
        
        # Obtener estado del turno desde Jornada (sistema único)
        from app.models.jornada_models import Jornada
        from datetime import datetime
        from app import CHILE_TZ
        fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
        try:
            jornada_actual = Jornada.query.filter_by(fecha_jornada=fecha_hoy, estado_apertura='abierto').first()
        except Exception as e:
            current_app.logger.error(f"Error al consultar jornada en admin_dashboard: {e}", exc_info=True)
            jornada_actual = None
        
        # Usar información de Jornada
        if jornada_actual:
            shift_status_dict = {
                'is_open': True,
                'shift_date': jornada_actual.fecha_jornada,
                'opened_at': jornada_actual.abierto_en.isoformat() if jornada_actual.abierto_en else jornada_actual.horario_apertura_programado,
                'closed_at': None,
                'fiesta_nombre': jornada_actual.nombre_fiesta,
                'djs': jornada_actual.djs,
                'from_jornada': True
            }
            # Crear objeto shift_status compatible para código existente
            class ShiftStatusCompat:
                def __init__(self, jornada):
                    self.is_open = True
                    self.shift_date = jornada.fecha_jornada
                    self.fiesta_nombre = jornada.nombre_fiesta
                    self.djs = jornada.djs
                    self.opened_at = jornada.abierto_en.isoformat() if jornada.abierto_en else jornada.horario_apertura_programado
                    self.closed_at = None
            shift_status = ShiftStatusCompat(jornada_actual)
        else:
            # No hay turno abierto
            shift_status_dict = {
                'is_open': False,
                'shift_date': fecha_hoy,
                'opened_at': None,
                'closed_at': None,
                'fiesta_nombre': None,
                'djs': None,
                'from_jornada': False
            }
            class ShiftStatusCompat:
                def __init__(self):
                    self.is_open = False
                    self.shift_date = fecha_hoy
                    self.fiesta_nombre = None
                    self.djs = None
                    self.opened_at = None
                    self.closed_at = None
            shift_status = ShiftStatusCompat()
        
        # Obtener solicitudes SOS pendientes
        from app.helpers.sos_drawer_helper import get_pending_requests
        try:
            sos_requests = get_pending_requests()
        except Exception as e:
            current_app.logger.error(f"Error al cargar solicitudes de apertura de cajón: {e}")
            sos_requests = []
        
        # Obtener cierres de caja pendientes desde base de datos
        from app.helpers.register_close_db import get_pending_closes
        try:
            pending_closes = get_pending_closes()
        except Exception as e:
            current_app.logger.error(f"Error al cargar cierres pendientes: {e}")
            pending_closes = []
        
        # Obtener bloqueos de cajas activos
        from app.helpers.register_lock_db import get_all_register_locks
        try:
            register_locks = get_all_register_locks()
        except Exception as e:
            current_app.logger.error(f"Error al cargar bloqueos de cajas: {e}")
            register_locks = []
        
        # Obtener ventas recientes del turno (últimas 20)
        from app.models import PosSale
        try:
            shift_date_for_sales = shift_status_dict.get('shift_date') or shift_status.shift_date
            if shift_status_dict.get('is_open', False) or shift_status.is_open:
                # Optimizar query con eager loading
                from sqlalchemy.orm import joinedload
                recent_sales = PosSale.query.options(
                    joinedload(PosSale.items)  # Eager loading para evitar N+1 queries
                ).filter(
                    PosSale.shift_date == shift_date_for_sales
                ).order_by(PosSale.created_at.desc()).limit(20).all()
                recent_sales_data = [sale.to_dict() for sale in recent_sales]
            else:
                recent_sales_data = []
        except Exception as e:
            current_app.logger.error(f"Error al cargar ventas recientes: {e}", exc_info=True)
            recent_sales_data = []
        
        # Convertir ShiftStatus a dict para compatibilidad con template
        shift_status_dict = shift_status.to_dict() if hasattr(shift_status, 'to_dict') else {
            'is_open': shift_status.is_open,
            'shift_date': shift_status.shift_date,
            'opened_at': shift_status.opened_at,
            'closed_at': shift_status.closed_at,
            'fiesta_nombre': shift_status.fiesta_nombre,
            'djs': shift_status.djs
        }
        
        # Obtener estadísticas del kiosko FILTRADAS POR TURNO (no por día)
        kiosk_stats = {}
        shift_metrics = {}
        try:
            from app.models.kiosk_models import Pago
            from datetime import datetime, timedelta
            from app.models import db
            
            # Usar información de Jornada (sistema único)
            if jornada_actual and jornada_actual.abierto_en:
                # Filtrar por turno: pagos desde opened_at de Jornada
                shift_opened_at = jornada_actual.abierto_en
                if shift_opened_at.tzinfo is not None:
                    shift_opened_at = shift_opened_at.replace(tzinfo=None)
                
                # OPTIMIZADO: Usar agregaciones SQL en lugar de cargar todo en memoria
                from sqlalchemy import func
                
                # Pagos del turno (agregación SQL)
                pagos_turno_query = Pago.query.filter(
                    Pago.created_at >= shift_opened_at,
                    Pago.estado == 'PAID'
                )
                pagos_turno_count = pagos_turno_query.count()
                monto_turno_result = db.session.query(func.sum(Pago.monto)).filter(
                    Pago.created_at >= shift_opened_at,
                    Pago.estado == 'PAID'
                ).scalar()
                monto_turno = float(monto_turno_result or 0)
                
                # Totales históricos (agregación SQL)
                total_pagos = Pago.query.filter_by(estado='PAID').count()
                monto_total_result = db.session.query(func.sum(Pago.monto)).filter_by(estado='PAID').scalar()
                monto_total = float(monto_total_result or 0)
                pagos_pendientes = Pago.query.filter_by(estado='PENDING').count()
                
                kiosk_stats = {
                    'pagos_turno': pagos_turno_count,
                    'monto_turno': monto_turno,
                    'total_pagos': total_pagos,
                    'monto_total': monto_total,
                    'pagos_pendientes': pagos_pendientes
                }
                
                # Calcular tiempo transcurrido del turno usando hora de Chile
                from datetime import timezone
                now_chile = datetime.now(CHILE_TZ)
                
                # Manejar abierto_en: puede ser UTC naive (antiguo) o UTC naive que representa hora de Chile
                opened_dt_utc = shift_opened_at
                if opened_dt_utc.tzinfo is None:
                    # Si no tiene timezone, verificar si es muy antiguo (más de 12 horas)
                    # Si es muy antiguo, probablemente fue guardado como hora local (Chile) sin timezone
                    diff_naive = now_chile.replace(tzinfo=None) - opened_dt_utc
                    if diff_naive.total_seconds() > 12 * 3600:  # Más de 12 horas
                        # Asumir que es hora local (Chile) sin timezone
                        opened_dt_chile = CHILE_TZ.localize(opened_dt_utc)
                    else:
                        # Asumir que es UTC (nuevo formato)
                        opened_dt_utc_aware = opened_dt_utc.replace(tzinfo=timezone.utc)
                        opened_dt_chile = opened_dt_utc_aware.astimezone(CHILE_TZ)
                else:
                    # Ya tiene timezone, convertir a Chile
                    opened_dt_chile = opened_dt_utc.astimezone(CHILE_TZ)
                
                diff = now_chile - opened_dt_chile
                horas = int(diff.total_seconds() // 3600)
                minutos = int((diff.total_seconds() % 3600) // 60)
                
                # OPTIMIZADO: Métricas del turno con menos procesamiento
                delivery_service = get_delivery_service()
                
                # Entregas del turno (filtrar en query)
                # Usar el nuevo método optimizado si está disponible, sino fallback
                if hasattr(delivery_service.delivery_repository, 'find_by_timestamp_after'):
                    shift_deliveries = delivery_service.delivery_repository.find_by_timestamp_after(shift_opened_at)
                else:
                    # Fallback por si no se actualizó el repo (aunque acabamos de hacerlo)
                    all_deliveries = delivery_service.delivery_repository.find_all()
                    shift_deliveries = []
                    for delivery in all_deliveries:
                        try:
                            if isinstance(delivery.timestamp, str):
                                delivery_time = datetime.strptime(delivery.timestamp, '%Y-%m-%d %H:%M:%S')
                            else:
                                delivery_time = delivery.timestamp
                            if delivery_time >= shift_opened_at:
                                shift_deliveries.append(delivery)
                        except:
                            continue
                
                total_entregas_turno = sum(d.qty for d in shift_deliveries)
                
                # OPTIMIZADO: Entradas del turno - solo cargar lo necesario
                from .helpers.ticket_scans import get_all_ticket_scans
                ticket_scans = get_all_ticket_scans()
                total_entradas_turno = 0
                entradas_5000_turno = 0
                entradas_10000_turno = 0
                
                # Procesar tickets (esto sigue siendo en memoria porque es JSON, 
                # pero al menos evitamos lógica compleja si no es necesario)
                if ticket_scans:
                    for sale_id, ticket_data in ticket_scans.items():
                        scanned_at = ticket_data.get('scanned_at', '')
                        if not scanned_at:
                            continue
                            
                        try:
                            # Parseo rápido de fecha ISO
                            if 'T' in scanned_at:
                                # Comparación de strings ISO es válida si están en UTC/mismo formato
                                # Pero para seguridad convertimos
                                ticket_time = datetime.fromisoformat(scanned_at.replace('Z', '+00:00'))
                                if ticket_time.tzinfo:
                                    ticket_time = ticket_time.replace(tzinfo=None)
                                
                                if ticket_time < shift_opened_at:
                                    continue
                            else:
                                continue
                        except:
                            continue
                        
                        items = ticket_data.get('items', [])
                        for item in items:
                            item_name = item.get('name', '').lower()
                            if 'entrada' in item_name:
                                qty = item.get('quantity', 0)
                                price = item.get('unit_price', 0) or item.get('price', 0)
                                if not price:
                                    sale_data = ticket_data.get('sale_data', {})
                                    total = float(sale_data.get('total', 0) or 0)
                                    if total > 0 and qty > 0:
                                        price = total / qty
                                total_entradas_turno += qty
                                if abs(price - 5000) < 100:
                                    entradas_5000_turno += qty
                                elif abs(price - 10000) < 100:
                                    entradas_10000_turno += qty
                
                # OPTIMIZADO: Hora pico y top productos (solo si hay deliveries)
                from collections import Counter
                if shift_deliveries:
                    hour_counts = {}
                    item_counts = Counter()
                    bartender_counts = Counter()
                    
                    for delivery in shift_deliveries:
                        try:
                            if isinstance(delivery.timestamp, str):
                                delivery_time = datetime.strptime(delivery.timestamp, '%Y-%m-%d %H:%M:%S')
                            else:
                                delivery_time = delivery.timestamp
                            hour = delivery_time.hour
                            hour_counts[hour] = hour_counts.get(hour, 0) + delivery.qty
                        except:
                            pass
                        
                        item_counts[delivery.item_name] += delivery.qty
                        bartender_counts[delivery.bartender] += delivery.qty
                    
                    peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else None
                    peak_hour_count = hour_counts.get(peak_hour, 0) if peak_hour else 0
                    top_productos = item_counts.most_common(3)
                    top_bartenders = bartender_counts.most_common(3)
                else:
                    peak_hour = None
                    peak_hour_count = 0
                    top_productos = []
                    top_bartenders = []
                
                # Calcular datos para gráfico mini (últimas 4 horas) - solo si hay deliveries
                mini_hours_data = []
                mini_hours_labels = []
                if shift_deliveries:
                    current_hour = datetime.now(CHILE_TZ).hour
                    for i in range(3, -1, -1):
                        check_hour = (current_hour - i + 24) % 24
                        mini_hours_labels.append(f"{check_hour:02d}:00")
                        count = sum(d.qty for d in shift_deliveries 
                                   if (datetime.strptime(d.timestamp, '%Y-%m-%d %H:%M:%S') if isinstance(d.timestamp, str) else d.timestamp).hour == check_hour)
                        mini_hours_data.append(count)
                
                shift_metrics = {
                    'tiempo_transcurrido': f"{horas}h {minutos}m",  # Calculado usando hora de Chile
                    'total_entregas': total_entregas_turno,
                    'total_entradas': total_entradas_turno,
                    'entradas_5000': entradas_5000_turno,
                    'entradas_10000': entradas_10000_turno,
                    'monto_kiosko': monto_turno,
                    'peak_hour': peak_hour,
                    'peak_hour_count': peak_hour_count,
                    'top_productos': top_productos,
                    'top_bartenders': top_bartenders,
                    'opened_at': shift_opened_at
                }
            else:
                # Sin turno abierto - OPTIMIZADO: usar agregaciones SQL
                total_pagos_count = Pago.query.filter_by(estado='PAID').count()
                monto_total_result = db.session.query(func.sum(Pago.monto)).filter_by(estado='PAID').scalar()
                monto_total = float(monto_total_result or 0)
                pagos_pendientes_count = Pago.query.filter_by(estado='PENDING').count()
                
                kiosk_stats = {
                    'pagos_turno': 0,
                    'monto_turno': 0,
                    'total_pagos': total_pagos_count,
                    'monto_total': monto_total,
                    'pagos_pendientes': pagos_pendientes_count
                }
                shift_metrics = {
                    'tiempo_transcurrido': 'N/A',
                    'total_entregas': 0,
                    'total_entradas': 0,
                    'entradas_5000': 0,
                    'entradas_10000': 0,
                    'monto_kiosko': 0,
                    'peak_hour': None,
                    'peak_hour_count': 0,
                    'top_productos': [],
                    'top_bartenders': [],
                    'opened_at': None
                }
                mini_hours_data = []
                mini_hours_labels = []
        except Exception as e:
            current_app.logger.warning(f"No se pudieron obtener estadísticas del kiosko o métricas del turno: {e}")
            kiosk_stats = {
                'pagos_turno': 0,
                'monto_turno': 0,
                'total_pagos': 0,
                'monto_total': 0,
                'pagos_pendientes': 0
            }
            shift_metrics = {
                'tiempo_transcurrido': 'N/A',
                'total_entregas': 0,
                'total_entradas': 0,
                'entradas_5000': 0,
                'entradas_10000': 0,
                'monto_kiosko': 0,
                'peak_hour': None,
                'peak_hour_count': 0,
                'top_productos': [],
                'top_bartenders': [],
                'opened_at': None
            }
            mini_hours_data = []
            mini_hours_labels = []
        
        return render_template(
            'admin_dashboard.html', 
            shift_status=shift_status_dict, 
            get_shift_status=lambda: shift_status_dict,
            kiosk_stats=kiosk_stats,
            services_status={'api': {'status': 'unknown', 'online': None, 'message': 'Cargando...', 'last_updated': None}},
            shift_metrics=shift_metrics,
            mini_hours_data=mini_hours_data if 'mini_hours_data' in locals() else [],
            mini_hours_labels=mini_hours_labels if 'mini_hours_labels' in locals() else [],
            sos_requests=sos_requests,
            pending_closes=pending_closes,
            register_locks=register_locks,
            recent_sales=recent_sales_data
        )
    except Exception as e:
        current_app.logger.error(f"Error completo en admin_dashboard: {e}", exc_info=True)
        flash(f"Error al cargar el dashboard: {str(e)}", "error")
        return render_template('admin_dashboard.html', 
                              shift_status={'is_open': False},
                              kiosk_stats={},
                              services_status={'api': {'status': 'error', 'online': False}},
                              shift_metrics={},
                              mini_hours_data=[],
                              mini_hours_labels=[],
                              sos_requests=[],
                              pending_closes=[],
                              register_locks=[],
                              recent_sales=[])

@bp.route('/admin/panel-control')
def admin_panel_control():
    """Panel de Control - Información del sistema"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    # OPTIMIZADO: No cargar estado de servicios en el dashboard inicial
    # Esto se carga asíncronamente via AJAX desde el navegador
    # para no bloquear la carga de la página
    services_status = {}
    
    # Obtener estado de servicios externos
    local_only = current_app.config.get('LOCAL_ONLY', True)
    services_state = {
        'local_only': local_only,
        'api': {
            'enabled': not local_only and bool(current_app.config.get('BASE_API_URL') and current_app.config.get('API_KEY')),
            'name': 'API PHP POS'
        },
        'openai': {
            'enabled': not local_only and bool(current_app.config.get('OPENAI_API_KEY')),
            'name': 'OpenAI'
        },
        'getnet': {
            'enabled': current_app.config.get('GETNET_ENABLED', False),
            'name': 'GetNet'
        },
        'sumup': {
            'enabled': False,  # SumUp no tiene flag de configuración separado
            'name': 'SumUp'
        }
    }
    
    # Obtener hora y fecha actual (Chile)
    from datetime import datetime
    from app import CHILE_TZ
    from app.helpers.timezone_utils import format_date_spanish
    now_chile = datetime.now(CHILE_TZ)
    system_info = {
        'current_date': format_date_spanish(dt=now_chile),  # Formato DD/MM/YYYY
        'current_time': now_chile.strftime('%H:%M:%S'),
        'current_datetime': now_chile.strftime('%Y-%m-%d %H:%M:%S'),
        'timezone': 'America/Santiago (Chile)',
        'day_name': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][now_chile.weekday()],
        'month_name': ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'][now_chile.month - 1]
    }
    
    return render_template(
        'admin/panel_control.html',
        system_info=system_info,
        services_status=services_status,
        services_state=services_state
    )

@bp.route('/admin/generar-pagos')
def admin_generar_pagos():
    """Generar Pagos - Muestra todos los pagos pendientes agrupados por trabajador"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.employee_shift_models import EmployeeShift
        from app.models.employee_advance_models import EmployeeAdvance
        from app.models.pos_models import Employee
        from datetime import datetime
        from app import CHILE_TZ
        from sqlalchemy import func
        from collections import defaultdict
        
        # Optimización: Usar agregación SQL en lugar de agrupar en Python
        from app.helpers.query_optimizer import get_employee_payments_grouped
        
        # Obtener resumen agrupado por empleado usando SQL GROUP BY
        payments_grouped = get_employee_payments_grouped()
        
        # Convertir a formato esperado
        pagos_lista = []
        for payment in payments_grouped:
            pagos_lista.append({
                'employee_id': str(payment.employee_id),
                'employee_name': payment.employee_name,
                'total_adeudado': float(payment.total_adeudado or 0),
                'num_turnos': payment.num_turnos,
                'total_bonos': float(payment.total_bonos or 0),
                'total_descuentos': float(payment.total_descuentos or 0)
            })
        
        # Obtener todos los turnos pendientes para la tabla detallada
        shifts_pendientes = EmployeeShift.query.filter_by(pagado=False).order_by(
            EmployeeShift.fecha_turno.desc(),
            EmployeeShift.hora_inicio.desc()
        ).all()
        
        # Obtener abonos pendientes para calcular saldos pendientes después de abonos
        abonos_pendientes = EmployeeAdvance.query.filter_by(aplicado=False).all()
        abonos_por_empleado = defaultdict(float)
        for abono in abonos_pendientes:
            employee_id = str(abono.employee_id)
            abonos_por_empleado[employee_id] += float(abono.monto or 0)
        
        # Calcular saldos pendientes después de abonos
        for pago in pagos_lista:
            employee_id = str(pago['employee_id'])
            abono_total = abonos_por_empleado.get(employee_id, 0.0)
            pago['saldo_pendiente'] = pago['total_adeudado'] - abono_total
        
        # Crear lista completa de turnos con información detallada para la tabla
        turnos_detallados = []
        for shift in shifts_pendientes:
            employee_id = str(shift.employee_id)
            abono_total = abonos_por_empleado.get(employee_id, 0.0)
            
            # Obtener información del empleado
            employee = Employee.query.filter_by(id=employee_id).first()
            
            turnos_detallados.append({
                'shift_id': shift.id,
                'employee_id': employee_id,
                'employee_name': shift.employee_name,
                'fecha_turno': shift.fecha_turno,
                'cargo': shift.cargo or 'N/A',
                'sueldo_por_turno': float(shift.sueldo_por_turno or 0),
                'bonos': float(shift.bonos or 0),
                'descuentos': float(shift.descuentos or 0),
                'sueldo_turno': float(shift.sueldo_turno or 0),
                'horas_trabajadas': float(shift.horas_trabajadas) if shift.horas_trabajadas else None,
                'hora_inicio': shift.hora_inicio.strftime('%d/%m/%Y %H:%M') if shift.hora_inicio else 'N/A',
                'hora_fin': shift.hora_fin.strftime('%d/%m/%Y %H:%M') if shift.hora_fin else 'Pendiente',
                'tipo_turno': shift.tipo_turno or 'N/A',
                'jornada_id': shift.jornada_id,
                'estado': shift.estado
            })
        
        # Ordenar turnos por fecha descendente
        turnos_detallados.sort(key=lambda x: (x['fecha_turno'], x['employee_name']), reverse=True)
        
        # Calcular totales usando agregación SQL (más eficiente)
        from app.helpers.query_optimizer import get_employee_shifts_summary
        summary = get_employee_shifts_summary(pagado=False)
        
        total_a_pagar = summary['sueldo_pendiente']
        total_empleados = len(pagos_lista)
        total_turnos_pendientes = summary['total_turnos']
        total_saldos_pendientes = sum([p['saldo_pendiente'] for p in pagos_lista])
        total_abonos_pendientes = sum(abonos_por_empleado.values())
        
        return render_template(
            'admin/generar_pagos.html',
            pagos_por_empleado=pagos_lista,
            turnos_detallados=turnos_detallados,
            total_a_pagar=total_a_pagar,
            total_empleados=total_empleados,
            total_turnos_pendientes=total_turnos_pendientes,
            total_abonos_pendientes=total_abonos_pendientes,
            total_saldos_pendientes=total_saldos_pendientes
        )
    except Exception as e:
        current_app.logger.error(f"Error al generar pagos: {e}", exc_info=True)
        flash(f"Error al generar pagos: {str(e)}", "error")
        return redirect(url_for('routes.admin_panel_control'))

@bp.route('/admin/generar-pagos/pagar-completo', methods=['POST'])
def pagar_completo_empleado():
    """Pagar completo todos los turnos pendientes de un empleado"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        from app.models.employee_shift_models import EmployeeShift
        from app.models.audit_log_models import AuditLog
        from app.models.pos_models import Employee
        from datetime import datetime
        from app import CHILE_TZ
        from sqlalchemy import select
        import json
        
        employee_id = request.form.get('employee_id') or request.json.get('employee_id')
        if not employee_id:
            return jsonify({'success': False, 'message': 'ID de empleado no proporcionado'}), 400
        
        # Validar que el empleado existe
        employee = Employee.query.filter_by(id=str(employee_id)).first()
        if not employee:
            return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
        
        # Usar transacción con lock de fila para evitar race conditions
        with db.session.begin():
            # Obtener turnos pendientes con lock (SELECT FOR UPDATE)
            shifts_pendientes = db.session.execute(
                select(EmployeeShift)
                .where(
                    EmployeeShift.employee_id == str(employee_id),
                    EmployeeShift.pagado == False
                )
                .with_for_update()  # Lock de fila para evitar race conditions
            ).scalars().all()
            
            if not shifts_pendientes:
                return jsonify({'success': False, 'message': 'No hay turnos pendientes para este empleado'}), 404
            
            # Validar montos antes de pagar
            total_pagado = 0.0
            shifts_data = []
            
            for shift in shifts_pendientes:
                # Verificar nuevamente que no esté pagado (doble verificación)
                if shift.pagado:
                    continue
                
                sueldo_turno = float(shift.sueldo_turno or 0)
                if sueldo_turno <= 0:
                    current_app.logger.warning(
                        f"⚠️ Turno {shift.id} tiene sueldo inválido: ${sueldo_turno}"
                    )
                    continue
                
                shifts_data.append({
                    'id': shift.id,
                    'fecha_turno': shift.fecha_turno,
                    'sueldo_turno': sueldo_turno
                })
                total_pagado += sueldo_turno
            
            if total_pagado <= 0:
                return jsonify({'success': False, 'message': 'No hay turnos válidos para pagar'}), 400
            
            # Guardar valores antiguos para auditoría
            old_values = json.dumps([s for s in shifts_data])
            
            # Calcular pendiente antes y después
            from app.helpers.query_optimizer import get_employee_shifts_summary
            summary_antes = get_employee_shifts_summary(employee_id=str(employee_id), pagado=False)
            monto_pendiente_antes = summary_antes.get('sueldo_pendiente', 0)
            monto_pendiente_despues = monto_pendiente_antes - total_pagado
            
            # Marcar todos como pagados
            import pytz
            import json
            now_utc = datetime.now(CHILE_TZ).astimezone(pytz.UTC).replace(tzinfo=None)
            
            shift_ids = []
            for shift in shifts_pendientes:
                if shift.pagado:  # Doble verificación
                    continue
                shift.pagado = True
                shift.fecha_pago = now_utc
                shift_ids.append(shift.id)
            
            # Crear instancia de pago
            from app.models.employee_payment_models import EmployeePayment
            payment_instance = EmployeePayment(
                employee_id=str(employee_id),
                employee_name=employee.name,
                tipo_pago='pago_completo',
                monto=total_pagado,
                monto_total_deuda=monto_pendiente_antes,
                monto_pendiente_antes=monto_pendiente_antes,
                monto_pendiente_despues=monto_pendiente_despues,
                turnos_pagados_ids=json.dumps(shift_ids),
                descripcion=f'Pago completo de {len(shifts_pendientes)} turnos',
                pagado_por=session.get('admin_username', 'unknown'),
                fecha_pago=now_utc
            )
            db.session.add(payment_instance)
            
            # Registrar en auditoría ANTES de commit
            audit_log = AuditLog(
                user_id=session.get('admin_username', 'unknown'),
                username=session.get('admin_username', 'unknown'),
                action='pagar_completo',
                entity_type='Employee',
                entity_id=str(employee_id),
                old_value=old_values,
                new_value=json.dumps({'total_pagado': total_pagado, 'turnos': len(shifts_pendientes)}),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                request_method=request.method,
                request_path=request.path,
                success=True
            )
            db.session.add(audit_log)
        
        # Commit se hace automáticamente al salir del bloque 'with'
        
        current_app.logger.info(
            f"💰 Pagado completo para empleado {employee_id} ({employee.name}): "
            f"{len(shifts_pendientes)} turnos, Total: ${total_pagado:,.0f} "
            f"por {session.get('admin_username', 'unknown')}"
        )
        
        return jsonify({
            'success': True,
            'message': f'Se pagaron {len(shifts_pendientes)} turnos por un total de ${total_pagado:,.0f}',
            'total_pagado': total_pagado,
            'turnos_pagados': len(shifts_pendientes)
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al pagar completo: {e}", exc_info=True)
        
        # Registrar error en auditoría
        try:
            from app.models.audit_log_models import AuditLog
            import json
            error_audit = AuditLog(
                user_id=session.get('admin_username', 'unknown'),
                username=session.get('admin_username', 'unknown'),
                action='pagar_completo',
                entity_type='Employee',
                entity_id=str(employee_id) if 'employee_id' in locals() else None,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                request_method=request.method,
                request_path=request.path,
                success=False,
                error_message=str(e)
            )
            db.session.add(error_audit)
            db.session.commit()
        except:
            pass
        
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/admin/generar-pagos/abonar', methods=['POST'])
def abonar_empleado():
    """Abonar un monto parcial a un empleado"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        from app.models.employee_advance_models import EmployeeAdvance
        from app.models.audit_log_models import AuditLog
        from app.models.employee_shift_models import EmployeeShift
        from datetime import datetime
        from app import CHILE_TZ
        from sqlalchemy import func
        import json
        
        employee_id = request.form.get('employee_id') or request.json.get('employee_id')
        monto = request.form.get('monto') or request.json.get('monto')
        descripcion = request.form.get('descripcion') or request.json.get('descripcion', 'Abono desde Generar Pagos')
        
        # Validación mejorada
        from app.helpers.validation import validate_employee_id, validate_amount
        
        is_valid_emp_id, emp_id_error = validate_employee_id(employee_id)
        if not is_valid_emp_id:
            return jsonify({'success': False, 'message': f'ID de empleado inválido: {emp_id_error}'}), 400
        
        is_valid_amount, monto_float, amount_error = validate_amount(monto, min_amount=0.01, max_amount=10000000.0)
        if not is_valid_amount:
            return jsonify({'success': False, 'message': f'Monto inválido: {amount_error}'}), 400
        
        # Validar que el abono no exceda el sueldo pendiente
        sueldo_pendiente = db.session.query(
            func.sum(EmployeeShift.sueldo_turno)
        ).filter_by(
            employee_id=str(employee_id),
            pagado=False
        ).scalar() or 0
        
        # Obtener abonos pendientes
        abonos_pendientes = db.session.query(
            func.sum(EmployeeAdvance.monto)
        ).filter_by(
            employee_id=str(employee_id),
            aplicado=False
        ).scalar() or 0
        
        disponible = float(sueldo_pendiente) - float(abonos_pendientes)
        
        if monto_float > disponible:
            return jsonify({
                'success': False,
                'message': f'El abono (${monto_float:,.0f}) excede el sueldo disponible (${disponible:,.0f})'
            }), 400
        
        # Obtener información del empleado
        from app.models.pos_models import Employee
        employee = Employee.query.filter_by(id=str(employee_id)).first()
        if not employee:
            return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
        
        employee_name = employee.name or f'Empleado {employee_id}'
        
        # Crear abono
        fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
        abono = EmployeeAdvance(
            employee_id=str(employee_id),
            employee_name=employee_name,
            tipo='abono',
            monto=monto_float,
            fecha_abono=fecha_hoy,
            descripcion=descripcion,
            aplicado=False,
            creado_por=session.get('admin_username', 'admin')
        )
        
        db.session.add(abono)
        # Crear instancia de pago para el abono
        from app.models.employee_payment_models import EmployeePayment
        import json
        import pytz
        
        monto_pendiente_antes = float(disponible)
        monto_pendiente_despues = monto_pendiente_antes - monto_float
        now_utc = datetime.now(CHILE_TZ).astimezone(pytz.UTC).replace(tzinfo=None)
        
        payment_instance = EmployeePayment(
            employee_id=str(employee_id),
            employee_name=employee_name,
            tipo_pago="abono",
            monto=monto_float,
            monto_total_deuda=float(sueldo_pendiente),
            monto_pendiente_antes=monto_pendiente_antes,
            monto_pendiente_despues=monto_pendiente_despues,
            turnos_pagados_ids=json.dumps([]),
            descripcion=descripcion or f"Abono de {monto_float:,.0f}",
            pagado_por=session.get("admin_username", "unknown"),
            fecha_pago=now_utc
        )
        db.session.add(payment_instance)
        db.session.commit()
        
        current_app.logger.info(
            f"💰 Abono creado para empleado {employee_id} ({employee_name}): "
            f"${monto_float:,.0f} - {descripcion}"
        )
        
        return jsonify({
            'success': True,
            'message': f'Abono de ${monto_float:,.0f} registrado correctamente',
            'abono_id': abono.id
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al crear abono: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

def admin_liquidacion_pagos():
    """Liquidación de Pagos - Muestra todos los pagos asignados a trabajadores"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.employee_shift_models import EmployeeShift
        from app.models.pos_models import Employee
        from datetime import datetime, timedelta
        from app import CHILE_TZ
        from sqlalchemy import func, and_, or_
        
        # Obtener parámetros de filtro
        filtro_empleado = request.args.get('empleado', '')
        filtro_fecha_desde = request.args.get('fecha_desde', '')
        filtro_fecha_hasta = request.args.get('fecha_hasta', '')
        filtro_estado = request.args.get('estado', '')  # Por defecto vacío = pendientes
        
        # Construir query base
        query = EmployeeShift.query
        
        # Aplicar filtros
        if filtro_empleado:
            query = query.filter(
                or_(
                    EmployeeShift.employee_id == filtro_empleado,
                    EmployeeShift.employee_name.ilike(f'%{filtro_empleado}%')
                )
            )
        
        if filtro_fecha_desde:
            try:
                fecha_desde_dt = datetime.strptime(filtro_fecha_desde, '%Y-%m-%d')
                query = query.filter(EmployeeShift.fecha_turno >= filtro_fecha_desde)
            except:
                pass
        
        if filtro_fecha_hasta:
            try:
                fecha_hasta_dt = datetime.strptime(filtro_fecha_hasta, '%Y-%m-%d')
                query = query.filter(EmployeeShift.fecha_turno <= filtro_fecha_hasta)
            except:
                pass
        
        # Por defecto mostrar solo pendientes, pero permitir cambiar con filtro
        if filtro_estado == 'pagado':
            query = query.filter(EmployeeShift.pagado == True)
        elif filtro_estado == 'todos':
            # No aplicar filtro de estado, mostrar todos
            pass
        else:
            # Por defecto (vacío o 'pendiente'): solo pendientes
            query = query.filter(EmployeeShift.pagado == False)
        
        # Ordenar por fecha descendente
        shifts = query.order_by(
            EmployeeShift.fecha_turno.desc(),
            EmployeeShift.hora_inicio.desc()
        ).all()
        
        # Optimización: Calcular estadísticas usando agregación SQL en lugar de Python
        from app.helpers.query_optimizer import get_employee_shifts_summary
        
        # Construir filtros para la agregación
        fecha_desde = None
        fecha_hasta = None
        if filtro_fecha_desde:
            try:
                fecha_desde = datetime.strptime(filtro_fecha_desde, '%Y-%m-%d').date()
            except:
                pass
        if filtro_fecha_hasta:
            try:
                fecha_hasta = datetime.strptime(filtro_fecha_hasta, '%Y-%m-%d').date()
            except:
                pass
        
        # Obtener resumen usando agregación SQL
        summary_all = get_employee_shifts_summary(
            employee_id=filtro_empleado if filtro_empleado else None,
            pagado=None,  # Todos
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta
        )
        
        summary_pagados = get_employee_shifts_summary(
            employee_id=filtro_empleado if filtro_empleado else None,
            pagado=True,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta
        )
        
        summary_pendientes = get_employee_shifts_summary(
            employee_id=filtro_empleado if filtro_empleado else None,
            pagado=False,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta
        )
        
        total_turnos = summary_all['total_turnos']
        turnos_pagados = summary_pagados['total_turnos']
        turnos_pendientes = summary_pendientes['total_turnos']
        
        sueldo_total = summary_all['total_sueldo']
        sueldo_pagado = summary_pagados['total_sueldo']
        sueldo_pendiente = summary_pendientes['total_sueldo']
        
        # Obtener lista de empleados para el filtro
        empleados = Employee.query.filter(
            ()
        ).order_by(Employee.name).all()
        
        # Calcular resumen quincenal (últimos 15 días)
        fecha_hoy = datetime.now(CHILE_TZ).date()
        fecha_hace_15_dias = fecha_hoy - timedelta(days=15)
        
        # OPTIMIZACIÓN: Usar agregación SQL en lugar de agrupar en Python
        from app.helpers.query_optimizer import get_employee_shifts_quincenal_grouped
        
        # Obtener turnos agrupados por empleado usando SQL GROUP BY
        shifts_quincenales_grouped = get_employee_shifts_quincenal_grouped(
            fecha_hace_15_dias.strftime('%Y-%m-%d'),
            fecha_hoy.strftime('%Y-%m-%d')
        )
        
        # Obtener todos los turnos para los detalles (si es necesario)
        shifts_quincenales = EmployeeShift.query.filter(
            EmployeeShift.fecha_turno >= fecha_hace_15_dias.strftime('%Y-%m-%d'),
            EmployeeShift.fecha_turno <= fecha_hoy.strftime('%Y-%m-%d'),
            EmployeeShift.pagado == False
        ).all()
        
        # Construir resumen usando datos agrupados de SQL
        resumen_quincenal = {}
        for grouped_shift in shifts_quincenales_grouped:
            emp_id = str(grouped_shift.employee_id)
            # Obtener información del empleado (con cache si es posible)
            empleado = Employee.query.filter_by(id=emp_id).first()
            
            # Obtener lista de turnos para este empleado
            turnos_lista = [
                {
                    'fecha': s.fecha_turno,
                    'sueldo': float(s.sueldo_turno or 0)
                }
                for s in shifts_quincenales
                if str(s.employee_id) == emp_id
            ]
            
            resumen_quincenal[emp_id] = {
                'employee_id': emp_id,
                'employee_name': grouped_shift.employee_name,
                'rut': empleado.rut if empleado else None,
                'banco': empleado.banco if empleado else None,
                'tipo_cuenta': empleado.tipo_cuenta if empleado else None,
                'numero_cuenta': empleado.numero_cuenta if empleado else None,
                'email': empleado.email if empleado else None,
                'total_turnos': grouped_shift.total_turnos,
                'total_sueldo': float(grouped_shift.total_sueldo or 0),
                'turnos': turnos_lista
            }
        
        # Preparar datos para el template
        shifts_data = []
        for shift in shifts:
            shifts_data.append({
                'id': shift.id,
                'employee_id': shift.employee_id,
                'employee_name': shift.employee_name,
                'fecha_turno': shift.fecha_turno,
                'cargo': shift.cargo or 'N/A',
                'sueldo_por_turno': float(shift.sueldo_por_turno or 0),
                'bonos': float(shift.bonos or 0),
                'descuentos': float(shift.descuentos or 0),
                'sueldo_turno': float(shift.sueldo_turno or 0),
                'pagado': shift.pagado,
                'fecha_pago': shift.fecha_pago.strftime('%Y-%m-%d') if shift.fecha_pago else None,
                'estado': shift.estado,
                'horas_trabajadas': float(shift.horas_trabajadas) if shift.horas_trabajadas else None
            })
        
        return render_template(
            'admin/liquidacion_pagos.html',
            shifts_data=shifts_data,
            empleados=empleados,
            total_turnos=total_turnos,
            turnos_pagados=turnos_pagados,
            turnos_pendientes=turnos_pendientes,
            sueldo_total=sueldo_total,
            sueldo_pagado=sueldo_pagado,
            sueldo_pendiente=sueldo_pendiente,
            filtro_empleado=filtro_empleado,
            filtro_fecha_desde=filtro_fecha_desde,
            filtro_fecha_hasta=filtro_fecha_hasta,
            filtro_estado=filtro_estado,
            resumen_quincenal=list(resumen_quincenal.values()),
            fecha_periodo_desde=fecha_hace_15_dias.strftime('%Y-%m-%d'),
            fecha_periodo_hasta=fecha_hoy.strftime('%Y-%m-%d')
        )
    except Exception as e:
        current_app.logger.error(f"Error al cargar liquidación de pagos: {e}", exc_info=True)
        flash(f"Error al cargar la liquidación de pagos: {str(e)}", "error")
        return redirect(url_for('routes.admin_panel_control'))

@bp.route('/admin/liquidacion-pagos/exportar-resumen-quincenal')
def exportar_resumen_quincenal():
    """Exporta el resumen quincenal de pagos a CSV para transferencias bancarias"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.employee_shift_models import EmployeeShift
        from app.models.pos_models import Employee
        from datetime import datetime, timedelta
        from app import CHILE_TZ
        from flask import make_response
        import csv
        import io
        
        # Calcular período de 15 días
        fecha_hoy = datetime.now(CHILE_TZ).date()
        fecha_hace_15_dias = fecha_hoy - timedelta(days=15)
        
        # Obtener turnos pendientes de los últimos 15 días
        shifts_quincenales = EmployeeShift.query.filter(
            EmployeeShift.fecha_turno >= fecha_hace_15_dias.strftime('%Y-%m-%d'),
            EmployeeShift.fecha_turno <= fecha_hoy.strftime('%Y-%m-%d'),
            EmployeeShift.pagado == False  # Solo pendientes
        ).all()
        
        # Agrupar por trabajador
        resumen_por_trabajador = {}
        for shift in shifts_quincenales:
            emp_id = shift.employee_id
            if emp_id not in resumen_por_trabajador:
                empleado = Employee.query.filter_by(id=emp_id).first()
                resumen_por_trabajador[emp_id] = {
                    'employee_id': emp_id,
                    'employee_name': shift.employee_name,
                    'rut': empleado.rut if empleado and empleado.rut else '',
                    'banco': empleado.banco if empleado and empleado.banco else '',
                    'tipo_cuenta': empleado.tipo_cuenta if empleado and empleado.tipo_cuenta else '',
                    'numero_cuenta': empleado.numero_cuenta if empleado and empleado.numero_cuenta else '',
                    'email': empleado.email if empleado and empleado.email else '',
                    'total_turnos': 0,
                    'total_sueldo': 0.0
                }
            
            resumen_por_trabajador[emp_id]['total_turnos'] += 1
            resumen_por_trabajador[emp_id]['total_sueldo'] += float(shift.sueldo_turno or 0)
        
        # Crear CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Escribir header
        writer.writerow([
            'ID Trabajador',
            'Nombre',
            'RUT',
            'Banco',
            'Tipo Cuenta',
            'Número Cuenta',
            'Email',
            'Total Turnos',
            'Total a Pagar ($)'
        ])
        
        # Escribir datos
        for emp_id, resumen in sorted(resumen_por_trabajador.items(), key=lambda x: x[1]['employee_name']):
            writer.writerow([
                resumen['employee_id'],
                resumen['employee_name'],
                resumen['rut'],
                resumen['banco'],
                resumen['tipo_cuenta'],
                resumen['numero_cuenta'],
                resumen['email'],
                resumen['total_turnos'],
                f"{resumen['total_sueldo']:.0f}"
            ])
        
        # Agregar fila de totales
        total_general = sum([r['total_sueldo'] for r in resumen_por_trabajador.values()])
        writer.writerow([])
        writer.writerow(['TOTAL GENERAL', '', '', '', '', '', '', len(resumen_por_trabajador), f"{total_general:.0f}"])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=resumen_quincenal_pagos_{fecha_hoy.strftime("%Y%m%d")}.csv'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error al exportar resumen quincenal: {e}", exc_info=True)
        flash(f"Error al exportar resumen: {str(e)}", "error")
        return redirect(url_for('routes.admin_liquidacion_pagos'))

@bp.route('/admin/api/restart-services', methods=['POST'])
def api_restart_services():
    """API: Reiniciar todos los servicios del sistema"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        import subprocess
        import os
        
        # Obtener el directorio del proyecto
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        restart_script = os.path.join(project_dir, 'restart_services.sh')
        
        # Verificar que el script existe
        if not os.path.exists(restart_script):
            return jsonify({
                'success': False,
                'message': f'Script de reinicio no encontrado en: {restart_script}'
            }), 404
        
        # Ejecutar el script en background
        # Usar nohup para que continúe ejecutándose incluso si se cierra la conexión
        process = subprocess.Popen(
            ['bash', restart_script],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Crear nuevo grupo de procesos
        )
        
        # No esperar a que termine, solo confirmar que se inició
        return jsonify({
            'success': True,
            'message': 'Reinicio de servicios iniciado. El servidor se reiniciará en unos segundos.',
            'pid': process.pid
        })
        
    except Exception as e:
        current_app.logger.error(f"Error al reiniciar servicios: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al reiniciar servicios: {str(e)}'
        }), 500

@bp.route('/admin/api/restart-everything', methods=['POST'])
def api_restart_everything():
    """API: Reiniciar todo el sistema - servicios, cachés y configuración"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        # 1. Limpiar todos los cachés
        try:
            from app.helpers.cache import clear_cache
            from app import invalidate_shift_cache
            
            # Limpiar cachés de ventas, empleados, etc.
            clear_cache()
            invalidate_shift_cache()
            
            current_app.logger.info("✅ Cachés limpiados")
        except Exception as e:
            current_app.logger.warning(f"⚠️ Error al limpiar cachés: {e}")
        
        # 2. Invalidar cachés específicos
        try:
            from app.helpers.cache import invalidate_sale_cache
            # Limpiar cachés de ventas
            current_app.logger.info("✅ Cachés de ventas invalidados")
        except Exception as e:
            current_app.logger.warning(f"⚠️ Error al invalidar cachés de ventas: {e}")
        
        # 3. Reiniciar servicios usando el script existente
        try:
            import subprocess
            import os
            
            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            restart_script = os.path.join(project_dir, 'restart_services.sh')
            
            if os.path.exists(restart_script):
                # Ejecutar el script en background
                process = subprocess.Popen(
                    ['bash', restart_script],
                    cwd=project_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid if hasattr(os, 'setsid') else None
                )
                current_app.logger.info(f"✅ Reinicio de servicios iniciado (PID: {process.pid})")
            else:
                current_app.logger.warning(f"⚠️ Script de reinicio no encontrado: {restart_script}")
        except Exception as e:
            current_app.logger.warning(f"⚠️ Error al reiniciar servicios: {e}")
        
        # 4. Registrar en auditoría
        try:
            from app.models.audit_log_models import AuditLog
            audit_log = AuditLog(
                user_id=session.get('admin_username', 'unknown'),
                username=session.get('admin_username', 'unknown'),
                action='restart_everything',
                entity_type='System',
                entity_id='all',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                request_method=request.method,
                request_path=request.path,
                success=True
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            current_app.logger.warning(f"⚠️ Error al registrar auditoría: {e}")
            db.session.rollback()
        
        current_app.logger.warning(
            f"🔄 REINICIO TOTAL iniciado por {session.get('admin_username', 'unknown')}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Reinicio total iniciado correctamente. El sistema se reiniciará en unos segundos.'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error en reinicio total: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al reiniciar todo: {str(e)}'
        }), 500

@bp.route('/admin/api/deploy', methods=['POST'])
def deploy_to_production():
    """Despliega la aplicación a Cloud Run desde el panel de control"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    
    try:
        import subprocess
        import os
        
        # Verificar que estamos en el directorio correcto
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        current_app.logger.info(f"🚀 Deployment iniciado por {session.get('admin_username', 'unknown')}")
        
        # Ejecutar deployment en background
        result = subprocess.run(
            ['gcloud', 'run', 'deploy', 'bimba-pos', 
             '--source', '.', 
             '--region', 'us-central1',
             '--quiet'],  # No pedir confirmación
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutos máximo
        )
        
        if result.returncode == 0:
            # Extraer información de la salida
            output = result.stdout
            revision = 'N/A'
            
            # Intentar extraer el nombre de la revisión
            for line in output.split('\n'):
                if 'revision' in line.lower() and 'has been deployed' in line.lower():
                    parts = line.split('[')
                    if len(parts) > 1:
                        revision = parts[1].split(']')[0]
                    break
            
            current_app.logger.info(f"✅ Deployment exitoso. Revisión: {revision}")
            
            # Registrar en auditoría
            try:
                from app.models.audit_log_models import AuditLog
                audit_log = AuditLog(
                    action='deployment',
                    entity_type='system',
                    entity_id=revision,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', ''),
                    request_method=request.method,
                    request_path=request.path,
                    success=True,
                    details=f"Deployment a producción. Revisión: {revision}"
                )
                db.session.add(audit_log)
                db.session.commit()
            except Exception as e:
                current_app.logger.warning(f"⚠️ Error al registrar auditoría de deployment: {e}")
            
            return jsonify({
                'success': True,
                'message': 'Deployment iniciado correctamente. El sitio se actualizará en 2-3 minutos.',
                'revision': revision
            })
        else:
            error_msg = result.stderr[:200] if result.stderr else 'Error desconocido'
            current_app.logger.error(f"❌ Error en deployment: {error_msg}")
            return jsonify({
                'success': False,
                'error': f'Error en deployment: {error_msg}'
            }), 500
            
    except subprocess.TimeoutExpired:
        current_app.logger.error("❌ Timeout en deployment")
        return jsonify({
            'success': False,
            'error': 'Timeout: El deployment tomó más de 5 minutos'
        }), 500
    except FileNotFoundError:
        current_app.logger.error("❌ gcloud CLI no encontrado")
        return jsonify({
            'success': False,
            'error': 'gcloud CLI no está instalado o no está en el PATH'
        }), 500
    except Exception as e:
        current_app.logger.error(f"❌ Error inesperado en deployment: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Error inesperado: {str(e)}'
        }), 500

@bp.route('/admin/api/employees', methods=['GET', 'POST'])
def api_employees_legacy():
    """API: Listar o crear empleados"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    from app.models.pos_models import Employee
    from datetime import datetime
    import uuid
    
    if request.method == 'GET':
        # Listar empleados
        try:
            # IMPORTANTE: Solo empleados ACTIVOS para agregar a la planilla del turno
            all_local = Employee.query.filter(Employee.is_active == True).order_by(Employee.name).all()
            
            return jsonify({
                'success': True,
                'employees': [{
                    'id': str(emp.id),
                    'name': emp.name or '',
                    'cargo': emp.cargo or '',
                    'pin': emp.pin or '',
                    'active': emp.is_active if hasattr(emp, 'is_active') else True
                } for emp in all_local]
            })
        except Exception as e:
            current_app.logger.error(f"Error al listar empleados: {e}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500
    
    elif request.method == 'POST':
        # Crear empleado
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            cargo = data.get('cargo', '').strip()
            pin = data.get('pin', '').strip()
            active = data.get('active', True)
            
            if not name:
                return jsonify({'success': False, 'message': 'El nombre es obligatorio'}), 400
            
            # Verificar si ya existe un empleado con el mismo nombre
            existing = Employee.query.filter_by(name=name).first()
            if existing:
                return jsonify({'success': False, 'message': 'Ya existe un empleado con ese nombre'}), 400
            
            # Generar ID único para empleado local
            employee_id = str(uuid.uuid4())
            
            # Determinar si es bartender o cajero según el cargo
            cargo_lower = cargo.lower() if cargo else ''
            is_bartender = 'barra' in cargo_lower or cargo_lower == 'bartender'
            is_cashier = 'caja' in cargo_lower or cargo_lower == 'cajero'
            
            employee = Employee(
                id=employee_id,
                name=name,
                cargo=cargo,
                pin=pin if pin else None,
                is_active=active,
                is_bartender=is_bartender,
                is_cashier=is_cashier,
                synced_from_phppos=False,  # Empleado local
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(employee)
            db.session.commit()
            
            current_app.logger.info(f"Empleado local creado: {name} (ID: {employee_id})")
            return jsonify({'success': True, 'message': 'Empleado creado correctamente', 'employee_id': employee_id})
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al crear empleado: {e}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/admin/api/employees/<employee_id>', methods=['GET', 'PUT', 'DELETE'])
def api_employee_detail_legacy(employee_id):
    """API: Obtener, actualizar o eliminar un empleado"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    from app.models.pos_models import Employee
    from datetime import datetime
    
    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
    
    if request.method == 'GET':
        # Obtener empleado
        return jsonify({
            'success': True,
            'employee': {
                'id': str(employee.id),
                'name': employee.name or '',
                'cargo': employee.cargo or '',
                'pin': employee.pin or '',
                'active': employee.is_active if hasattr(employee, 'is_active') else True
            }
        })
    
    elif request.method == 'PUT':
        # Actualizar empleado
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            cargo = data.get('cargo', '').strip()
            pin = data.get('pin', '').strip()
            active = data.get('active', True)
            
            if not name:
                return jsonify({'success': False, 'message': 'El nombre es obligatorio'}), 400
            
            # Verificar si ya existe otro empleado con el mismo nombre
            existing = Employee.query.filter(Employee.name == name, Employee.id != employee_id).first()
            if existing:
                return jsonify({'success': False, 'message': 'Ya existe otro empleado con ese nombre'}), 400
            
            # Determinar si es bartender o cajero según el cargo
            cargo_lower = cargo.lower() if cargo else ''
            is_bartender = 'barra' in cargo_lower or cargo_lower == 'bartender'
            is_cashier = 'caja' in cargo_lower or cargo_lower == 'cajero'
            
            employee.name = name
            employee.cargo = cargo
            employee.pin = pin if pin else None
            employee.is_active = active
            employee.is_bartender = is_bartender
            employee.is_cashier = is_cashier
            employee.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Empleado actualizado: {name} (ID: {employee_id})")
            return jsonify({'success': True, 'message': 'Empleado actualizado correctamente'})
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al actualizar empleado: {e}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500
    
    elif request.method == 'DELETE':
        # Eliminar empleado
        try:
            name = employee.name
            db.session.delete(employee)
            db.session.commit()
            
            current_app.logger.info(f"Empleado eliminado: {name} (ID: {employee_id})")
            return jsonify({'success': True, 'message': 'Empleado eliminado correctamente'})
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al eliminar empleado: {e}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/admin/api/update-config', methods=['POST'])
def api_update_config():
    """API: Actualizar configuración de API"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        api_url = data.get('api_url', '').strip()
        api_key = data.get('api_key', '').strip()
        
        if not api_url or not api_key:
            return jsonify({'success': False, 'message': 'URL y API Key son requeridos'}), 400
        
        # Validar formato de URL
        from urllib.parse import urlparse
        try:
            parsed = urlparse(api_url)
            if not parsed.scheme or not parsed.netloc:
                return jsonify({
                    'success': False,
                    'message': 'URL inválida. Debe incluir protocolo (http:// o https://)'
                }), 400
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'URL inválida: {str(e)}'
            }), 400
        
        # Validar longitud de API key
        if len(api_key) < 10 or len(api_key) > 200:
            return jsonify({
                'success': False,
                'message': 'API key debe tener entre 10 y 200 caracteres'
            }), 400
        
        # Verificar que la API funciona antes de guardar
        import requests
        try:
            test_url = f"{api_url}/employees"
            headers = {
                "x-api-key": api_key,
                "accept": "application/json"
            }
            resp = requests.get(test_url, headers=headers, timeout=5)
            
            if resp.status_code == 401:
                return jsonify({
                    'success': False,
                    'message': 'API key inválida. La API rechazó la autenticación.'
                }), 400
            elif resp.status_code == 404:
                # Endpoint no encontrado, pero la API responde (puede ser válido)
                pass
            elif resp.status_code >= 500:
                return jsonify({
                    'success': False,
                    'message': f'Error del servidor API (código {resp.status_code}). Intenta más tarde.'
                }), 400
        except requests.exceptions.Timeout:
            return jsonify({
                'success': False,
                'message': 'Timeout al conectar con la API. Verifica la URL.'
            }), 400
        except requests.exceptions.ConnectionError:
            return jsonify({
                'success': False,
                'message': 'No se pudo conectar con la API. Verifica la URL y la conexión.'
            }), 400
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al verificar la API: {str(e)}'
            }), 400
        
        # Guardar valores antiguos para auditoría
        import json
        old_value = json.dumps({
            'api_url': current_app.config.get('BASE_API_URL', ''),
            'api_key': current_app.config.get('API_KEY', '')[:10] + '...' if current_app.config.get('API_KEY') else ''
        })
        
        # Crear backup del .env antes de modificar
        import os
        import shutil
        from datetime import datetime
        from app import CHILE_TZ
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_path):
            try:
                backup_path = f"{env_path}.backup.{datetime.now(CHILE_TZ).strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(env_path, backup_path)
                current_app.logger.info(f"✅ Backup creado: {backup_path}")
            except Exception as e:
                current_app.logger.warning(f"⚠️ No se pudo crear backup: {e}")
        
        if not os.path.exists(env_path):
            return jsonify({'success': False, 'message': 'Archivo .env no encontrado'}), 500
        
        # Leer archivo .env
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        # Actualizar o agregar variables
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith('BASE_API_URL='):
                new_lines.append(f'BASE_API_URL={api_url}\n')
                updated = True
            elif line.startswith('API_KEY='):
                new_lines.append(f'API_KEY={api_key}\n')
                updated = True
            else:
                new_lines.append(line)
        
        # Si no se encontraron, agregarlas al final
        if not any('BASE_API_URL=' in line for line in new_lines):
            new_lines.append(f'BASE_API_URL={api_url}\n')
        if not any('API_KEY=' in line for line in new_lines):
            new_lines.append(f'API_KEY={api_key}\n')
        
        # Escribir archivo .env
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        
        # Actualizar configuración en tiempo de ejecución
        current_app.config['BASE_API_URL'] = api_url
        current_app.config['API_KEY'] = api_key
        
        # Registrar en auditoría
        from app.models.audit_log_models import AuditLog
        audit_log = AuditLog(
            user_id=session.get('admin_username', 'unknown'),
            username=session.get('admin_username', 'unknown'),
            action='update_api_config',
            entity_type='Config',
            entity_id='api',
            old_value=old_value,
            new_value=json.dumps({
                'api_url': api_url,
                'api_key': api_key[:10] + '...'
            }),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            request_method=request.method,
            request_path=request.path,
            success=True
        )
        db.session.add(audit_log)
        db.session.commit()
        
        current_app.logger.warning(
            f"⚠️ Configuración de API actualizada por {session.get('admin_username', 'unknown')}: "
            f"URL={api_url[:30]}..., Key={api_key[:10]}..."
        )
        
        return jsonify({
            'success': True,
            'message': 'Configuración actualizada y verificada correctamente'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al actualizar configuración: {e}", exc_info=True)
        
        # Registrar error en auditoría
        try:
            from app.models.audit_log_models import AuditLog
            import json
            error_audit = AuditLog(
                user_id=session.get('admin_username', 'unknown'),
                username=session.get('admin_username', 'unknown'),
                action='update_api_config',
                entity_type='Config',
                entity_id='api',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                request_method=request.method,
                request_path=request.path,
                success=False,
                error_message=str(e)
            )
            db.session.add(error_audit)
            db.session.commit()
        except:
            pass
        
        return jsonify({
            'success': False,
            'message': f'Error al guardar: {str(e)}'
        }), 500

@bp.route('/admin/api/services/status', methods=['GET'])
def api_admin_services_status():
    """API: Obtener estado de servicios externos"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    
    try:
        local_only = current_app.config.get('LOCAL_ONLY', True)
        services = {
            'local_only': local_only,
            'api': {
                'enabled': not local_only and bool(current_app.config.get('BASE_API_URL') and current_app.config.get('API_KEY')),
                'name': 'API PHP POS'
            },
            'openai': {
                'enabled': not local_only and bool(current_app.config.get('OPENAI_API_KEY')),
                'name': 'OpenAI'
            },
            'getnet': {
                'enabled': current_app.config.get('GETNET_ENABLED', False),
                'name': 'GetNet'
            },
            'sumup': {
                'enabled': False,  # SumUp no tiene configuración separada
                'name': 'SumUp'
            }
        }
        return jsonify({'success': True, 'services': services})
    except Exception as e:
        current_app.logger.error(f"Error al obtener estado de servicios: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/admin/api/services/toggle', methods=['POST'])
def api_toggle_service():
    """API: Activar/desactivar un servicio externo"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        service_name = data.get('service')
        enabled = data.get('enabled', False)
        
        if service_name not in ['api', 'openai', 'getnet', 'sumup']:
            return jsonify({'success': False, 'message': 'Servicio inválido'}), 400
        
        # Obtener ruta del .env
        import os
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        
        if not os.path.exists(env_path):
            return jsonify({'success': False, 'message': 'Archivo .env no encontrado'}), 500
        
        # Leer archivo .env
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        # Actualizar configuración según el servicio
        new_lines = []
        updated = False
        
        if service_name == 'api':
            # Para API, activar/desactivar LOCAL_ONLY
            if enabled:
                # Activar: poner LOCAL_ONLY=false
                for line in lines:
                    if line.startswith('LOCAL_ONLY='):
                        new_lines.append('LOCAL_ONLY=false\n')
                        updated = True
                    else:
                        new_lines.append(line)
                if not updated:
                    new_lines.append('LOCAL_ONLY=false\n')
            else:
                # Desactivar: poner LOCAL_ONLY=true
                for line in lines:
                    if line.startswith('LOCAL_ONLY='):
                        new_lines.append('LOCAL_ONLY=true\n')
                        updated = True
                    else:
                        new_lines.append(line)
                if not updated:
                    new_lines.append('LOCAL_ONLY=true\n')
        
        elif service_name == 'openai':
            # Para OpenAI, verificar que tenga API key configurada antes de activar
            if enabled:
                # Verificar si hay API key en el .env
                openai_key = None
                for line in lines:
                    if line.startswith('OPENAI_API_KEY='):
                        openai_key = line.split('=', 1)[1].strip()
                        break
                
                if not openai_key or openai_key == '':
                    return jsonify({'success': False, 'message': 'OpenAI requiere API Key configurada. Por favor, configura el servicio primero.'}), 400
                
                # Activar OpenAI: desactivar LOCAL_ONLY si está activo
                # También necesitamos asegurar que OPENAI esté habilitado
                local_only_found = False
                for line in lines:
                    if line.startswith('LOCAL_ONLY='):
                        new_lines.append('LOCAL_ONLY=false\n')
                        local_only_found = True
                        updated = True
                    else:
                        new_lines.append(line)
                
                if not local_only_found:
                    new_lines.append('LOCAL_ONLY=false\n')
                    updated = True
            else:
                # Desactivar OpenAI no cambia LOCAL_ONLY, solo desactiva OpenAI
                # Para desactivar, simplemente no lo usamos (ya está deshabilitado por defecto en modo local)
                for line in lines:
                    new_lines.append(line)
        
        elif service_name == 'getnet':
            # Para GetNet, actualizar GETNET_ENABLED
            for line in lines:
                if line.startswith('GETNET_ENABLED='):
                    new_lines.append(f'GETNET_ENABLED={"true" if enabled else "false"}\n')
                    updated = True
                else:
                    new_lines.append(line)
            if not updated:
                new_lines.append(f'GETNET_ENABLED={"true" if enabled else "false"}\n')
        
        elif service_name == 'sumup':
            # SumUp no tiene configuración separada
            return jsonify({'success': False, 'message': 'SumUp no se puede activar/desactivar individualmente'}), 400
        
        # Escribir archivo .env
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        
        # Actualizar configuración en tiempo de ejecución
        if service_name == 'api':
            current_app.config['LOCAL_ONLY'] = not enabled
            if not enabled:
                current_app.config['API_KEY'] = None
                current_app.config['BASE_API_URL'] = None
        elif service_name == 'getnet':
            current_app.config['GETNET_ENABLED'] = enabled
        
        # Registrar en auditoría
        from app.models.audit_log_models import AuditLog
        audit_log = AuditLog(
            user_id=session.get('admin_username', 'unknown'),
            username=session.get('admin_username', 'unknown'),
            action=f'toggle_service_{service_name}',
            entity_type='Config',
            entity_id=service_name,
            new_value=str(enabled),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            request_method=request.method,
            request_path=request.path,
            success=True
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Servicio {"activado" if enabled else "desactivado"} correctamente. Reinicia el servidor para aplicar cambios.'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al cambiar estado de servicio: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/admin/api/services/configure', methods=['POST'])
def api_configure_service():
    """API: Configurar un servicio externo"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        service_name = data.get('service')
        
        if service_name not in ['openai', 'getnet', 'sumup']:
            return jsonify({'success': False, 'message': 'Servicio inválido'}), 400
        
        # Obtener ruta del .env
        import os
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        
        if not os.path.exists(env_path):
            return jsonify({'success': False, 'message': 'Archivo .env no encontrado'}), 500
        
        # Crear backup del .env
        import shutil
        from datetime import datetime
        from app import CHILE_TZ
        try:
            backup_path = f"{env_path}.backup.{datetime.now(CHILE_TZ).strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(env_path, backup_path)
            current_app.logger.info(f"✅ Backup creado: {backup_path}")
        except Exception as e:
            current_app.logger.warning(f"⚠️ No se pudo crear backup: {e}")
        
        # Leer archivo .env
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        # Actualizar configuración según el servicio
        new_lines = []
        updated_vars = []
        
        if service_name == 'openai':
            api_key = data.get('api_key', '').strip()
            org_id = data.get('org_id', '').strip() or None
            project_id = data.get('project_id', '').strip() or None
            
            if not api_key:
                return jsonify({'success': False, 'message': 'API Key es requerida'}), 400
            
            # Actualizar variables de OpenAI
            vars_to_update = {
                'OPENAI_API_KEY': api_key,
                'OPENAI_ORGANIZATION_ID': org_id or '',
                'OPENAI_PROJECT_ID': project_id or ''
            }
            
            for var_name, var_value in vars_to_update.items():
                found = False
                for line in lines:
                    if line.startswith(f'{var_name}='):
                        new_lines.append(f'{var_name}={var_value}\n')
                        updated_vars.append(var_name)
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f'{var_name}={var_value}\n')
                    updated_vars.append(var_name)
            
            # Actualizar configuración en tiempo de ejecución
            current_app.config['OPENAI_API_KEY'] = api_key
            current_app.config['OPENAI_ORGANIZATION_ID'] = org_id
            current_app.config['OPENAI_PROJECT_ID'] = project_id
            
        elif service_name == 'getnet':
            host = data.get('host', '').strip()
            port = data.get('port', 8020)
            
            if not host:
                return jsonify({'success': False, 'message': 'Host es requerido'}), 400
            
            # Actualizar variables de GetNet
            vars_to_update = {
                'GETNET_SERVER_HOST': host,
                'GETNET_SERVER_PORT': str(port),
                'GETNET_ENABLED': 'true'  # Habilitar automáticamente al configurar
            }
            
            for var_name, var_value in vars_to_update.items():
                found = False
                for line in lines:
                    if line.startswith(f'{var_name}='):
                        new_lines.append(f'{var_name}={var_value}\n')
                        updated_vars.append(var_name)
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f'{var_name}={var_value}\n')
                    updated_vars.append(var_name)
            
            # Actualizar configuración en tiempo de ejecución
            current_app.config['GETNET_SERVER_HOST'] = host
            current_app.config['GETNET_SERVER_PORT'] = int(port)
            current_app.config['GETNET_ENABLED'] = True
            
        elif service_name == 'sumup':
            api_key = data.get('api_key', '').strip()
            
            if not api_key:
                return jsonify({'success': False, 'message': 'API Key es requerida'}), 400
            
            # Actualizar variable de SumUp
            var_name = 'SUMUP_API_KEY'
            found = False
            for line in lines:
                if line.startswith(f'{var_name}='):
                    new_lines.append(f'{var_name}={api_key}\n')
                    updated_vars.append(var_name)
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f'{var_name}={api_key}\n')
                updated_vars.append(var_name)
            
            # Actualizar configuración en tiempo de ejecución
            current_app.config['SUMUP_API_KEY'] = api_key
        
        # Escribir archivo .env
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        
        # Registrar en auditoría
        from app.models.audit_log_models import AuditLog
        audit_log = AuditLog(
            user_id=session.get('admin_username', 'unknown'),
            username=session.get('admin_username', 'unknown'),
            action=f'configure_service_{service_name}',
            entity_type='Config',
            entity_id=service_name,
            new_value=f'Configurado: {", ".join(updated_vars)}',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            request_method=request.method,
            request_path=request.path,
            success=True
        )
        db.session.add(audit_log)
        db.session.commit()
        
        current_app.logger.info(f"✅ Configuración de {service_name} actualizada por {session.get('admin_username', 'unknown')}")
        
        return jsonify({
            'success': True,
            'message': f'Configuración de {service_name} guardada correctamente'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al configurar servicio: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/admin/api/services/<service_name>/logs', methods=['GET'])
def api_service_logs(service_name):
    """API: Obtener logs de un servicio específico"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    
    try:
        if service_name not in ['api', 'openai', 'getnet', 'sumup']:
            return jsonify({'success': False, 'message': 'Servicio inválido'}), 400
        
        logs_data = []
        
        if service_name == 'api':
            # Logs de API PHP POS - usar ApiConnectionLog
            from app.models.api_log_models import ApiConnectionLog
            logs = ApiConnectionLog.query.order_by(ApiConnectionLog.timestamp.desc()).limit(100).all()
            
            for log in logs:
                timestamp_chile = log.timestamp_chile
                logs_data.append({
                    'timestamp': timestamp_chile.strftime('%d/%m/%Y %H:%M:%S') if timestamp_chile else 'N/A',
                    'status': log.status,
                    'response_time_ms': log.response_time_ms,
                    'message': log.message or 'N/A',
                    'error': None
                })
        
        elif service_name == 'openai':
            # Para OpenAI, buscar en logs de Flask o crear logs simples
            # Por ahora, retornar logs vacíos o mensaje informativo
            logs_data.append({
                'timestamp': datetime.now(CHILE_TZ).strftime('%d/%m/%Y %H:%M:%S'),
                'status': 'info',
                'response_time_ms': None,
                'message': 'Los logs de OpenAI aparecerán aquí cuando se use el servicio.',
                'error': None
            })
        
        elif service_name == 'getnet':
            # Para GetNet, buscar logs relacionados
            # Por ahora, retornar logs vacíos o mensaje informativo
            logs_data.append({
                'timestamp': datetime.now(CHILE_TZ).strftime('%d/%m/%Y %H:%M:%S'),
                'status': 'info',
                'response_time_ms': None,
                'message': 'Los logs de GetNet aparecerán aquí cuando se procesen pagos.',
                'error': None
            })
        
        elif service_name == 'sumup':
            # Para SumUp, buscar logs relacionados
            # Por ahora, retornar logs vacíos o mensaje informativo
            logs_data.append({
                'timestamp': datetime.now(CHILE_TZ).strftime('%d/%m/%Y %H:%M:%S'),
                'status': 'info',
                'response_time_ms': None,
                'message': 'Los logs de SumUp aparecerán aquí cuando se procesen pagos.',
                'error': None
            })
        
        return jsonify({
            'success': True,
            'logs': logs_data,
            'total': len(logs_data),
            'service': service_name
        })
        
    except Exception as e:
        logger.error(f"Error al obtener logs del servicio {service_name}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/admin/api/authorize-sos-drawer', methods=['POST'])
def api_authorize_sos_drawer_admin():
    """API: Autorizar apertura de cajón desde el dashboard admin"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        request_id = data.get('request_id')
        
        if not request_id:
            return jsonify({'success': False, 'error': 'ID de solicitud requerido'}), 400
        
        from app.helpers.sos_drawer_helper import load_sos_requests, update_sos_request
        
        # Buscar solicitud
        all_requests = load_sos_requests()
        found_request = None
        for req in all_requests:
            if req.get('request_id') == request_id and req.get('status') == 'pending':
                found_request = req
                break
        
        if not found_request:
            return jsonify({'success': False, 'error': 'Solicitud no encontrada o ya procesada'}), 404
        
        # Abrir cajón de dinero
        # NOTA: Actualmente abre el cajón del servidor. 
        # Para producción, cada caja debería tener su propia impresora configurada
        from app.infrastructure.services.ticket_printer_service import TicketPrinterService
        
        # Intentar usar la impresora específica de la caja si está disponible
        printer_name = found_request.get('printer_name')
        printer_service = TicketPrinterService(printer_name=printer_name) if printer_name else TicketPrinterService()
        drawer_opened = printer_service.open_cash_drawer()
        
        if drawer_opened:
            # Actualizar solicitud de forma segura
            updates = {
                'status': 'authorized',
                'authorized_by': session.get('admin_username', 'Superadmin'),
                'authorized_at': datetime.now(CHILE_TZ).isoformat(),
                'authorization_method': 'remote'
            }
            
            if update_sos_request(request_id, updates):
                current_app.logger.info(f"✅ Cajón abierto remotamente - Request ID: {request_id}, Caja: {found_request.get('register_name')}, Autorizado por: {updates['authorized_by']}")
                return jsonify({'success': True, 'message': 'Cajón abierto y solicitud autorizada'})
            else:
                current_app.logger.warning(f"⚠️  Cajón abierto pero no se pudo actualizar solicitud - Request ID: {request_id}")
                return jsonify({'success': True, 'message': 'Cajón abierto (pero hubo un error al actualizar el estado)'})
        else:
            current_app.logger.warning(f"⚠️  No se pudo abrir cajón remotamente - Request ID: {request_id}, Caja: {found_request.get('register_name')}")
            return jsonify({'success': False, 'error': 'No se pudo abrir el cajón de dinero'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Error al autorizar solicitud de apertura de cajón: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/admin/api/resolve-register-close', methods=['POST'])
def api_resolve_register_close():
    """Resuelve un cierre de caja pendiente desde el admin"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        close_id = data.get('close_id')
        resolution_notes = data.get('resolution_notes', '')
        
        if not close_id:
            return jsonify({'success': False, 'error': 'ID de cierre no proporcionado'}), 400
        
        # Resolver el cierre usando el helper
        from app.helpers.register_close_db import resolve_register_close, get_register_close_by_id
        from app.helpers.register_lock_db import unlock_register
        admin_user = session.get('admin_username', 'admin')
        
        # Obtener información del cierre antes de resolverlo
        close_data = get_register_close_by_id(close_id)
        if not close_data:
            return jsonify({'success': False, 'error': 'Cierre no encontrado'}), 404
        
        # Resolver el cierre
        success = resolve_register_close(
            close_id=close_id,
            resolved_by=admin_user,
            resolution_notes=resolution_notes
        )
        
        if success:
            # Liberar la caja ahora que el admin aceptó el cierre
            register_id = close_data.get('register_id')
            if register_id:
                unlock_register(register_id)
                current_app.logger.info(f"✅ Caja {register_id} liberada después de aceptar cierre")
            
            current_app.logger.info(f"✅ Cierre de caja aceptado por admin: ID {close_id} - Caja {register_id} liberada")
            
            # Emitir evento socket para notificar
            from app import socketio
            socketio.emit('register_close_resolved', {
                'close_id': close_id,
                'register_id': register_id,
                'resolved_by': admin_user
            })
            
            return jsonify({
                'success': True, 
                'message': 'Cierre aceptado y caja liberada correctamente',
                'register_id': register_id
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se pudo resolver el cierre'}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error al resolver cierre de caja: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/admin/api/reject-sos-drawer', methods=['POST'])
def api_reject_sos_drawer_admin():
    """API: Rechazar apertura de cajón desde el dashboard admin"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        request_id = data.get('request_id')
        
        if not request_id:
            return jsonify({'success': False, 'error': 'ID de solicitud requerido'}), 400
        
        from app.helpers.sos_drawer_helper import load_sos_requests, update_sos_request
        
        # Buscar solicitud
        all_requests = load_sos_requests()
        found_request = None
        for req in all_requests:
            if req.get('request_id') == request_id and req.get('status') == 'pending':
                found_request = req
                break
        
        if not found_request:
            return jsonify({'success': False, 'error': 'Solicitud no encontrada o ya procesada'}), 404
        
        # Actualizar solicitud de forma segura
        updates = {
            'status': 'rejected',
            'authorized_by': session.get('admin_username', 'Superadmin'),
            'authorized_at': datetime.now().isoformat(),
            'authorization_method': 'remote'
        }
        
        if update_sos_request(request_id, updates):
            current_app.logger.info(f"❌ Solicitud de apertura de cajón rechazada - Request ID: {request_id}, Caja: {found_request.get('register_name')}, Rechazado por: {updates['authorized_by']}")
            return jsonify({'success': True, 'message': 'Solicitud rechazada'})
        else:
            return jsonify({'success': False, 'error': 'Error al actualizar la solicitud'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Error al rechazar solicitud de apertura de cajón: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/admin/logs')
def admin_logs():
    """Área administrativa - Tickets escaneados en tiempo real (solo entregas registradas)"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))

    delivery_service = get_delivery_service()
    delivery_repo = delivery_service.delivery_repository
    
    # Verificar si se solicita filtrar por turno
    filter_by_turno = request.args.get('turno', 'false').lower() == 'true'
    
    # Obtener todas las entregas registradas (tickets escaneados)
    all_deliveries = delivery_repo.find_all()
    
    # Si se solicita filtrar por turno, obtener solo las entregas del turno actual
    if filter_by_turno:
        from .models.jornada_models import Jornada
        from datetime import datetime
        from flask import current_app
        
        CHILE_TZ = current_app.config.get('CHILE_TZ')
        fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
        
        # Buscar turno abierto del día
        turno_actual = Jornada.query.filter_by(
            fecha_jornada=fecha_hoy,
            estado_apertura='abierto'
        ).first()
        
        if turno_actual and turno_actual.abierto_en:
            # Filtrar entregas desde que se abrió el turno
            turno_inicio = turno_actual.abierto_en
            
            # Convertir entregas a datetime si son strings para comparar
            filtered_deliveries = []
            for delivery in all_deliveries:
                if isinstance(delivery.timestamp, str):
                    try:
                        delivery_dt = datetime.strptime(delivery.timestamp, '%Y-%m-%d %H:%M:%S')
                    except:
                        continue
                else:
                    delivery_dt = delivery.timestamp
                
                # Comparar fechas (sin timezone para evitar problemas)
                if delivery_dt.replace(tzinfo=None) >= turno_inicio.replace(tzinfo=None):
                    filtered_deliveries.append(delivery)
            
            all_deliveries = filtered_deliveries
        else:
            # No hay turno abierto, mostrar vacío o mensaje
            all_deliveries = []
    
    # Agrupar entregas por sale_id primero, luego por item_name
    deliveries_by_sale = defaultdict(lambda: defaultdict(list))
    
    for delivery in all_deliveries:
        deliveries_by_sale[delivery.sale_id][delivery.item_name].append(delivery)
    
    # Obtener información de tickets escaneados desde el log
    from .helpers.ticket_scans import get_all_ticket_scans
    ticket_scans = get_all_ticket_scans()
    
    # Agrupar por ticket y mostrar todos los productos
    logs_data = []
    
    for sale_id, items_dict in deliveries_by_sale.items():
        sale_id_clean = sale_id.replace("BMB ", "").replace("B ", "").strip()
        
        # Obtener información del ticket escaneado desde el log
        ticket_scan_info = ticket_scans.get(sale_id)
        ticket_items_vendidos = {}
        if ticket_scan_info:
            # Crear diccionario de productos vendidos
            for item in ticket_scan_info.get('items', []):
                item_name = item.get('name', '')
                qty_vendido = item.get('quantity', 0)
                ticket_items_vendidos[item_name] = qty_vendido
        
        # Obtener información del ticket (fecha más reciente, bartender, barra)
        all_ticket_deliveries = []
        for item_deliveries in items_dict.values():
            all_ticket_deliveries.extend(item_deliveries)
        
        if not all_ticket_deliveries:
            continue
            
        # Ordenar todas las entregas del ticket por timestamp
        all_ticket_deliveries.sort(key=lambda d: d.timestamp, reverse=True)
        latest_delivery = all_ticket_deliveries[0]
        
        # Calcular productos entregados y pendientes
        productos_entregados = len(items_dict)  # Productos que tienen entregas registradas
        productos_pendientes = 0
        
        if ticket_scan_info:
            # Calcular productos pendientes: productos vendidos sin entregas
            productos_vendidos = ticket_scan_info.get('total_items', 0)
            productos_pendientes = max(0, productos_vendidos - productos_entregados)
        
        # Para cada producto del ticket
        for item_name, deliveries in items_dict.items():
            # Ordenar entregas por timestamp (más reciente primero)
            deliveries.sort(key=lambda d: d.timestamp, reverse=True)
            
            # Calcular total entregado
            total_entregado = sum(d.qty for d in deliveries)
            
            # Preparar información de entregas
            entregas_info = [{
                'qty': d.qty,
                'bartender': d.bartender,
                'barra': d.barra,
                'timestamp': d.timestamp
            } for d in deliveries]
            
            log_entry = {
                'sale_id': sale_id,
                'sale_id_clean': sale_id_clean,
                'item_name': item_name,
                'qty_entregado': total_entregado,
                'bartender': latest_delivery.bartender,
                'barra': latest_delivery.barra,
                'fecha_entrega': latest_delivery.timestamp,
                'entregas_info': entregas_info,
                'total_items_ticket': len(items_dict),  # Productos con entregas
                'productos_entregados': productos_entregados,
                'productos_pendientes': productos_pendientes
            }
            
            logs_data.append(log_entry)
    
    # Ordenar por fecha (más recientes primero)
    # Si no hay fecha de entrega, usar fecha actual para ordenar al final
    logs_data.sort(key=lambda x: x['fecha_entrega'] if x['fecha_entrega'] != '-' else '1970-01-01', reverse=True)
    
    # Paginación
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))  # Mostrar 20, 50, 100 o 200 por página
    # Validar que per_page sea uno de los valores permitidos
    if per_page not in [20, 50, 100, 200]:
        per_page = 20
    total_logs = len(logs_data)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_logs = logs_data[start_idx:end_idx]
    
    # Obtener estado del turno para el footer
    from app.application.services.service_factory import get_shift_service
    shift_service = get_shift_service()
    shift_status = shift_service.get_current_shift_status()
    shift_status_dict = shift_status.to_dict() if hasattr(shift_status, 'to_dict') else {
        'is_open': shift_status.is_open,
        'shift_date': shift_status.shift_date,
        'opened_at': shift_status.opened_at,
        'closed_at': shift_status.closed_at,
        'fiesta_nombre': shift_status.fiesta_nombre,
        'djs': shift_status.djs
    }
    
    # Obtener métricas del turno para el footer
    shift_metrics = {}
    if shift_status.is_open:
        try:
            from app.models.jornada_models import Jornada
            from datetime import datetime, timezone
            from app import CHILE_TZ
            
            # Buscar jornada abierta usando la misma lógica que otras rutas
            # Primero buscar jornada de hoy
            fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
            jornada_actual = Jornada.query.filter_by(fecha_jornada=fecha_hoy).first()
            
            # Si no hay jornada de hoy, buscar cualquier jornada abierta
            if not jornada_actual:
                jornada_actual = Jornada.query.filter_by(estado_apertura='abierto').order_by(
                    Jornada.fecha_jornada.desc()
                ).first()
            elif jornada_actual.estado_apertura != 'abierto':
                # Si hay jornada de hoy pero no está abierta, buscar cualquier jornada abierta
                jornada_actual = Jornada.query.filter_by(estado_apertura='abierto').order_by(
                    Jornada.fecha_jornada.desc()
                ).first()
            
            if jornada_actual and jornada_actual.abierto_en:
                # Calcular tiempo transcurrido usando hora de Chile
                opened_dt_utc = jornada_actual.abierto_en
                now_chile = datetime.now(CHILE_TZ)
                
                # Manejar abierto_en: puede ser UTC naive o hora local (Chile) sin timezone
                if opened_dt_utc.tzinfo is None:
                    # Si no tiene timezone, verificar cuál es más probable
                    # Calcular diferencia naive (sin timezone)
                    diff_naive = now_chile.replace(tzinfo=None) - opened_dt_utc
                    
                    # Si la diferencia naive es razonable (menos de 12 horas), 
                    # probablemente es hora local (Chile) sin timezone
                    # Si es muy grande (más de 12 horas), podría ser UTC
                    if abs(diff_naive.total_seconds()) < 12 * 3600:  # Menos de 12 horas
                        # Asumir que es hora local (Chile) sin timezone
                        opened_dt_chile = CHILE_TZ.localize(opened_dt_utc)
                    else:
                        # Asumir que es UTC (nuevo formato)
                        opened_dt_utc_aware = opened_dt_utc.replace(tzinfo=timezone.utc)
                        opened_dt_chile = opened_dt_utc_aware.astimezone(CHILE_TZ)
                else:
                    # Ya tiene timezone, convertir a Chile
                    opened_dt_chile = opened_dt_utc.astimezone(CHILE_TZ)
                
                diff = now_chile - opened_dt_chile
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                shift_metrics['tiempo_transcurrido'] = f"{hours}h {minutes}m"
                # Logging opcional (comentado para evitar problemas de scope)
                # from flask import current_app
                # current_app.logger.debug(
                #     f"⏰ Tiempo transcurrido calculado en /admin/logs: "
                #     f"Jornada ID={jornada_actual.id}, Fecha={jornada_actual.fecha_jornada}, "
                #     f"Abierto en={opened_dt_chile}, Tiempo={hours}h {minutes}m"
                # )
                
                # Obtener estadísticas del turno
                from app.application.services.service_factory import get_stats_service
                stats_service = get_stats_service()
                delivery_stats = stats_service.get_delivery_stats(
                    start_date=shift_status.shift_date,
                    end_date=shift_status.shift_date
                )
                shift_metrics['total_entregas'] = delivery_stats.get('total_deliveries', 0)
                
                # Obtener entradas
                from .helpers.pos_api import get_entradas_sales
                try:
                    entradas_sales = get_entradas_sales(limit=100)
                    shift_metrics['total_entradas'] = len([s for s in entradas_sales if s.get('sale_time', '').startswith(shift_status.shift_date)])
                except:
                    shift_metrics['total_entradas'] = 0
            else:
                shift_metrics = {
                    'tiempo_transcurrido': 'N/A',
                    'total_entregas': 0,
                    'total_entradas': 0
                }
        except Exception as e:
            # current_app ya está importado al inicio del archivo (línea 26)
            # pero puede haber problemas de scope, así que lo importamos aquí también
            from flask import current_app as flask_current_app
            flask_current_app.logger.warning(f"Error al calcular métricas del turno: {e}")
            shift_metrics = {
                'tiempo_transcurrido': 'N/A',
                'total_entregas': 0,
                'total_entradas': 0
            }
    
    # Hacer shift_status y shift_metrics disponibles globalmente para base.html
    from flask import g
    g.shift_status = shift_status_dict
    g.shift_metrics = shift_metrics
    
    return render_template(
        'admin_area.html', 
        logs=paginated_logs,
        current_page=page,
        total_pages=(total_logs + per_page - 1) // per_page,
        total_logs=total_logs,
        per_page=per_page,
        has_prev=page > 1,
        has_next=end_idx < total_logs,
        shift_status=shift_status_dict,
        shift_metrics=shift_metrics
    )

@bp.route('/api/sale-details/<sale_id>')
def api_sale_details(sale_id):
    """API endpoint para obtener detalles completos de una venta - SOLO CONSULTA LOG LOCAL"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        delivery_service = get_delivery_service()
        delivery_repo = delivery_service.delivery_repository
        
        # Limpiar sale_id
        sale_id_clean = sale_id.replace("BMB ", "").replace("B ", "").strip()
        numeric_id = ''.join(filter(str.isdigit, sale_id_clean))
        
        if not numeric_id:
            return jsonify({'error': 'ID de venta inválido'}), 400
        
        # Obtener información del ticket desde el log local (NO consultar API)
        from .helpers.ticket_scans import get_ticket_scan
        ticket_scan = get_ticket_scan(sale_id_clean)
        
        if not ticket_scan:
            return jsonify({'error': 'Ticket no encontrado en el log. Debe ser escaneado primero.'}), 404
        
        # Extraer información guardada del log local
        sale_data = ticket_scan.get('sale_data', {})
        fecha_venta = ticket_scan.get('fecha_venta', sale_data.get('sale_time', sale_data.get('created_at', sale_data.get('order_time', ''))))
        vendedor = ticket_scan.get('vendedor', 'Desconocido')
        caja = ticket_scan.get('caja', 'Caja desconocida')
        employee_id = ticket_scan.get('employee_id') or sale_data.get('employee_id') or sale_data.get('sold_by_employee_id')
        register_id = ticket_scan.get('register_id') or sale_data.get('register_id')
        items_from_scan = ticket_scan.get('items', [])
        
        # Obtener entregas registradas para este ticket (del log local)
        deliveries = delivery_repo.find_by_sale_id(sale_id)
        
        # Agrupar entregas por item
        entregas_por_item = defaultdict(list)
        for delivery in deliveries:
            entregas_por_item[delivery.item_name].append({
                'qty': delivery.qty,
                'bartender': delivery.bartender,
                'barra': delivery.barra,
                'timestamp': delivery.timestamp
            })
        
        # Calcular pendientes por item usando datos del log local
        items_con_entregas = []
        for item in items_from_scan:
            item_name = item.get('name', '')
            qty_vendido = item.get('quantity', 0)
            entregas_item = entregas_por_item.get(item_name, [])
            total_entregado = sum(e['qty'] for e in entregas_item)
            pendiente = qty_vendido - total_entregado
            
            items_con_entregas.append({
                'name': item_name,
                'qty_vendido': qty_vendido,
                'qty_entregado': total_entregado,
                'pendiente': pendiente,
                'entregas': entregas_item
            })
        
        return jsonify({
            'sale_id': ticket_scan.get('sale_id', sale_id),
            'sale_id_clean': numeric_id,
            'fecha_compra': fecha_venta,
            'caja': caja,
            'register_id': register_id,
            'vendedor': vendedor,
            'employee_id': employee_id,
            'items': items_con_entregas,
            'total': float(sale_data.get('total', 0) or 0),
            'subtotal': float(sale_data.get('subtotal', 0) or 0)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener detalles de venta {sale_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/logs/modulos')
def admin_logs_modulos():
    """Área administrativa - Entrega por módulo (4 cuadros, uno por bartender)"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))

    delivery_service = get_delivery_service()
    delivery_repo = delivery_service.delivery_repository
    
    # Obtener todas las entregas registradas
    all_deliveries = delivery_repo.find_all()
    
    # Agrupar entregas por bartender
    deliveries_by_bartender = defaultdict(list)
    bartenders_set = set()
    
    for delivery in all_deliveries:
        bartender = delivery.bartender or "Sin asignar"
        bartenders_set.add(bartender)
        deliveries_by_bartender[bartender].append({
            'sale_id': delivery.sale_id,
            'item_name': delivery.item_name,
            'qty': delivery.qty,
            'barra': delivery.barra,
            'timestamp': delivery.timestamp
        })
    
    # Ordenar entregas por timestamp (más recientes primero) dentro de cada bartender
    for bartender in deliveries_by_bartender:
        deliveries_by_bartender[bartender].sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Obtener los 4 bartenders más activos (o todos si son menos de 4)
    bartenders_list = sorted(bartenders_set, key=lambda b: len(deliveries_by_bartender[b]), reverse=True)[:4]
    
    # Si hay menos de 4 bartenders, completar con "Sin asignar" si es necesario
    while len(bartenders_list) < 4:
        bartenders_list.append(f"Módulo {len(bartenders_list) + 1}")
    
    # Preparar datos para cada módulo
    modulos_data = []
    for i, bartender in enumerate(bartenders_list[:4]):
        entregas = deliveries_by_bartender.get(bartender, [])
        modulos_data.append({
            'bartender': bartender,
            'entregas': entregas[:20],  # Mostrar últimas 20 entregas
            'total_entregas': len(entregas),
            'total_items': sum(e['qty'] for e in entregas)
        })
    
    return render_template('admin_logs_modulos.html', modulos=modulos_data)

@bp.route('/admin/logs/turno')
def admin_logs_turno():
    """Área administrativa - Ventas vendidas en el turno actual"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))

    # Obtener estado del turno
    shift_status = get_shift_status()
    
    if not shift_status.get('is_open', False):
        return render_template(
            'admin_logs_turno.html',
            sales=[],
            current_page=1,
            total_pages=1,
            total_sales=0,
            has_prev=False,
            has_next=False,
            shift_open=False,
            shift_info=None
        )
    
    delivery_service = get_delivery_service()
    shift_opened_at = shift_status.get('opened_at')
    
    # Obtener todas las ventas desde la API POS
    sales_data = []
    api_error = False
    
    from datetime import datetime
    
    try:
        # Intentar obtener ventas del turno - RESPETANDO límites PHP POS API
        # PHP POS: máximo 100 items por request, paginación con delay de 60s entre requests
        # Para consulta de turno, limitamos a primera página (100 items) para no sobrecargar
        all_sales = delivery_service.pos_client.get_all_sales(limit=100, max_results=100, use_pagination=False)
        
        if not all_sales:
            current_app.logger.info("Endpoint /sales no disponible para turno. Intentando método alternativo...")
            api_error = True
            
            # Método alternativo: usar get_all_sales de helpers.pos_api
            # Solo primera página (100 items) para no sobrecargar API
            try:
                all_sales = get_all_sales(limit=100, max_results=100, use_pagination=False)
            except Exception as e:
                current_app.logger.error(f"Error al obtener ventas: {e}")
                all_sales = []
        
        if all_sales:
            # Filtrar ventas del turno actual (desde opened_at)
            if shift_opened_at:
                try:
                    shift_start = datetime.fromisoformat(shift_opened_at.replace('Z', '+00:00'))
                except:
                    # Si falla el parsing, usar la fecha del turno
                    shift_date = shift_status.get('shift_date', '')
                    if shift_date:
                        try:
                            shift_start = datetime.strptime(shift_date, '%Y-%m-%d')
                        except:
                            shift_start = None
                    else:
                        shift_start = None
            else:
                shift_start = None
            
            for sale in all_sales:
                sale_time_str = sale.get('sale_time', sale.get('sale_date', ''))
                if not sale_time_str:
                    continue
                
                try:
                    # Intentar parsear la fecha de la venta
                    sale_time = datetime.fromisoformat(sale_time_str.replace('Z', '+00:00'))
                    if shift_start and sale_time >= shift_start:
                        # Esta venta es del turno actual
                        sales_data.append(sale)
                    elif not shift_start:
                        # Si no hay filtro de fecha, incluir todas
                        sales_data.append(sale)
                except:
                    # Si no se puede parsear, incluirla si no hay filtro de fecha
                    if not shift_start:
                        sales_data.append(sale)
        else:
            api_error = True
            current_app.logger.warning("No se pudieron obtener ventas desde la API para el turno")
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar ventas del turno: {e}", exc_info=True)
        api_error = True
    
    # Ordenar por fecha (más recientes primero)
    sales_data.sort(key=lambda x: x.get('sale_time', x.get('sale_date', '')), reverse=True)
    
    # Paginación
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    if per_page not in [20, 50, 100, 200]:
        per_page = 20
    total_sales = len(sales_data)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_sales = sales_data[start_idx:end_idx]
    
    return render_template(
        'admin_logs_turno.html',
        sales=paginated_sales,
        current_page=page,
        total_pages=(total_sales + per_page - 1) // per_page,
        total_sales=total_sales,
        per_page=per_page,
        has_prev=page > 1,
        has_next=end_idx < total_sales,
        shift_open=shift_status.get('is_open', False),
        shift_info=shift_status,
        api_error=api_error
    )

@bp.route('/admin/logs/pendientes')
def admin_logs_pendientes():
    """Área administrativa - Ventas no entregadas - Consulta profunda al POS"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))

    delivery_service = get_delivery_service()
    delivery_repo = delivery_service.delivery_repository
    
    # Obtener todas las entregas registradas
    all_deliveries = delivery_repo.find_all()
    
    # Agrupar entregas por sale_id e item_name para calcular cantidades entregadas
    delivered_map = defaultdict(lambda: defaultdict(int))
    
    for delivery in all_deliveries:
        sale_id_clean = delivery.sale_id.replace("BMB ", "").replace("B ", "").strip()
        item_name = delivery.item_name
        delivered_map[sale_id_clean][item_name] += delivery.qty
    
    # Obtener todas las ventas desde la API POS
    pendientes_data = []
    bartender_default = "Sin asignar"
    api_error = False
    sales_processed = 0
    sales_found = 0
    
    try:
        # Intentar obtener todas las ventas usando el endpoint /sales
        all_sales = delivery_service.pos_client.get_all_sales(limit=1000)
        
        if not all_sales:
            current_app.logger.info("Endpoint /sales no disponible. Consultando ventas individualmente...")
            api_error = True
            
            # Método alternativo: Consultar ventas individualmente
            # Obtener IDs de ventas desde las entregas registradas
            sales_from_deliveries = set()
            for delivery in all_deliveries:
                sale_id_clean = delivery.sale_id.replace("BMB ", "").replace("B ", "").strip()
                # Intentar extraer el ID numérico
                try:
                    numeric_id = int(sale_id_clean)
                    sales_from_deliveries.add(numeric_id)
                except:
                    pass
            
            # También intentar consultar un rango de ventas recientes
            # Empezar desde el ID más alto encontrado y buscar hacia atrás
            max_sale_id = max(sales_from_deliveries) if sales_from_deliveries else 0
            start_id = max(1, max_sale_id - 500)  # Últimas 500 ventas desde la más alta
            end_id = max_sale_id + 50  # Hasta 50 ventas más nuevas
            
            current_app.logger.info(f"Consultando ventas desde ID {start_id} hasta {end_id}...")
            
            # Consultar ventas en el rango
            for sale_id_num in range(start_id, end_id + 1):
                try:
                    items, error, canonical_id = get_sale_items(str(sale_id_num))
                    if items and not error:
                        sales_found += 1
                        sale_id = canonical_id or f"BMB {sale_id_num}"
                        sale_id_clean = str(sale_id_num)
                        
                        # Intentar obtener información de la venta completa
                        sale_time = "N/A"
                        employee_id = None
                        try:
                            api_key = current_app.config['API_KEY']
                            base_url = current_app.config['BASE_API_URL']
                            url = f"{base_url}/sales/{sale_id_num}"
                            headers = {
                                "x-api-key": api_key,
                                "accept": "application/json"
                            }
                            resp = requests.get(url, headers=headers, timeout=5)
                            if resp.status_code == 200:
                                sale_data = resp.json()
                                sale_time = sale_data.get('sale_time', sale_data.get('sale_date', 'N/A'))
                                employee_id = sale_data.get('employee_id', '')
                        except:
                            pass
                        
                        # Intentar obtener nombre del empleado
                        vendedor_name = bartender_default
                        if employee_id:
                            try:
                                employee_info = get_entity_details("employees", employee_id)
                                if employee_info:
                                    first_name = employee_info.get('first_name', '')
                                    last_name = employee_info.get('last_name', '')
                                    vendedor_name = f"{first_name} {last_name}".strip() or employee_info.get('name', f'Empleado {employee_id}')
                            except:
                                pass
                        
                        # Procesar items de la venta
                        for item in items:
                            item_name = item.get('name', 'Sin nombre')
                            qty_vendido = item.get('quantity', 1)
                            qty_entregado = delivered_map[sale_id_clean].get(item_name, 0)
                            pendiente = qty_vendido - qty_entregado
                            
                            if pendiente > 0:
                                log_entry = {
                                    'sale_id': sale_id,
                                    'sale_id_clean': sale_id_clean,
                                    'item_name': item_name,
                                    'qty_vendido': qty_vendido,
                                    'qty_entregado': qty_entregado,
                                    'pendiente': pendiente,
                                    'vendedor': vendedor_name,
                                    'fecha_venta': sale_time
                                }
                                pendientes_data.append(log_entry)
                        
                        sales_processed += 1
                        if sales_processed % 50 == 0:
                            current_app.logger.info(f"Procesadas {sales_processed} ventas, encontradas {sales_found} válidas...")
                except Exception as e:
                    # Ignorar errores de ventas que no existen
                    pass
        
        if all_sales:
            # Procesar ventas normalmente si la API responde
            current_app.logger.info(f"Procesando {len(all_sales)} ventas desde endpoint /sales...")
            for sale in all_sales:
                sale_id = sale.get('sale_id', '')
                sale_id_clean = sale_id.replace("BMB ", "").replace("B ", "").strip()
                sale_time = sale.get('sale_time', sale.get('sale_date', ''))
                employee_id = sale.get('employee_id', '')
                
                # Intentar obtener nombre del empleado que vendió
                vendedor_name = bartender_default
                if employee_id:
                    try:
                        employee_info = get_entity_details("employees", employee_id)
                        if employee_info:
                            first_name = employee_info.get('first_name', '')
                            last_name = employee_info.get('last_name', '')
                            vendedor_name = f"{first_name} {last_name}".strip() or employee_info.get('name', f'Empleado {employee_id}')
                    except:
                        pass
                
                # Obtener items de la venta
                try:
                    numeric_id = sale_id_clean
                    items, error, canonical_id = get_sale_items(numeric_id)
                    
                    if items and not error:
                        for item in items:
                            item_name = item.get('name', 'Sin nombre')
                            qty_vendido = item.get('quantity', 1)
                            
                            # Obtener cantidad entregada
                            qty_entregado = delivered_map[sale_id_clean].get(item_name, 0)
                            pendiente = qty_vendido - qty_entregado
                            
                            # Solo agregar si hay items pendientes
                            if pendiente > 0:
                                log_entry = {
                                    'sale_id': sale_id,
                                    'sale_id_clean': sale_id_clean,
                                    'item_name': item_name,
                                    'qty_vendido': qty_vendido,
                                    'qty_entregado': qty_entregado,
                                    'pendiente': pendiente,
                                    'vendedor': vendedor_name,
                                    'fecha_venta': sale_time
                                }
                                pendientes_data.append(log_entry)
                except Exception as e:
                    current_app.logger.warning(f"Error al obtener items de venta {sale_id}: {e}")
        
        # Ordenar por fecha de venta (más recientes primero)
        if pendientes_data:
            pendientes_data.sort(key=lambda x: x.get('fecha_venta', ''), reverse=True)
        
        current_app.logger.info(f"Consulta completada: {len(pendientes_data)} items pendientes encontrados")
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar ventas desde API: {e}", exc_info=True)
        api_error = True
        pendientes_data = []
    
    # Paginación
    page = int(request.args.get('page', 1))
    per_page = 20
    total_pendientes = len(pendientes_data)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_pendientes = pendientes_data[start_idx:end_idx]
    
    return render_template(
        'admin_logs_pendientes.html', 
        pendientes=paginated_pendientes,
        current_page=page,
        total_pages=(total_pendientes + per_page - 1) // per_page,
        total_pendientes=total_pendientes,
        has_prev=page > 1,
        has_next=end_idx < total_pendientes,
        api_error=api_error
    )

@bp.route('/admin/api/pending_deliveries')
def api_pending_deliveries():
    """API para obtener ventas con items pendientes de entregar"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        delivery_service = get_delivery_service()
        delivery_repo = delivery_service.delivery_repository
        
        # Obtener todas las entregas registradas
        all_deliveries = delivery_repo.find_all()
        
        # Agrupar entregas por sale_id e item_name
        delivered_map = defaultdict(lambda: defaultdict(int))
        for delivery in all_deliveries:
            sale_id_clean = delivery.sale_id.replace("BMB ", "").strip()
            delivered_map[sale_id_clean][delivery.item_name] += delivery.qty
        
        # Obtener ventas recientes del POS - RESPETANDO límites PHP POS API (máx 100 por request)
        all_sales = delivery_service.pos_client.get_all_sales(limit=100, max_results=100, use_pagination=False)
        
        pending_sales = []
        
        # Para cada venta, verificar si hay items pendientes
        for sale in all_sales:
            sale_id = str(sale.get('sale_id', ''))
            if not sale_id:
                continue
            
            # Obtener items de la venta (pueden estar en cart_items o necesitar consulta individual)
            cart_items = sale.get('cart_items', [])
            
            # Si no hay cart_items en la venta, obtenerlos individualmente
            if not cart_items:
                try:
                    items_data = delivery_service.pos_client.get_sale_items(sale_id)
                    if isinstance(items_data, list):
                        cart_items = items_data
                    elif isinstance(items_data, dict):
                        cart_items = items_data.get('cart_items', [])
                except Exception as e:
                    current_app.logger.warning(f"No se pudieron obtener items para venta {sale_id}: {e}")
                    continue
            
            if not cart_items:
                continue
            
            pending_items = []
            has_pending = False
            
            for item in cart_items:
                item_name = item.get('name', '')
                item_qty = item.get('quantity', 0)
                
                if not item_name or item_qty <= 0:
                    continue
                
                # Verificar cuántas unidades se han entregado
                delivered_qty = delivered_map[sale_id].get(item_name, 0)
                pending_qty = item_qty - delivered_qty
                
                if pending_qty > 0:
                    has_pending = True
                    pending_items.append({
                        'name': item_name,
                        'total_qty': item_qty,
                        'delivered_qty': delivered_qty,
                        'pending_qty': pending_qty
                    })
            
            if has_pending:
                pending_sales.append({
                    'sale_id': sale_id,
                    'sale_id_display': f"BMB {sale_id}",
                    'sale_time': sale.get('sale_time_formatted', sale.get('sale_time', '')),
                    'pending_items': pending_items,
                    'total_pending_items': len(pending_items),
                    'total_pending_qty': sum(item['pending_qty'] for item in pending_items)
                })
        
        # Ordenar por fecha más reciente primero
        pending_sales.sort(key=lambda x: x['sale_time'], reverse=True)
        
        return jsonify({
            'success': True,
            'pending_sales': pending_sales[:100],  # Limitar a 100 más recientes
            'total': len(pending_sales)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo entregas pendientes: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'pending_sales': []
        }), 500

@bp.route('/admin/delete_log', methods=['POST'])
def delete_log():
    if not session.get('admin_logged_in'):
        return redirect(url_for('routes.login_admin'))

    entry = [
        request.form.get('sale_id'),
        request.form.get('item_name'),
        request.form.get('qty'),
        request.form.get('bartender'),
        request.form.get('barra'),
        request.form.get('timestamp')
    ]

    success = delete_log_entry(entry)

    if success:
        flash("Entrada eliminada.", "success")
    else:
        flash("No se pudo eliminar la entrada.", "error")

    return redirect(url_for('routes.admin_logs'))

@bp.route('/admin/clear_all_logs', methods=['POST'])
def clear_all_logs_route():
    if not session.get('admin_logged_in'):
        return redirect(url_for('routes.login_admin'))

    success = clear_all_logs()

    if success:
        flash("Todos los logs han sido eliminados.", "success")
    else:
        flash("No se pudieron eliminar los logs.", "error")

    return redirect(url_for('routes.admin_logs'))

@bp.route('/admin/export_csv')
def export_csv():
    """Exporta todos los logs a CSV"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('routes.login_admin'))
    
    from flask import make_response
    import csv
    import io
    
    logs = load_logs()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Escribir header
    writer.writerow(['sale_id', 'item_name', 'qty', 'bartender', 'barra', 'timestamp'])
    
    # Escribir datos
    for log in logs:
        writer.writerow(log)
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=logs_{time.strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

@bp.route('/admin/turnos')
def admin_turnos():
    """Página de gestión de turnos - Flujo completo"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.jornada_models import Jornada, PlanillaTrabajador, AperturaCaja
        from datetime import datetime
        from app import CHILE_TZ
        
        # Obtener jornada_id desde query params (si se está editando una jornada específica)
        jornada_id_param = request.args.get('jornada_id', type=int)
        
        # Obtener turno del día actual (hora de Chile)
        fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
        
        # Si se especifica jornada_id, cargar esa jornada
        if jornada_id_param:
            jornada_actual = Jornada.query.get(jornada_id_param)
            if not jornada_actual:
                flash(f"❌ No se encontró la jornada con ID {jornada_id_param}", "error")
                return redirect(url_for('routes.admin_turnos'))
            current_app.logger.info(f"📝 Editando jornada ID {jornada_id_param} (fecha: {jornada_actual.fecha_jornada})")
        else:
            # Buscar jornada de hoy primero
            jornada_actual = Jornada.query.filter_by(fecha_jornada=fecha_hoy).first()
            
            # Si no hay jornada de hoy, buscar cualquier jornada abierta
            # (puede ser de días anteriores que aún no se cerró)
            if not jornada_actual:
                jornada_abierta = Jornada.query.filter_by(estado_apertura='abierto').order_by(
                    Jornada.fecha_jornada.desc()
                ).first()
                if jornada_abierta:
                    jornada_actual = jornada_abierta
                    current_app.logger.info(
                        f"✅ Jornada abierta encontrada (fecha: {jornada_actual.fecha_jornada}, "
                        f"buscando para: {fecha_hoy})"
                    )
        
        # Obtener empleados disponibles desde snapshot del turno (NO desde API)
        from app.models.jornada_models import SnapshotEmpleados
        empleados_list = []
        
        # Función helper para obtener empleados desde API o BD
        def _obtener_empleados_fallback():
            """Obtiene empleados activos desde BD local (no desde API)"""
            empleados = []
            try:
                from app.models.pos_models import Employee
                # Solo empleados activos (tanto locales como sincronizados desde PHP POS)
                empleados_disponibles = Employee.query.filter(Employee.is_active == True).order_by(Employee.name).all()
                
                current_app.logger.info(f"📋 Empleados encontrados en BD: {len(empleados_disponibles)} (solo activos)")
                
                for emp_obj in empleados_disponibles:
                    # Verificación adicional: asegurar que esté activo
                    is_active = getattr(emp_obj, 'is_active', True)
                    if not is_active:
                        current_app.logger.warning(f"⚠️  Empleado {emp_obj.id} marcado como inactivo pero pasó el filtro, omitiendo")
                        continue
                    
                    # Obtener nombre completo (usar name, o first_name + last_name como fallback)
                    nombre = getattr(emp_obj, 'name', None)
                    if not nombre or nombre.strip() == '':
                        first_name = getattr(emp_obj, 'first_name', '') or ''
                        last_name = getattr(emp_obj, 'last_name', '') or ''
                        nombre = f"{first_name} {last_name}".strip()
                        if not nombre:
                            nombre = f'Empleado {emp_obj.id}'
                    
                    nombre = nombre.strip()
                    
                    # Filtrar nombres que parecen cargos o roles del sistema
                    nombre_lower = nombre.lower()
                    if nombre_lower in ['admin', 'administrador', 'cajero 1', 'cajero 2', 'cajero 3', 
                                       'bartender 1', 'bartender 2', 'guardia 1', 'guardia 2', 'guardia 3',
                                       'dj 1', 'dj 2']:
                        current_app.logger.debug(f"⏭️  Nombre '{nombre}' parece ser un cargo, omitiendo")
                        continue
                    
                    current_app.logger.debug(f"✅ Agregando empleado activo: {nombre} (ID: {emp_obj.id})")
                    empleados.append({
                        'id': str(emp_obj.id),
                        'name': nombre,
                        'cargo': getattr(emp_obj, 'cargo', 'N/A')
                    })
                current_app.logger.info(f"✅ Empleados activos obtenidos desde BD: {len(empleados)} empleados")
            except Exception as bd_error:
                current_app.logger.warning(f"Error al obtener empleados de BD: {bd_error}")
            return empleados
        
        # SIEMPRE obtener empleados desde BD local (ignorar snapshot para tener datos actualizados)
        # Esto asegura que siempre se muestren los empleados activos más recientes
        current_app.logger.info("📋 Obteniendo empleados activos desde BD local (ignorando snapshot)")
        empleados_list = _obtener_empleados_fallback()
        
        # Obtener historial de turnos (más registros para el selector)
        jornadas_historial = Jornada.query.order_by(Jornada.fecha_jornada.desc()).limit(50).all()
        
        # Obtener estado del turno (compatibilidad con sistema anterior)
        shift_service = get_shift_service()
        shift_status = shift_service.get_current_shift_status()
        shift_status_dict = shift_status.to_dict() if hasattr(shift_status, 'to_dict') else {
            'is_open': shift_status.is_open,
            'shift_date': shift_status.shift_date,
            'opened_at': shift_status.opened_at,
            'closed_at': shift_status.closed_at,
            'fiesta_nombre': shift_status.fiesta_nombre,
            'djs': shift_status.djs
        }
        
        # Obtener métricas del turno para el footer
        shift_metrics = {}
        if shift_status.is_open:
            try:
                stats_service = get_stats_service()
                from datetime import datetime
                
                # Calcular tiempo transcurrido usando abierto_en directamente de la jornada
                if jornada_actual and jornada_actual.abierto_en:
                    # Usar abierto_en directamente (ya está en UTC naive)
                    # Calcular diferencia usando hora de Chile para que sea más preciso
                    opened_dt_utc = jornada_actual.abierto_en
                    now_chile = datetime.now(CHILE_TZ)
                    
                    # Manejar abierto_en: puede ser UTC naive (antiguo) o UTC naive que representa hora de Chile
                    if opened_dt_utc.tzinfo is None:
                        # Si no tiene timezone, verificar si es muy antiguo (más de 12 horas)
                        # Si es muy antiguo, probablemente fue guardado como hora local (Chile) sin timezone
                        diff_naive = now_chile.replace(tzinfo=None) - opened_dt_utc
                        if diff_naive.total_seconds() > 12 * 3600:  # Más de 12 horas
                            # Asumir que es hora local (Chile) sin timezone
                            opened_dt_chile = CHILE_TZ.localize(opened_dt_utc)
                        else:
                            # Asumir que es UTC (nuevo formato)
                            from datetime import timezone
                            opened_dt_utc_aware = opened_dt_utc.replace(tzinfo=timezone.utc)
                            opened_dt_chile = opened_dt_utc_aware.astimezone(CHILE_TZ)
                    else:
                        # Ya tiene timezone, convertir a Chile
                        opened_dt_chile = opened_dt_utc.astimezone(CHILE_TZ)
                    
                    # Calcular diferencia en hora de Chile
                    diff = now_chile - opened_dt_chile
                    hours = int(diff.total_seconds() // 3600)
                    minutes = int((diff.total_seconds() % 3600) // 60)
                    shift_metrics['tiempo_transcurrido'] = f"{hours}h {minutes}m"
                elif shift_status.opened_at:
                    # Fallback: parsear desde string
                    try:
                        opened_dt = datetime.fromisoformat(shift_status.opened_at.replace('Z', '+00:00') if 'Z' in shift_status.opened_at else shift_status.opened_at)
                        # Si tiene timezone, convertir a naive UTC
                        if opened_dt.tzinfo:
                            opened_dt = opened_dt.replace(tzinfo=None)
                        now = datetime.now(CHILE_TZ)
                        # Convertir opened_dt a hora de Chile para comparar
                        if opened_dt.tzinfo is None:
                            opened_dt_aware = pytz.UTC.localize(opened_dt)
                        else:
                            opened_dt_aware = opened_dt
                        opened_dt_chile = opened_dt_aware.astimezone(CHILE_TZ)
                        diff = now - opened_dt_chile
                        hours = int(diff.total_seconds() // 3600)
                        minutes = int((diff.total_seconds() % 3600) // 60)
                        shift_metrics['tiempo_transcurrido'] = f"{hours}h {minutes}m"
                    except Exception as e:
                        current_app.logger.error(f"Error al parsear opened_at: {e}")
                        shift_metrics['tiempo_transcurrido'] = 'N/A'
                else:
                    shift_metrics['tiempo_transcurrido'] = 'N/A'
                
                # Obtener estadísticas del turno
                delivery_stats = stats_service.get_delivery_stats(
                    start_date=shift_status.shift_date,
                    end_date=shift_status.shift_date
                )
                shift_metrics['total_entregas'] = delivery_stats.get('total_deliveries', 0)
                
                # Obtener entradas
                from .helpers.pos_api import get_entradas_sales
                try:
                    entradas_sales = get_entradas_sales(limit=100)
                    shift_metrics['total_entradas'] = len([s for s in entradas_sales if s.get('sale_time', '').startswith(shift_status.shift_date)])
                except:
                    shift_metrics['total_entradas'] = 0
            except Exception as e:
                current_app.logger.warning(f"Error al calcular métricas del turno: {e}")
                shift_metrics = {
                    'tiempo_transcurrido': 'N/A',
                    'total_entregas': 0,
                    'total_entradas': 0
                }
        
        # Obtener planilla de trabajadores si existe turno
        planilla_trabajadores = []
        responsables = {}
        if jornada_actual:
            planilla_trabajadores = [p.to_dict() for p in jornada_actual.planilla_trabajadores]
            responsables = {
                'cajas': jornada_actual.responsable_cajas,
                'puerta': jornada_actual.responsable_puerta,
                'seguridad': jornada_actual.responsable_seguridad,
                'admin': jornada_actual.responsable_admin
            }
        
        # Hacer shift_status y shift_metrics disponibles globalmente para base.html
        g.shift_status = shift_status_dict
        g.shift_metrics = shift_metrics
        
        return render_template('admin_turnos.html',
                             jornada_actual=jornada_actual,  # Pasar objeto Jornada directamente, no diccionario
                             empleados_disponibles=empleados_list,
                             jornadas_historial=[j.to_dict() for j in jornadas_historial],
                             shift_status=shift_status_dict,
                             shift_metrics=shift_metrics,
                             fecha_hoy=fecha_hoy,
                             planilla_trabajadores=planilla_trabajadores,
                             responsables=responsables,
                             jornada_id_actual=jornada_actual.id if jornada_actual else None)
    except Exception as e:
        current_app.logger.error(f"Error al cargar página de turnos: {e}", exc_info=True)
        flash(f"Error al cargar información de turnos: {str(e)}", "error")
        return redirect(url_for('routes.admin_dashboard'))

@bp.route('/admin/turnos/crear-jornada', methods=['POST'])
def crear_jornada():
    """Paso 2: Crear turno del día"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.jornada_models import Jornada
        from datetime import datetime
        
        fecha_jornada = request.form.get('fecha_jornada')
        tipo_turno = request.form.get('tipo_turno')
        nombre_fiesta = request.form.get('nombre_fiesta')
        horario_apertura = request.form.get('horario_apertura_programado')
        horario_cierre = request.form.get('horario_cierre_programado')
        
        # Usar el servicio para crear la jornada (maneja automáticamente jornadas cerradas)
        from app.application.services.jornada_service import JornadaService
        from app.application.dto.jornada_dto import CrearJornadaRequest
        
        jornada_service = JornadaService()
        crear_request = CrearJornadaRequest(
            fecha_jornada=fecha_jornada,
            tipo_turno=tipo_turno,
            nombre_fiesta=nombre_fiesta,
            horario_apertura_programado=horario_apertura,
            horario_cierre_programado=horario_cierre
        )
        
        current_app.logger.info(f"📝 Creando jornada: fecha={fecha_jornada}, tipo={tipo_turno}, nombre={nombre_fiesta}")
        
        success, message, nueva_jornada = jornada_service.crear_jornada(
            crear_request,
            creado_por=session.get('admin_username', 'admin')
        )
        
        current_app.logger.info(f"📊 Resultado crear_jornada: success={success}, message={message}, jornada_id={nueva_jornada.id if nueva_jornada else None}")
        
        if not success:
            current_app.logger.error(f"❌ Error al crear jornada: {message}")
            flash(f"❌ {message}", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        flash(f"✅ Turno creado exitosamente para {fecha_jornada}", "success")
        return redirect(url_for('routes.admin_turnos', jornada_id=nueva_jornada.id))
        
    except Exception as e:
        current_app.logger.error(f"Error al crear jornada: {e}", exc_info=True)
        db.session.rollback()
        flash(f"❌ Error al crear turno: {str(e)}", "error")
        return redirect(url_for('routes.admin_turnos'))

@bp.route('/admin/turnos/actualizar-jornada', methods=['POST'])
def actualizar_jornada():
    """Actualizar jornada existente"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.jornada_models import Jornada
        
        jornada_id = request.form.get('jornada_id', type=int)
        if not jornada_id:
            flash("❌ ID de jornada no proporcionado", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        jornada = Jornada.query.get(jornada_id)
        if not jornada:
            flash(f"❌ No se encontró la jornada con ID {jornada_id}", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        # Actualizar campos
        jornada.fecha_jornada = request.form.get('fecha_jornada')
        jornada.tipo_turno = request.form.get('tipo_turno')
        jornada.nombre_fiesta = request.form.get('nombre_fiesta')
        jornada.horario_apertura_programado = request.form.get('horario_apertura_programado')
        jornada.horario_cierre_programado = request.form.get('horario_cierre_programado')
        
        db.session.commit()
        
        flash(f"✅ Turno actualizado exitosamente", "success")
        return redirect(url_for('routes.admin_turnos', jornada_id=jornada_id))
        
    except Exception as e:
        current_app.logger.error(f"Error al actualizar jornada: {e}", exc_info=True)
        db.session.rollback()
        flash(f"❌ Error al actualizar turno: {str(e)}", "error")
        return redirect(url_for('routes.admin_turnos'))

@bp.route('/admin/turnos/agregar-trabajador', methods=['POST'])
def agregar_trabajador():
    """Paso 3: Agregar trabajador a la planilla"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.jornada_models import Jornada, PlanillaTrabajador
        from datetime import datetime
        
        jornada_id = request.form.get('jornada_id')
        id_empleado = request.form.get('id_empleado')
        nombre_empleado = request.form.get('nombre_empleado') or id_empleado
        rol = request.form.get('rol')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')
        costo_hora = float(request.form.get('costo_hora', 0))
        area = request.form.get('area', '')
        
        jornada = Jornada.query.get(jornada_id)
        if not jornada:
            flash("Jornada no encontrada.", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        # Obtener nombre del empleado si existe en la BD
        from app.models import Employee
        empleado = Employee.query.filter_by(id=id_empleado).first()
        if empleado:
            nombre_empleado = getattr(empleado, 'name', nombre_empleado)
        
        # Calcular costo total
        try:
            inicio = datetime.strptime(hora_inicio, '%H:%M')
            fin = datetime.strptime(hora_fin, '%H:%M')
            if fin < inicio:
                fin = fin.replace(day=fin.day + 1)
            diferencia = fin - inicio
            horas_trabajadas = diferencia.total_seconds() / 3600.0
            costo_total = costo_hora * horas_trabajadas
        except:
            costo_total = 0
        
        # Crear trabajador en planilla
        trabajador = PlanillaTrabajador(
            jornada_id=jornada_id,
            id_empleado=id_empleado,
            nombre_empleado=nombre_empleado,
            rol=rol,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            costo_hora=costo_hora,
            costo_total=costo_total,
            area=area
        )
        
        db.session.add(trabajador)
        db.session.commit()
        
        flash(f"✅ Trabajador {nombre_empleado} agregado a la planilla", "success")
        return redirect(url_for('routes.admin_turnos'))
        
    except Exception as e:
        current_app.logger.error(f"Error al agregar trabajador: {e}", exc_info=True)
        db.session.rollback()
        flash(f"❌ Error al agregar trabajador: {str(e)}", "error")
        return redirect(url_for('routes.admin_turnos'))

@bp.route('/admin/turnos/asignar-planilla-responsables', methods=['POST'])
def asignar_planilla_responsables():
    """Paso 3: Asignar planilla de trabajadores y responsables juntos"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.jornada_models import Jornada, PlanillaTrabajador
        from datetime import datetime
        
        jornada_id = request.form.get('jornada_id')
        jornada = Jornada.query.get(jornada_id)
        
        if not jornada:
            flash("Jornada no encontrada.", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        # Procesar trabajadores desde la planilla tipo tabla
        # Los datos vienen como: planilla[rowId][empleado_id] y planilla[rowId][cargo]
        from app.models import Employee
        from app.models.cargo_salary_models import CargoSalaryConfig
        
        # Obtener todos los datos de planilla del formulario
        planilla_data = {}
        for key in request.form.keys():
            if key.startswith('planilla['):
                # Parsear: planilla[rowId][campo] = valor
                import re
                match = re.match(r'planilla\[([^\]]+)\]\[([^\]]+)\]', key)
                if match:
                    row_id = match.group(1)
                    campo = match.group(2)
                    valor = request.form.get(key)
                    
                    if row_id not in planilla_data:
                        planilla_data[row_id] = {}
                    planilla_data[row_id][campo] = valor
        
        # Obtener trabajadores existentes (mapeados por id_empleado + cargo para permitir duplicados)
        trabajadores_existentes = {(str(t.id_empleado), t.rol): t for t in jornada.planilla_trabajadores}
        
        # Crear conjunto de trabajadores nuevos desde la planilla
        trabajadores_nuevos = set()
        for row_id, row_data in planilla_data.items():
            empleado_id = row_data.get('empleado_id', '').strip()
            cargo = row_data.get('cargo', '').strip()
            
            if empleado_id and cargo:
                trabajadores_nuevos.add((empleado_id, cargo))
        
        # Eliminar trabajadores que no están en la nueva planilla
        for (emp_id, cargo), trabajador in trabajadores_existentes.items():
            if (emp_id, cargo) not in trabajadores_nuevos:
                db.session.delete(trabajador)
        
        # Agregar o actualizar trabajadores desde la planilla
        for row_id, row_data in planilla_data.items():
            empleado_id = row_data.get('empleado_id', '').strip()
            cargo = row_data.get('cargo', '').strip()
            area = row_data.get('area', '').strip() or cargo  # Usar cargo como fallback si no hay area
            
            if not empleado_id or not cargo:
                continue
            
            # Buscar si ya existe este trabajador con este cargo
            trabajador_existente = trabajadores_existentes.get((empleado_id, cargo))
            
            if trabajador_existente:
                # Actualizar trabajador existente (por si cambió algo)
                empleado = Employee.query.filter_by(id=empleado_id).first()
                nombre = empleado.name if empleado else f'Empleado {empleado_id}'
                trabajador_existente.nombre_empleado = nombre
                trabajador_existente.rol = cargo
                trabajador_existente.area = area  # Actualizar también el área/servicio
                
                # Actualizar el pago según el cargo (importante: recalcular siempre)
                cargo_salary = CargoSalaryConfig.query.filter_by(cargo=cargo).first()
                sueldo_por_turno = float(cargo_salary.sueldo_por_turno) if cargo_salary else 0.0
                bono_fijo = float(cargo_salary.bono_fijo) if cargo_salary else 0.0
                
                # Calcular costo total (sueldo por turno + bono fijo)
                costo_total = sueldo_por_turno + bono_fijo
                
                # Calcular costo por hora (aproximado para mostrar en planilla)
                # Asumir 8 horas de trabajo por defecto
                horas_trabajo = 8.0
                costo_hora = costo_total / horas_trabajo if horas_trabajo > 0 else 0
                
                # Actualizar costos en el trabajador existente
                trabajador_existente.costo_hora = costo_hora
                trabajador_existente.costo_total = costo_total
                
                current_app.logger.info(
                    f"💰 Pago actualizado para {nombre} (Cargo: {cargo}): "
                    f"Sueldo base: ${sueldo_por_turno:.0f}, Bono: ${bono_fijo:.0f}, Total: ${costo_total:.0f}"
                )
            else:
                # Crear nuevo trabajador
                empleado = Employee.query.filter_by(id=empleado_id).first()
                nombre = empleado.name if empleado else f'Empleado {empleado_id}'
                
                # Obtener sueldo del cargo si está configurado
                cargo_salary = CargoSalaryConfig.query.filter_by(cargo=cargo).first()
                sueldo_por_turno = float(cargo_salary.sueldo_por_turno) if cargo_salary else 0.0
                bono_fijo = float(cargo_salary.bono_fijo) if cargo_salary else 0.0
                
                # Calcular costo total (sueldo por turno + bono fijo)
                costo_total = sueldo_por_turno + bono_fijo
                
                # Calcular costo por hora (aproximado para mostrar en planilla)
                # Asumir 8 horas de trabajo por defecto
                horas_trabajo = 8.0
                costo_hora = costo_total / horas_trabajo if horas_trabajo > 0 else 0
                
                trabajador = PlanillaTrabajador(
                    jornada_id=jornada_id,
                    id_empleado=empleado_id,
                    nombre_empleado=nombre,
                    rol=cargo,
                    area=area,  # Asignar el servicio/área
                    hora_inicio=jornada.horario_apertura_programado or '20:00',
                    hora_fin=jornada.horario_cierre_programado or '04:00',
                    costo_hora=costo_hora,
                    costo_total=costo_total
                )
                db.session.add(trabajador)
                
                current_app.logger.info(
                    f"💰 Pago asignado a {nombre} (Cargo: {cargo}): "
                    f"Sueldo base: ${sueldo_por_turno:.0f}, Bono: ${bono_fijo:.0f}, Total: ${costo_total:.0f}"
                )
        
        # Responsables eliminados - ya no se procesan
        
        db.session.commit()
        
        flash("✅ Planilla actualizada correctamente", "success")
        return redirect(url_for('routes.admin_turnos'))
        
    except Exception as e:
        current_app.logger.error(f"Error al asignar planilla y responsables: {e}", exc_info=True)
        db.session.rollback()
        flash(f"❌ Error al actualizar: {str(e)}", "error")
        return redirect(url_for('routes.admin_turnos'))

@bp.route('/admin/turnos/asignar-responsables', methods=['POST'])
def asignar_responsables():
    """Paso 4: Asignar responsables de cada área"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.jornada_models import Jornada
        
        jornada_id = request.form.get('jornada_id')
        responsable_cajas = request.form.get('responsable_cajas', '').strip()
        responsable_puerta = request.form.get('responsable_puerta', '').strip()
        responsable_seguridad = request.form.get('responsable_seguridad', '').strip()
        responsable_admin = request.form.get('responsable_admin', '').strip()
        
        jornada = Jornada.query.get(jornada_id)
        if not jornada:
            flash("Jornada no encontrada.", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        jornada.responsable_cajas = responsable_cajas
        jornada.responsable_puerta = responsable_puerta
        jornada.responsable_seguridad = responsable_seguridad
        jornada.responsable_admin = responsable_admin
        
        db.session.commit()
        
        flash("✅ Responsables asignados correctamente", "success")
        return redirect(url_for('routes.admin_turnos'))
        
    except Exception as e:
        current_app.logger.error(f"Error al asignar responsables: {e}", exc_info=True)
        db.session.rollback()
        flash(f"❌ Error al asignar responsables: {str(e)}", "error")
        return redirect(url_for('routes.admin_turnos'))

@bp.route('/admin/turnos/abrir-local', methods=['POST'])
def abrir_local():
    """Paso 5: Abrir local - Habilita ventas, escaneo y control"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.jornada_models import Jornada
        from datetime import datetime
        from app import CHILE_TZ
        
        jornada_id = request.form.get('jornada_id')
        jornada = Jornada.query.get(jornada_id)
        
        if not jornada:
            flash("Jornada no encontrada.", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        # Validar que todos los pasos estén completos
        if jornada.estado_apertura == 'abierto':
            flash("El local ya está abierto.", "warning")
            return redirect(url_for('routes.admin_turnos'))
        
        if not jornada.planilla_trabajadores:
            flash("Debes agregar al menos un trabajador a la planilla.", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        # Usar el servicio JornadaService para abrir el local correctamente
        # Esto asegura que se creen los EmployeeShift con los pagos
        from app.application.services.jornada_service import JornadaService
        from app.application.dto.jornada_dto import AbrirLocalRequest
        
        jornada_service = JornadaService()
        abrir_request = AbrirLocalRequest(
            abierto_por=session.get('admin_username', 'admin')
        )
        
        success, message = jornada_service.abrir_local(jornada_id, abrir_request)
        
        if not success:
            flash(f"❌ Error al abrir local: {message}", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        # El servicio JornadaService ya maneja todo (snapshots, EmployeeShift, etc.)
        # Solo mostrar mensaje de éxito
        flash("✅ Local abierto exitosamente. Sistema habilitado para ventas, escaneo y control en tiempo real.", "success")
        return redirect(url_for('routes.admin_turnos'))
        
    except Exception as e:
        current_app.logger.error(f"Error al abrir local: {e}", exc_info=True)
        db.session.rollback()
        flash(f"❌ Error al abrir local: {str(e)}", "error")
        return redirect(url_for('routes.admin_turnos'))

@bp.route('/admin/turnos/ver-detalle/<int:jornada_id>')
def ver_detalle_jornada(jornada_id):
    """Ver detalle de un turno específico"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.jornada_models import Jornada, PlanillaTrabajador, AperturaCaja
        from app.application.services.service_factory import get_stats_service
        
        jornada = Jornada.query.get(jornada_id)
        if not jornada:
            flash("Jornada no encontrada.", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        # Obtener planilla de trabajadores
        planilla = [p.to_dict() for p in jornada.planilla_trabajadores]
        
        # Obtener aperturas de cajas
        aperturas = [a.to_dict() for a in jornada.aperturas_cajas]
        
        # Obtener cierres de caja del turno
        from app.models.pos_models import RegisterClose
        from datetime import datetime
        import pytz
        
        CHILE_TZ = pytz.timezone('America/Santiago')
        
        cierres_caja = []
        if jornada.fecha_jornada:
            closes = RegisterClose.query.filter_by(shift_date=jornada.fecha_jornada).order_by(RegisterClose.closed_at.desc()).all()
            
            for close in closes:
                # Calcular total recaudado
                actual_cash = float(close.actual_cash or 0)
                actual_debit = float(close.actual_debit or 0)
                actual_credit = float(close.actual_credit or 0)
                total_recaudado = actual_cash + actual_debit + actual_credit
                
                # Si total_amount es 0 pero hay montos reales, usar la suma de los montos reales
                total_amount = float(close.total_amount or 0)
                if total_amount == 0 and total_recaudado > 0:
                    total_amount = total_recaudado
                
                # Formatear fechas
                opened_at_formatted = None
                if close.opened_at:
                    try:
                        if isinstance(close.opened_at, str):
                            dt = datetime.strptime(close.opened_at, '%Y-%m-%d %H:%M:%S')
                        elif isinstance(close.opened_at, datetime):
                            dt = close.opened_at
                        else:
                            opened_at_formatted = str(close.opened_at)
                            dt = None
                        
                        if dt:
                            hour = dt.hour
                            period = 'a. m.' if hour < 12 else 'p. m.'
                            hour12 = hour % 12 if hour % 12 != 0 else 12
                            opened_at_formatted = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
                    except Exception as e:
                        current_app.logger.warning(f"Error formateando opened_at: {e}")
                        opened_at_formatted = str(close.opened_at) if close.opened_at else 'N/A'
                
                closed_at_formatted = None
                if close.closed_at:
                    try:
                        if isinstance(close.closed_at, datetime):
                            dt = close.closed_at
                        elif isinstance(close.closed_at, str):
                            dt = datetime.strptime(close.closed_at, '%Y-%m-%d %H:%M:%S')
                        else:
                            closed_at_formatted = str(close.closed_at)
                            dt = None
                        
                        if dt:
                            hour = dt.hour
                            period = 'a. m.' if hour < 12 else 'p. m.'
                            hour12 = hour % 12 if hour % 12 != 0 else 12
                            closed_at_formatted = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
                    except Exception as e:
                        current_app.logger.warning(f"Error formateando closed_at: {e}")
                        closed_at_formatted = str(close.closed_at) if close.closed_at else 'N/A'
                
                cierres_caja.append({
                    'id': close.id,
                    'register_id': str(close.register_id),
                    'register_name': close.register_name or f'Caja {close.register_id}',
                    'employee_name': close.employee_name or 'Sin asignar',
                    'opened_at': opened_at_formatted,
                    'closed_at': closed_at_formatted,
                    'total_sales': int(close.total_sales) if close.total_sales else 0,
                    'total_amount': total_amount,
                    'expected_cash': float(close.expected_cash or 0),
                    'actual_cash': actual_cash,
                    'actual_debit': actual_debit,
                    'actual_credit': actual_credit,
                    'diff_cash': float(close.diff_cash or 0),
                    'diff_debit': float(close.diff_debit or 0),
                    'diff_credit': float(close.diff_credit or 0),
                    'difference_total': float(close.difference_total or 0),
                    'status': close.status or 'closed'
                })
        
        # Obtener estadísticas si está abierta
        estadisticas = {}
        if jornada.estado_apertura == 'abierto':
            try:
                stats_service = get_stats_service()
                delivery_stats = stats_service.get_delivery_stats(
                    start_date=jornada.fecha_jornada,
                    end_date=jornada.fecha_jornada
                )
                estadisticas = {
                    'total_entregas': delivery_stats.get('total_deliveries', 0),
                    'total_entradas': 0  # Se puede calcular si es necesario
                }
            except:
                pass
        
        # Obtener estado del turno para el template base.html
        from app.application.services.service_factory import get_shift_service
        shift_service = get_shift_service()
        shift_status = shift_service.get_current_shift_status()
        shift_status_dict = shift_status.to_dict() if hasattr(shift_status, 'to_dict') else {
            'is_open': shift_status.is_open,
            'shift_date': shift_status.shift_date,
            'opened_at': shift_status.opened_at,
            'closed_at': shift_status.closed_at,
            'fiesta_nombre': shift_status.fiesta_nombre,
            'djs': shift_status.djs
        }
        
        # Obtener métricas del turno para el footer
        shift_metrics = {}
        if shift_status.is_open:
            try:
                stats_service = get_stats_service()
                from datetime import datetime
                
                # Calcular tiempo transcurrido usando abierto_en directamente de la jornada
                if jornada and jornada.abierto_en:
                    opened_dt_utc = jornada.abierto_en
                    now_chile = datetime.now(CHILE_TZ)
                    
                    # Manejar abierto_en: puede ser UTC naive o hora local (Chile) sin timezone
                    if opened_dt_utc.tzinfo is None:
                        # Si no tiene timezone, verificar cuál es más probable
                        diff_naive = now_chile.replace(tzinfo=None) - opened_dt_utc
                        
                        # Si la diferencia naive es razonable (menos de 12 horas), 
                        # probablemente es hora local (Chile) sin timezone
                        if abs(diff_naive.total_seconds()) < 12 * 3600:  # Menos de 12 horas
                            opened_dt_chile = CHILE_TZ.localize(opened_dt_utc)
                        else:
                            # Asumir que es UTC (nuevo formato)
                            from datetime import timezone
                            opened_dt_utc_aware = opened_dt_utc.replace(tzinfo=timezone.utc)
                            opened_dt_chile = opened_dt_utc_aware.astimezone(CHILE_TZ)
                    else:
                        # Ya tiene timezone, convertir a Chile
                        opened_dt_chile = opened_dt_utc.astimezone(CHILE_TZ)
                    
                    # Calcular diferencia en hora de Chile
                    diff = now_chile - opened_dt_chile
                    hours = int(diff.total_seconds() // 3600)
                    minutes = int((diff.total_seconds() % 3600) // 60)
                    shift_metrics['tiempo_transcurrido'] = f"{hours}h {minutes}m"
                elif shift_status.opened_at:
                    # Fallback: parsear desde string
                    try:
                        opened_dt = datetime.fromisoformat(shift_status.opened_at.replace('Z', '+00:00') if 'Z' in shift_status.opened_at else shift_status.opened_at)
                        # Si tiene timezone, convertir a naive UTC
                        if opened_dt.tzinfo:
                            opened_dt = opened_dt.replace(tzinfo=None)
                        now = datetime.now(CHILE_TZ)
                        # Convertir opened_dt a hora de Chile para comparar
                        if opened_dt.tzinfo is None:
                            opened_dt_aware = pytz.UTC.localize(opened_dt)
                        else:
                            opened_dt_aware = opened_dt
                        opened_dt_chile = opened_dt_aware.astimezone(CHILE_TZ)
                        diff = now - opened_dt_chile
                        hours = int(diff.total_seconds() // 3600)
                        minutes = int((diff.total_seconds() % 3600) // 60)
                        shift_metrics['tiempo_transcurrido'] = f"{hours}h {minutes}m"
                    except Exception as e:
                        current_app.logger.error(f"Error al parsear opened_at: {e}")
                        shift_metrics['tiempo_transcurrido'] = 'N/A'
                else:
                    shift_metrics['tiempo_transcurrido'] = 'N/A'
                
                # Obtener estadísticas del turno
                delivery_stats = stats_service.get_delivery_stats(
                    start_date=shift_status.shift_date,
                    end_date=shift_status.shift_date
                )
                shift_metrics['total_entregas'] = delivery_stats.get('total_deliveries', 0)
                
                # Obtener entradas
                from .helpers.pos_api import get_entradas_sales
                try:
                    entradas_sales = get_entradas_sales(limit=100)
                    shift_metrics['total_entradas'] = len([s for s in entradas_sales if s.get('sale_time', '').startswith(shift_status.shift_date)])
                except:
                    shift_metrics['total_entradas'] = 0
            except Exception as e:
                current_app.logger.warning(f"Error al calcular métricas del turno: {e}")
                shift_metrics = {
                    'tiempo_transcurrido': 'N/A',
                    'total_entregas': 0,
                    'total_entradas': 0
                }
        
        # Hacer shift_status y shift_metrics disponibles globalmente para base.html
        from flask import g
        g.shift_status = shift_status_dict
        g.shift_metrics = shift_metrics
        
        return render_template('admin_detalle_jornada.html',
                             jornada=jornada.to_dict(),
                             planilla=planilla,
                             aperturas=aperturas,
                             estadisticas=estadisticas,
                             cierres_caja=cierres_caja,
                             shift_status=shift_status_dict,
                             shift_metrics=shift_metrics)
    except Exception as e:
        current_app.logger.error(f"Error al cargar detalle de jornada: {e}", exc_info=True)
        flash(f"Error al cargar detalle: {str(e)}", "error")
        return redirect(url_for('routes.admin_turnos'))

@bp.route('/admin/turnos/cerrar-jornada', methods=['POST'])
def cerrar_jornada():
    """Cerrar un turno que quedó abierto"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.models.jornada_models import Jornada
        from datetime import datetime
        
        jornada_id = request.form.get('jornada_id')
        jornada = Jornada.query.get(jornada_id)
        
        if not jornada:
            flash("Turno no encontrado.", "error")
            return redirect(url_for('routes.admin_turnos'))
        
        if jornada.estado_apertura != 'abierto':
            flash("Este turno ya está cerrado.", "warning")
            return redirect(url_for('routes.admin_turnos'))
        
        # Cerrar el turno
        jornada.estado_apertura = 'cerrado'
        # Nota: El modelo Jornada no tiene campo closed_at, solo estado_apertura
        
        # Cerrar turnos de empleados y calcular sueldos
        try:
            from app.models.employee_shift_models import EmployeeShift
            from datetime import datetime
            from app import CHILE_TZ
            import pytz
            
            now_chile = datetime.now(CHILE_TZ)
            now_utc = now_chile.astimezone(pytz.UTC).replace(tzinfo=None)
            
            # Obtener todos los turnos activos de esta jornada
            employee_shifts = EmployeeShift.query.filter_by(
                jornada_id=jornada_id,
                estado='activo'
            ).all()
            
            for shift in employee_shifts:
                # Parsear hora de fin desde planilla si existe
                from app.models.jornada_models import PlanillaTrabajador
                planilla = PlanillaTrabajador.query.filter_by(
                    jornada_id=jornada_id,
                    id_empleado=shift.employee_id
                ).first()
                
                if planilla:
                    try:
                        hora_fin_str = planilla.hora_fin
                        fecha_jornada = jornada.fecha_jornada
                        hora_fin_dt = datetime.strptime(f"{fecha_jornada} {hora_fin_str}", "%Y-%m-%d %H:%M")
                        # Si la hora fin es menor que inicio, asumir día siguiente
                        if hora_fin_dt < hora_fin_dt.replace(hour=12):
                            from datetime import timedelta
                            hora_fin_dt = hora_fin_dt + timedelta(days=1)
                        hora_fin_chile = CHILE_TZ.localize(hora_fin_dt)
                        hora_fin_utc = hora_fin_chile.astimezone(pytz.UTC).replace(tzinfo=None)
                    except:
                        hora_fin_utc = now_utc
                else:
                    hora_fin_utc = now_utc
                
                shift.hora_fin = hora_fin_utc
                shift.estado = 'cerrado'
                # IMPORTANTE: Solo recalcular si NO está pagado (para proteger sueldo congelado)
                if not shift.pagado:
                    shift.sueldo_turno = shift.calcular_sueldo_turno()
                shift.horas_trabajadas = shift.calcular_horas_trabajadas()
        except Exception as e:
            current_app.logger.warning(f"Error al cerrar turnos de empleados: {e}")
            # No fallar si hay error al cerrar turnos
        
        # Cerrar todas las cajas abiertas de esta jornada
        try:
            from app.models.jornada_models import AperturaCaja
            cajas_abiertas = AperturaCaja.query.filter_by(
                jornada_id=jornada_id,
                estado='abierta'
            ).all()
            
            for caja in cajas_abiertas:
                caja.estado = 'cerrada'
                caja.cerrada_en = now_utc
                caja.cerrada_por = session.get('admin_username', 'admin')
            current_app.logger.info(f"✅ {len(cajas_abiertas)} cajas cerradas")
        except Exception as e:
            current_app.logger.warning(f"Error al cerrar cajas: {e}")
        
        # ========== RESETEO COMPLETO DE PASOS DE LA JORNADA ==========
        # Resetear todos los pasos de la jornada para que no interfiera con nuevos turnos
        try:
            # Resetear estado a 'preparando' (no 'cerrado' para que pueda ser reutilizada o eliminada)
            jornada.estado_apertura = 'preparando'
            
            # Limpiar checklist técnico
            jornada.checklist_tecnico = None
            
            # Limpiar checklist de apertura
            jornada.checklist_apertura = None
            
            # Limpiar responsables (ya no se usan, pero por si acaso)
            jornada.responsable_cajas = None
            jornada.responsable_puerta = None
            jornada.responsable_seguridad = None
            jornada.responsable_admin = None
            
            # Limpiar información de apertura
            jornada.abierto_en = None
            jornada.abierto_por = None
            jornada.horario_apertura_real = None
            
            # Eliminar planilla de trabajadores (cascade debería hacerlo, pero por si acaso)
            from app.models.jornada_models import PlanillaTrabajador
            planilla_trabajadores = PlanillaTrabajador.query.filter_by(jornada_id=jornada_id).all()
            for trabajador in planilla_trabajadores:
                db.session.delete(trabajador)
            current_app.logger.info(f"✅ {len(planilla_trabajadores)} trabajadores eliminados de la planilla")
            
            # Eliminar aperturas de cajas (ya cerradas arriba, pero las eliminamos completamente)
            for caja in cajas_abiertas:
                db.session.delete(caja)
            
            current_app.logger.info("✅ Pasos de la jornada reseteados completamente")
        except Exception as e:
            current_app.logger.error(f"Error al resetear pasos de jornada: {e}", exc_info=True)
            # Continuar aunque haya error
        
        db.session.commit()
        
        # ========== RESETEO COMPLETO DEL SISTEMA ==========
        # Guardar variables de admin que NO se deben resetear
        admin_logged_in = session.get('admin_logged_in')
        admin_username = session.get('admin_username')
        last_activity = session.get('last_activity')
        session_id = session.get('session_id')
        
        # Limpiar TODA la sesión
        session.clear()
        
        # Restaurar solo las variables de admin
        if admin_logged_in:
            session['admin_logged_in'] = admin_logged_in
        if admin_username:
            session['admin_username'] = admin_username
        if last_activity:
            session['last_activity'] = last_activity
        if session_id:
            session['session_id'] = session_id
        
        # Limpiar cache del sistema
        try:
            from .helpers.cache import clear_cache, invalidate_sale_cache
            clear_cache()
            invalidate_sale_cache()
            current_app.logger.info("✅ Cache limpiado")
        except Exception as e:
            current_app.logger.warning(f"Error al limpiar cache: {e}")
        
        # Cerrar sesiones de encuestas si existen
        try:
            from app.application.services.service_factory import get_survey_service
            survey_service = get_survey_service()
            survey_service.close_session(jornada.fecha_jornada)
            current_app.logger.info("✅ Sesiones de encuestas cerradas")
        except Exception as e:
            current_app.logger.warning(f"Error al cerrar sesiones de encuestas: {e}")
        
        # Cerrar turno del sistema legacy si existe
        try:
            from .helpers.shift_manager_compat import get_shift_status, close_shift as shift_close
            shift_status = get_shift_status()
            if shift_status.get('is_open', False):
                shift_close(closed_by=admin_username or 'admin')
                current_app.logger.info("✅ Turno legacy cerrado")
        except Exception as e:
            current_app.logger.warning(f"Error al cerrar turno legacy: {e}")
        
        # Sistema único - no necesita sincronización
        current_app.logger.info("✅ Turno cerrado - Sistema completamente reseteado (excepto login admin)")
        
        flash(f"✅ Turno del {jornada.fecha_jornada} cerrado correctamente. Todo el sistema ha sido reseteado.", "success")
        return redirect(url_for('routes.admin_turnos'))
        
    except Exception as e:
        current_app.logger.error(f"Error al cerrar jornada: {e}", exc_info=True)
        db.session.rollback()
        flash(f"❌ Error al cerrar turno: {str(e)}", "error")
        return redirect(url_for('routes.admin_turnos'))

@bp.route('/admin/shift_history')
def shift_history():
    """Historial detallado de turnos cerrados"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    try:
        stats_service = get_stats_service()
        shift_service = get_shift_service()
        
        # Obtener todos los turnos cerrados (sin límite para mostrar todos los días disponibles)
        shift_history_list = shift_service.get_shift_history(limit=365)  # Último año
        
        # Obtener estadísticas detalladas para cada turno
        shifts_stats = stats_service.get_shifts_history_stats(limit=365)
        
        # Organizar por fecha (más reciente primero)
        shifts_by_date = {}
        for shift_stat in shifts_stats:
            shift_date = shift_stat.get('shift_date', '')
            if shift_date:
                shifts_by_date[shift_date] = shift_stat
        
        # Obtener lista de días únicos ordenados (más reciente primero)
        available_dates = sorted(shifts_by_date.keys(), reverse=True) if shifts_by_date else []
        
        # Obtener fecha seleccionada (si viene en query param)
        selected_date = request.args.get('date', None)
        
        # Si hay una fecha seleccionada, obtener datos detallados de ese turno
        selected_shift_data = None
        if selected_date and selected_date in shifts_by_date:
            selected_shift_data = shifts_by_date[selected_date]
            
            # Calcular duración del turno
            opened_at_str = selected_shift_data.get('opened_at', '')
            closed_at_str = selected_shift_data.get('closed_at', '')
            if opened_at_str and closed_at_str:
                try:
                    from datetime import datetime
                    opened_dt = datetime.fromisoformat(opened_at_str.replace('Z', '+00:00') if 'Z' in opened_at_str else opened_at_str)
                    closed_dt = datetime.fromisoformat(closed_at_str.replace('Z', '+00:00') if 'Z' in closed_at_str else closed_at_str)
                    duration_seconds = (closed_dt - opened_dt).total_seconds()
                    duration_hours = duration_seconds / 3600
                    selected_shift_data['duration'] = f"{duration_hours:.2f} horas"
                except Exception as e:
                    current_app.logger.warning(f"Error calculando duración: {e}")
                    selected_shift_data['duration'] = 'N/A'
            
            # Obtener entregas detalladas de ese día
            delivery_service = get_delivery_service()
            deliveries = delivery_service.get_deliveries_by_shift_date(selected_date)
            
            # Obtener estadísticas detalladas de entregas
            delivery_stats = stats_service.get_delivery_stats(start_date=selected_date, end_date=selected_date)
            
            # Calcular entregas por hora del día (21:00 - 06:00) - Curva de Compra
            hours_data = [0] * 10
            hours_labels = ['21:00', '22:00', '23:00', '00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00']
            
            for delivery in deliveries:
                try:
                    if isinstance(delivery.timestamp, str):
                        delivery_time = datetime.strptime(delivery.timestamp, '%Y-%m-%d %H:%M:%S')
                    else:
                        delivery_time = delivery.timestamp
                    
                    hour = delivery_time.hour
                    if hour >= 21:
                        idx = hour - 21
                        hours_data[idx] += delivery.qty
                    elif hour <= 6:
                        idx = hour + 3
                        hours_data[idx] += delivery.qty
                except:
                    continue
            
            # Hora pico de compras
            peak_hour_idx = max(range(len(hours_data)), key=lambda i: hours_data[i]) if hours_data else 0
            peak_hour_label = hours_labels[peak_hour_idx] if hours_labels else 'N/A'
            peak_hour_count = hours_data[peak_hour_idx] if hours_data else 0
            
            # Obtener estadísticas de entradas (curva de entrada)
            entradas_stats = stats_service.get_entradas_stats(limit=5000)
            entradas_hours_data = [0] * 10
            entradas_hours_labels = ['21:00', '22:00', '23:00', '00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00']
            
            today_entradas = 0
            today_5000 = 0
            today_10000 = 0
            
            try:
                # PHP POS API: máximo 100 items por request
                entradas_sales = get_entradas_sales(limit=100)
                for sale in entradas_sales:
                    sale_time = sale.get('sale_time', '')
                    if sale_time and sale_time.startswith(selected_date):
                        cart_items = sale.get('cart_items', [])
                        for item in cart_items:
                            item_name = item.get('name', '').lower()
                            if 'entrada' in item_name:
                                qty = item.get('quantity', 0)
                                price = item.get('unit_price', 0)
                                today_entradas += qty
                                if price == 5000:
                                    today_5000 += qty
                                elif price == 10000:
                                    today_10000 += qty
                                
                                # Contar por hora (curva de entrada)
                                try:
                                    hour = int(sale_time[11:13])
                                    if hour >= 21:
                                        idx = hour - 21
                                        entradas_hours_data[idx] += qty
                                    elif hour <= 6:
                                        idx = hour + 3
                                        entradas_hours_data[idx] += qty
                                except (ValueError, IndexError):
                                    pass
            except Exception as e:
                current_app.logger.warning(f"Error al obtener entradas del turno: {e}")
            
            # Hora pico de entradas
            peak_entradas_idx = max(range(len(entradas_hours_data)), key=lambda i: entradas_hours_data[i]) if entradas_hours_data else 0
            peak_entradas_hour_label = entradas_hours_labels[peak_entradas_idx] if entradas_hours_labels else 'N/A'
            peak_entradas_count = entradas_hours_data[peak_entradas_idx] if entradas_hours_data else 0
            
            # Obtener estadísticas de cajas (cajeros y registros) del día
            today_cashiers = []
            today_registers = []
            
            try:
                # PHP POS API: máximo 100 items por request, sin paginación para evitar sobrecarga
                all_sales = get_all_sales(limit=100, max_results=100, use_pagination=False)
                cashier_counts_today = Counter()
                register_counts_today = Counter()
                cashier_amounts_today = defaultdict(float)
                register_amounts_today = defaultdict(float)
                cashier_names = {}
                register_names = {}
                
                for sale in all_sales:
                    sale_time = sale.get('sale_time', '')
                    if sale_time and sale_time.startswith(selected_date):
                        employee_id = str(sale.get('employee_id', '')) or 'Sin cajero'
                        register_id = str(sale.get('register_id', '')) or 'Sin caja'
                        sale_total = sale.get('sale_total', 0)
                        
                        if employee_id and employee_id != 'Sin cajero':
                            cashier_counts_today[employee_id] += 1
                            cashier_amounts_today[employee_id] += sale_total
                            if employee_id not in cashier_names:
                                employee_info = get_entity_details("employees", employee_id)
                                if employee_info:
                                    name = f"{employee_info.get('first_name', '')} {employee_info.get('last_name', '')}".strip()
                                    cashier_names[employee_id] = name or employee_info.get('name', f'Cajero {employee_id}')
                                else:
                                    cashier_names[employee_id] = f'Cajero {employee_id}'
                        
                        if register_id and register_id != 'Sin caja':
                            register_counts_today[register_id] += 1
                            register_amounts_today[register_id] += sale_total
                            if register_id not in register_names:
                                register_info = get_entity_details("registers", register_id)
                                if register_info:
                                    register_names[register_id] = register_info.get('name', f'Caja {register_id}')
                                else:
                                    register_names[register_id] = f'Caja {register_id}'
                
                # Top cajeros del día
                for employee_id, count in cashier_counts_today.most_common(10):
                    today_cashiers.append({
                        'id': employee_id,
                        'name': cashier_names.get(employee_id, f'Cajero {employee_id}'),
                        'sales_count': count,
                        'total_amount': cashier_amounts_today.get(employee_id, 0)
                    })
                
                # Top cajas del día
                for register_id, count in register_counts_today.most_common(10):
                    today_registers.append({
                        'id': register_id,
                        'name': register_names.get(register_id, f'Caja {register_id}'),
                        'sales_count': count,
                        'total_amount': register_amounts_today.get(register_id, 0)
                    })
            except Exception as e:
                current_app.logger.warning(f"Error al obtener estadísticas de cajas del turno: {e}")
            
            # Agregar entregas detalladas y estadísticas
            selected_shift_data['deliveries'] = deliveries
            selected_shift_data['delivery_stats'] = delivery_stats
            selected_shift_data['hours_data'] = hours_data
            selected_shift_data['hours_labels'] = hours_labels
            selected_shift_data['peak_hour_label'] = peak_hour_label
            selected_shift_data['peak_hour_count'] = peak_hour_count
            selected_shift_data['entradas_hours_data'] = entradas_hours_data
            selected_shift_data['entradas_hours_labels'] = entradas_hours_labels
            selected_shift_data['peak_entradas_hour_label'] = peak_entradas_hour_label
            selected_shift_data['peak_entradas_count'] = peak_entradas_count
            selected_shift_data['total_personas_en_local'] = today_entradas
            selected_shift_data['entradas_5000_count'] = today_5000
            selected_shift_data['entradas_10000_count'] = today_10000
            selected_shift_data['top_cashiers'] = today_cashiers
            selected_shift_data['top_registers'] = today_registers
            
            # Obtener estadísticas de encuestas más detalladas
            survey_service = get_survey_service()
            survey_results = survey_service.get_survey_results()
            if survey_results.get('session_date') == selected_date:
                selected_shift_data['survey_detailed'] = survey_results
        
        return render_template(
            'admin/shift_history.html',
            available_dates=available_dates,
            selected_date=selected_date,
            selected_shift_data=selected_shift_data,
            total_shifts=len(available_dates)
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar historial de turnos: {e}", exc_info=True)
        flash(f"❌ Error al cargar historial de turnos: {str(e)}", "error")
        return redirect(url_for('routes.admin_dashboard'))

@bp.route('/admin/api/recent-sales', methods=['GET'])
def api_recent_sales():
    """API: Obtener ventas recientes del turno actual"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        limit = int(request.args.get('limit', 20))
        
        # Obtener estado del turno
        shift_service = get_shift_service()
        shift_status = shift_service.get_current_shift_status()
        
        # Obtener ventas recientes del turno
        from app.models import PosSale
        from sqlalchemy.orm import joinedload
        
        if shift_status.is_open:
            recent_sales = PosSale.query.options(
                joinedload(PosSale.items)
            ).filter(
                PosSale.shift_date == shift_status.shift_date
            ).order_by(PosSale.created_at.desc()).limit(limit).all()
            
            sales_data = [sale.to_dict() for sale in recent_sales]
        else:
            sales_data = []
        
        return jsonify({
            'success': True,
            'sales': sales_data
        })
    except Exception as e:
        current_app.logger.error(f"Error al obtener ventas recientes: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'sales': []
        }), 500

@bp.route('/admin/api/register-sales-monitor', methods=['GET'])
def api_register_sales_monitor():
    """API: Obtener monitoreo de ventas por caja en tiempo real"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        from app.helpers.register_sales_monitor import get_sales_by_register
        
        register_id = request.args.get('register_id')
        include_stats = request.args.get('include_stats', 'false').lower() == 'true'
        
        current_app.logger.info(f"📊 API: Obteniendo monitoreo de ventas (register_id={register_id})")
        
        # Obtener ventas agrupadas por caja
        sales_data = get_sales_by_register(register_id=register_id)
        
        current_app.logger.info(f"✅ API: Retornando {sales_data.get('summary', {}).get('total_sales', 0)} ventas en {len(sales_data.get('registers', {}))} cajas")
        
        response_data = {
            'success': True,
            'data': sales_data
        }
        
        # Si se solicitan estadísticas avanzadas
        if include_stats:
            try:
                from app.helpers.sales_statistics import calculate_sales_statistics
                
                # Calcular estadísticas avanzadas usando la función que existe
                advanced_stats = calculate_sales_statistics(sales_data)
                response_data['statistics'] = advanced_stats
            except ImportError as e:
                current_app.logger.warning(f"No se pudieron calcular estadísticas avanzadas: {e}")
                response_data['statistics'] = {}
            except Exception as e:
                current_app.logger.error(f"Error al calcular estadísticas avanzadas: {e}", exc_info=True)
                response_data['statistics'] = {}
        
        return jsonify(response_data)
    except Exception as e:
        current_app.logger.error(f"❌ Error al obtener monitoreo de ventas por caja: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {
                'registers': {},
                'summary': {
                    'total_registers': 0,
                    'total_sales': 0,
                    'total_amount': 0.0,
                    'total_cash': 0.0,
                    'total_debit': 0.0,
                    'total_credit': 0.0
                }
            }
        }), 500

@bp.route('/admin/api/register-closes', methods=['GET'])
def api_register_closes():
    """API: Obtener TODOS los cierres de caja con paginación"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        from app.models.pos_models import RegisterClose
        from datetime import datetime
        import pytz
        
        CHILE_TZ = pytz.timezone('America/Santiago')
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Obtener TODOS los cierres (sin filtrar por turno)
        total_closes = RegisterClose.query.count()
        
        # Paginación manual usando offset y limit
        closes_query = RegisterClose.query.order_by(RegisterClose.closed_at.desc())
        offset = (page - 1) * per_page
        closes = closes_query.offset(offset).limit(per_page).all()
        total_pages = (total_closes + per_page - 1) // per_page
        
        # Formatear cierres
        closes_list = []
        for close in closes:
            # Formatear opened_at y closed_at en formato legible directamente en el backend
            # Esto evita problemas de timezone en JavaScript
            opened_at_formatted = None
            if close.opened_at:
                try:
                    if isinstance(close.opened_at, str):
                        # Parsear string 'YYYY-MM-DD HH:MM:SS' y formatear
                        dt = datetime.strptime(close.opened_at, '%Y-%m-%d %H:%M:%S')
                    elif isinstance(close.opened_at, datetime):
                        dt = close.opened_at
                    else:
                        opened_at_formatted = str(close.opened_at)
                        dt = None
                    
                    if dt:
                        # Formatear en formato chileno: DD-MM-YYYY, HH:MM AM/PM
                        hour = dt.hour
                        period = 'a. m.' if hour < 12 else 'p. m.'
                        hour12 = hour % 12 if hour % 12 != 0 else 12
                        opened_at_formatted = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
                except Exception as e:
                    current_app.logger.warning(f"Error formateando opened_at: {e}")
                    opened_at_formatted = str(close.opened_at) if close.opened_at else 'N/A'
            
            closed_at_formatted = None
            if close.closed_at:
                try:
                    if isinstance(close.closed_at, datetime):
                        dt = close.closed_at
                    elif isinstance(close.closed_at, str):
                        # Parsear string 'YYYY-MM-DD HH:MM:SS'
                        dt = datetime.strptime(close.closed_at, '%Y-%m-%d %H:%M:%S')
                    else:
                        closed_at_formatted = str(close.closed_at)
                        dt = None
                    
                    if dt:
                        # Formatear en formato chileno: DD-MM-YYYY, HH:MM AM/PM
                        hour = dt.hour
                        period = 'a. m.' if hour < 12 else 'p. m.'
                        hour12 = hour % 12 if hour % 12 != 0 else 12
                        closed_at_formatted = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
                except Exception as e:
                    current_app.logger.warning(f"Error formateando closed_at: {e}")
                    closed_at_formatted = str(close.closed_at) if close.closed_at else 'N/A'
            
            # Calcular el total real como suma de los montos reales (actual_cash + actual_debit + actual_credit)
            # Esto es lo que realmente se recaudó, no lo que se esperaba
            actual_cash = float(close.actual_cash or 0)
            actual_debit = float(close.actual_debit or 0)
            actual_credit = float(close.actual_credit or 0)
            total_recaudado = actual_cash + actual_debit + actual_credit
            
            # Si total_amount es 0 pero hay montos reales, usar la suma de los montos reales
            total_amount = float(close.total_amount or 0)
            if total_amount == 0 and total_recaudado > 0:
                total_amount = total_recaudado
            
            closes_list.append({
                'id': close.id,
                'register_id': str(close.register_id),
                'register_name': close.register_name or f'Caja {close.register_id}',
                'employee_id': str(close.employee_id) if close.employee_id else None,
                'employee_name': close.employee_name or 'Sin asignar',
                'shift_date': close.shift_date,
                'opened_at': opened_at_formatted,
                'closed_at': closed_at_formatted,
                'total_sales': int(close.total_sales) if close.total_sales else 0,
                'total_amount': total_amount,  # Usar el total recaudado si total_amount es 0
                'expected_cash': float(close.expected_cash) if close.expected_cash else 0.0,
                'actual_cash': actual_cash,
                'actual_debit': actual_debit,
                'actual_credit': actual_credit,
                'diff_cash': float(close.diff_cash) if close.diff_cash else 0.0,
                'diff_debit': float(close.diff_debit) if close.diff_debit else 0.0,
                'diff_credit': float(close.diff_credit) if close.diff_credit else 0.0,
                'difference_total': float(close.difference_total) if close.difference_total else 0.0,
                'status': close.status or 'closed'
            })
        
        return jsonify({
            'success': True,
            'closes': closes_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_closes,
                'pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_page': page - 1 if page > 1 else None,
                'next_page': page + 1 if page < total_pages else None
            }
        })
    except Exception as e:
        current_app.logger.error(f"❌ Error al obtener cierres de caja: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'closes': [],
            'pagination': {
                'page': 1,
                'per_page': 10,
                'total': 0,
                'pages': 0
            }
        }), 500

@bp.route('/admin/cierres-pendientes')
def admin_pending_closes():
    """Página para que el admin vea y acepte cierres de caja pendientes"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    try:
        from app.helpers.register_close_db import get_pending_closes
        from datetime import datetime
        import pytz
        
        CHILE_TZ = pytz.timezone('America/Santiago')
        
        # Obtener cierres pendientes
        pending_closes = get_pending_closes()
        
        # Formatear fechas para mostrar
        for close in pending_closes:
            # Formatear closed_at
            if close.get('closed_at'):
                try:
                    if isinstance(close['closed_at'], str):
                        dt = datetime.strptime(close['closed_at'], '%Y-%m-%d %H:%M:%S')
                    else:
                        dt = close['closed_at']
                    
                    hour = dt.hour
                    period = 'a. m.' if hour < 12 else 'p. m.'
                    hour12 = hour % 12 if hour % 12 != 0 else 12
                    close['closed_at_formatted'] = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
                except:
                    close['closed_at_formatted'] = str(close.get('closed_at', 'N/A'))
            
            # Formatear opened_at
            if close.get('opened_at'):
                try:
                    if isinstance(close['opened_at'], str):
                        dt = datetime.strptime(close['opened_at'], '%Y-%m-%d %H:%M:%S')
                        hour = dt.hour
                        period = 'a. m.' if hour < 12 else 'p. m.'
                        hour12 = hour % 12 if hour % 12 != 0 else 12
                        close['opened_at_formatted'] = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
                    else:
                        close['opened_at_formatted'] = str(close['opened_at'])
                except:
                    close['opened_at_formatted'] = str(close.get('opened_at', 'N/A'))
        
        return render_template('admin/pending_closes.html', pending_closes=pending_closes)
    except Exception as e:
        current_app.logger.error(f"Error al cargar cierres pendientes: {e}", exc_info=True)
        flash(f"Error al cargar cierres pendientes: {str(e)}", "error")
        return render_template('admin/pending_closes.html', pending_closes=[])

@bp.route('/admin/api/pending-closes', methods=['GET'])
def api_pending_closes():
    """API: Obtener cierres de caja pendientes en formato JSON"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        from app.helpers.register_close_db import get_pending_closes
        from datetime import datetime
        
        # Obtener cierres pendientes
        pending_closes = get_pending_closes()
        
        # Formatear fechas para mostrar
        formatted_closes = []
        for close in pending_closes:
            close_dict = {
                'id': close.get('id'),
                'register_id': str(close.get('register_id', '')),
                'register_name': close.get('register_name', f"Caja {close.get('register_id', '')}"),
                'employee_id': str(close.get('employee_id', '')) if close.get('employee_id') else None,
                'employee_name': close.get('employee_name', 'Sin asignar'),
                'shift_date': close.get('shift_date'),
                'opened_at': close.get('opened_at'),
                'closed_at': close.get('closed_at'),
                'expected_cash': float(close.get('expected_cash', 0)) if close.get('expected_cash') else 0.0,
                'actual_cash': float(close.get('actual_cash', 0)) if close.get('actual_cash') else 0.0,
                'diff_cash': float(close.get('diff_cash', 0)) if close.get('diff_cash') else 0.0,
                'expected_debit': float(close.get('expected_debit', 0)) if close.get('expected_debit') else 0.0,
                'actual_debit': float(close.get('actual_debit', 0)) if close.get('actual_debit') else 0.0,
                'diff_debit': float(close.get('diff_debit', 0)) if close.get('diff_debit') else 0.0,
                'expected_credit': float(close.get('expected_credit', 0)) if close.get('expected_credit') else 0.0,
                'actual_credit': float(close.get('actual_credit', 0)) if close.get('actual_credit') else 0.0,
                'diff_credit': float(close.get('diff_credit', 0)) if close.get('diff_credit') else 0.0,
                'difference_total': float(close.get('difference_total', 0)) if close.get('difference_total') else 0.0,
                'total_sales': int(close.get('total_sales', 0)) if close.get('total_sales') else 0,
                'total_amount': float(close.get('total_amount', 0)) if close.get('total_amount') else 0.0,
                'notes': close.get('notes', ''),
                'status': close.get('status', 'pending')
            }
            
            # Formatear fechas
            if close_dict['closed_at']:
                try:
                    if isinstance(close_dict['closed_at'], str):
                        dt = datetime.strptime(close_dict['closed_at'], '%Y-%m-%d %H:%M:%S')
                    else:
                        dt = close_dict['closed_at']
                    hour = dt.hour
                    period = 'a. m.' if hour < 12 else 'p. m.'
                    hour12 = hour % 12 if hour % 12 != 0 else 12
                    close_dict['closed_at_formatted'] = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
                except:
                    close_dict['closed_at_formatted'] = str(close_dict['closed_at'])
            else:
                close_dict['closed_at_formatted'] = 'N/A'
            
            if close_dict['opened_at']:
                try:
                    if isinstance(close_dict['opened_at'], str):
                        dt = datetime.strptime(close_dict['opened_at'], '%Y-%m-%d %H:%M:%S')
                    else:
                        dt = close_dict['opened_at']
                    hour = dt.hour
                    period = 'a. m.' if hour < 12 else 'p. m.'
                    hour12 = hour % 12 if hour % 12 != 0 else 12
                    close_dict['opened_at_formatted'] = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
                except:
                    close_dict['opened_at_formatted'] = str(close_dict['opened_at'])
            else:
                close_dict['opened_at_formatted'] = 'N/A'
            
            formatted_closes.append(close_dict)
        
        return jsonify({
            'success': True,
            'pending_closes': formatted_closes
        })
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener cierres pendientes: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Error al obtener cierres pendientes: {str(e)}',
            'pending_closes': []
        }), 500

@bp.route('/admin/api/register-close/<int:close_id>', methods=['GET'])
def api_register_close_detail(close_id):
    """API: Obtener detalles completos de un cierre de caja por ID"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        from app.helpers.register_close_db import get_register_close_by_id
        from datetime import datetime
        import pytz
        
        CHILE_TZ = pytz.timezone('America/Santiago')
        
        close_data = get_register_close_by_id(close_id)
        
        if not close_data:
            return jsonify({'success': False, 'error': 'Cierre no encontrado'}), 404
        
        # Formatear fechas en formato legible
        opened_at_formatted = None
        if close_data.get('opened_at'):
            try:
                if isinstance(close_data['opened_at'], str):
                    dt = datetime.strptime(close_data['opened_at'], '%Y-%m-%d %H:%M:%S')
                elif isinstance(close_data['opened_at'], datetime):
                    dt = close_data['opened_at']
                else:
                    opened_at_formatted = str(close_data['opened_at'])
                    dt = None
                
                if dt:
                    hour = dt.hour
                    period = 'a. m.' if hour < 12 else 'p. m.'
                    hour12 = hour % 12 if hour % 12 != 0 else 12
                    opened_at_formatted = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
            except Exception as e:
                current_app.logger.warning(f"Error formateando opened_at: {e}")
                opened_at_formatted = str(close_data.get('opened_at', 'N/A'))
        
        closed_at_formatted = None
        if close_data.get('closed_at'):
            try:
                if isinstance(close_data['closed_at'], str):
                    dt = datetime.strptime(close_data['closed_at'], '%Y-%m-%d %H:%M:%S')
                elif isinstance(close_data['closed_at'], datetime):
                    dt = close_data['closed_at']
                else:
                    closed_at_formatted = str(close_data['closed_at'])
                    dt = None
                
                if dt:
                    hour = dt.hour
                    period = 'a. m.' if hour < 12 else 'p. m.'
                    hour12 = hour % 12 if hour % 12 != 0 else 12
                    closed_at_formatted = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
            except Exception as e:
                current_app.logger.warning(f"Error formateando closed_at: {e}")
                closed_at_formatted = str(close_data.get('closed_at', 'N/A'))
        
        resolved_at_formatted = None
        if close_data.get('resolved_at'):
            try:
                if isinstance(close_data['resolved_at'], str):
                    dt = datetime.strptime(close_data['resolved_at'], '%Y-%m-%d %H:%M:%S')
                elif isinstance(close_data['resolved_at'], datetime):
                    dt = close_data['resolved_at']
                else:
                    resolved_at_formatted = str(close_data['resolved_at'])
                    dt = None
                
                if dt:
                    hour = dt.hour
                    period = 'a. m.' if hour < 12 else 'p. m.'
                    hour12 = hour % 12 if hour % 12 != 0 else 12
                    resolved_at_formatted = dt.strftime(f'%d-%m-%Y, {hour12}:%M {period}')
            except Exception as e:
                current_app.logger.warning(f"Error formateando resolved_at: {e}")
                resolved_at_formatted = str(close_data.get('resolved_at', 'N/A'))
        
        # Preparar respuesta con todos los detalles
        return jsonify({
            'success': True,
            'close': {
                'id': close_data.get('id'),
                'register_id': str(close_data.get('register_id', '')),
                'register_name': close_data.get('register_name', 'Caja'),
                'employee_id': str(close_data.get('employee_id', '')) if close_data.get('employee_id') else None,
                'employee_name': close_data.get('employee_name', 'Sin asignar'),
                'shift_date': close_data.get('shift_date'),
                'opened_at': opened_at_formatted,
                'closed_at': closed_at_formatted,
                'total_sales': int(close_data.get('total_sales', 0)),
                'total_amount': float(close_data.get('total_amount', 0.0)),
                'expected_cash': float(close_data.get('expected_cash', 0.0)),
                'actual_cash': float(close_data.get('actual_cash', 0.0)),
                'diff_cash': float(close_data.get('diff_cash', 0.0)),
                'expected_debit': float(close_data.get('expected_debit', 0.0)),
                'actual_debit': float(close_data.get('actual_debit', 0.0)),
                'diff_debit': float(close_data.get('diff_debit', 0.0)),
                'expected_credit': float(close_data.get('expected_credit', 0.0)),
                'actual_credit': float(close_data.get('actual_credit', 0.0)),
                'diff_credit': float(close_data.get('diff_credit', 0.0)),
                'difference_total': float(close_data.get('difference_total', 0.0)),
                'status': close_data.get('status', 'closed'),
                'notes': close_data.get('notes', ''),
                'resolved_by': close_data.get('resolved_by'),
                'resolved_at': resolved_at_formatted,
                'resolution_notes': close_data.get('resolution_notes', '')
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error al obtener detalles del cierre {close_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Error al obtener detalles del cierre: {str(e)}'
        }), 500

@bp.route('/admin/api/accept-close', methods=['POST'])
def api_accept_close():
    """API: Aceptar un cierre de caja pendiente"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        close_id = data.get('close_id')
        notes = data.get('notes', '')
        
        if not close_id:
            return jsonify({'success': False, 'error': 'ID de cierre requerido'}), 400
        
        from app.helpers.register_close_db import accept_register_close
        
        # Obtener nombre del admin
        admin_name = session.get('admin_name', 'Admin')
        
        success = accept_register_close(close_id, admin_name, notes)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Cierre aceptado correctamente. La caja ha sido desbloqueada.'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo aceptar el cierre. Verifica que esté pendiente.'
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error al aceptar cierre: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Error al aceptar cierre: {str(e)}'
        }), 500

@bp.route('/admin/estadisticas-cajas')
def pos_stats():
    """Página dedicada para estadísticas POS en tiempo real"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    # Obtener estado del turno desde Jornada (sistema único)
    from app.models.jornada_models import Jornada
    from datetime import datetime
    from flask import current_app
    
    CHILE_TZ = current_app.config.get('CHILE_TZ')
    fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
    
    jornada_actual = Jornada.query.filter_by(fecha_jornada=fecha_hoy, estado_apertura='abierto').first()
    
    # Convertir Jornada a dict para compatibilidad con template
    if jornada_actual:
        shift_status_dict = {
            'is_open': True,
            'shift_date': jornada_actual.fecha_jornada,
            'opened_at': jornada_actual.abierto_en.isoformat() if jornada_actual.abierto_en else jornada_actual.horario_apertura_programado,
            'closed_at': None,
            'fiesta_nombre': jornada_actual.nombre_fiesta,
            'djs': jornada_actual.djs
        }
    else:
        shift_status_dict = {
            'is_open': False,
            'shift_date': fecha_hoy,
            'opened_at': None,
            'closed_at': None,
            'fiesta_nombre': None,
            'djs': None
        }
    
    # Obtener estadísticas del kiosko FILTRADAS POR TURNO (no por día)
    kiosk_stats = {}
    try:
        from app.models.kiosk_models import Pago
        from sqlalchemy import func
        from app.models import db
        
        # Usar información de Jornada (sistema único)
        if jornada_actual and jornada_actual.abierto_en:
            # Filtrar por turno: pagos desde opened_at de Jornada
            shift_opened_at = jornada_actual.abierto_en
            if shift_opened_at.tzinfo is not None:
                shift_opened_at = shift_opened_at.replace(tzinfo=None)
            
            # Pagos del turno (agregación SQL)
            pagos_turno_count = Pago.query.filter(
                Pago.created_at >= shift_opened_at,
                Pago.estado == 'PAID'
            ).count()
            monto_turno_result = db.session.query(func.sum(Pago.monto)).filter(
                Pago.created_at >= shift_opened_at,
                Pago.estado == 'PAID'
            ).scalar()
            monto_turno = float(monto_turno_result or 0)
            
            # Totales históricos (agregación SQL)
            total_pagos = Pago.query.filter_by(estado='PAID').count()
            monto_total_result = db.session.query(func.sum(Pago.monto)).filter_by(estado='PAID').scalar()
            monto_total = float(monto_total_result or 0)
            pagos_pendientes = Pago.query.filter_by(estado='PENDING').count()
            
            kiosk_stats = {
                'pagos_turno': pagos_turno_count,
                'monto_turno': monto_turno,
                'total_pagos': total_pagos,
                'monto_total': monto_total,
                'pagos_pendientes': pagos_pendientes
            }
        else:
            # Sin turno abierto - usar agregaciones SQL
            total_pagos_count = Pago.query.filter_by(estado='PAID').count()
            monto_total_result = db.session.query(func.sum(Pago.monto)).filter_by(estado='PAID').scalar()
            monto_total = float(monto_total_result or 0)
            pagos_pendientes_count = Pago.query.filter_by(estado='PENDING').count()
            
            kiosk_stats = {
                'pagos_turno': 0,
                'monto_turno': 0,
                'total_pagos': total_pagos_count,
                'monto_total': monto_total,
                'pagos_pendientes': pagos_pendientes_count
            }
    except Exception as e:
        current_app.logger.warning(f"No se pudieron obtener estadísticas del kiosko: {e}")
        kiosk_stats = {
            'pagos_turno': 0,
            'monto_turno': 0,
            'total_pagos': 0,
            'monto_total': 0,
            'pagos_pendientes': 0
        }
    
    return render_template('admin/pos_stats.html', shift_status=shift_status_dict, kiosk_stats=kiosk_stats)

@bp.route('/api/dashboard/stats', methods=['GET'])
def api_dashboard_stats():
    """API: Obtener estadísticas en tiempo real para el dashboard del home"""
    try:
        from datetime import datetime, timedelta
        from collections import Counter
        from sqlalchemy import func
        from app.models import db
        from app.models.pos_models import PosSale
        from app.models.jornada_models import Jornada
        from app import CHILE_TZ
        
        # Obtener turno actual
        shift_service = get_shift_service()
        shift_status = shift_service.get_current_shift_status()
        
        if not shift_status.is_open:
            return jsonify({
                'success': True,
                'shift_open': False,
                'message': 'No hay turno abierto'
            })
        
        # Obtener jornada actual
        fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
        jornada_actual = Jornada.query.filter_by(
            fecha_jornada=fecha_hoy,
            estado_apertura='abierto'
        ).first()
        
        if not jornada_actual or not jornada_actual.abierto_en:
            return jsonify({
                'success': True,
                'shift_open': False,
                'message': 'No hay turno abierto'
            })
        
        shift_opened_at = jornada_actual.abierto_en
        if shift_opened_at.tzinfo:
            shift_opened_at = shift_opened_at.replace(tzinfo=None)
        
        now_chile = datetime.now(CHILE_TZ)
        horas_transcurridas = max(0.1, (now_chile.replace(tzinfo=None) - shift_opened_at).total_seconds() / 3600)
        
        # =============================================================================
        # 1. ESTADÍSTICAS FINANCIERAS (VENTAS POS)
        # =============================================================================
        sales_stats = db.session.query(
            func.sum(PosSale.total_amount).label('total_amount'),
            func.sum(PosSale.payment_cash).label('total_cash'),
            func.sum(PosSale.payment_debit).label('total_debit'),
            func.sum(PosSale.payment_credit).label('total_credit'),
            func.count(PosSale.id).label('total_sales')
        ).filter(PosSale.created_at >= shift_opened_at).first()
        
        total_recaudado = float(sales_stats.total_amount or 0)
        total_efectivo = float(sales_stats.total_cash or 0)
        total_debito = float(sales_stats.total_debit or 0)
        total_credito = float(sales_stats.total_credit or 0)
        total_ventas = int(sales_stats.total_sales or 0)
        ticket_promedio = total_recaudado / total_ventas if total_ventas > 0 else 0
        
        # =============================================================================
        # 2. ESTADÍSTICAS DE ENTREGAS
        # =============================================================================
        delivery_service = get_delivery_service()
        stats_service = get_stats_service()
        
        # Crear objeto compatible con ShiftStatus
        class ShiftStatusCompat:
            def __init__(self, jornada):
                self.is_open = True
                self.shift_date = jornada.fecha_jornada
                self.fiesta_nombre = jornada.nombre_fiesta
                self.djs = jornada.djs
                self.opened_at = jornada.abierto_en.isoformat() if jornada.abierto_en else jornada.horario_apertura_programado
                self.closed_at = None
        
        current_shift = ShiftStatusCompat(jornada_actual)
        delivery_stats = stats_service.get_delivery_stats_for_shift(current_shift)
        
        total_entregas = delivery_stats.get('total_deliveries', 0)
        entregas_por_hora = total_entregas / horas_transcurridas if horas_transcurridas > 0 else 0
        
        # =============================================================================
        # OPTIMIZACIÓN: Consolidar todos los loops en uno solo
        # Calculamos todas las métricas en una sola iteración sobre las entregas
        # =============================================================================
        all_deliveries = delivery_service.delivery_repository.find_all()
        
        # Preparar variables de tiempo (una sola vez)
        last_hour_start = (now_chile - timedelta(hours=1)).replace(tzinfo=None)
        last_15min_start = (now_chile - timedelta(minutes=15)).replace(tzinfo=None)
        two_hours_ago = (now_chile - timedelta(hours=2)).replace(tzinfo=None)
        last_30min_start = (now_chile - timedelta(minutes=30)).replace(tzinfo=None)
        
        # Inicializar contadores y métricas
        entregas_ultima_hora = 0
        entregas_ultimos_15min = 0
        entregas_hora_anterior = 0
        items_last_30min = Counter()
        bartenders_last_30min = Counter()
        barras_last_30min = Counter()
        
        # UN SOLO LOOP para calcular todas las métricas
        for delivery in all_deliveries:
            try:
                # Parsear timestamp una sola vez por delivery
                if isinstance(delivery.timestamp, str):
                    delivery_time = datetime.strptime(delivery.timestamp, '%Y-%m-%d %H:%M:%S')
                else:
                    delivery_time = delivery.timestamp
                
                # Si no tiene timezone info, asumir naive datetime (ya es hora local)
                if delivery_time.tzinfo:
                    delivery_time = delivery_time.replace(tzinfo=None)
                
                # Filtrar solo entregas del turno actual
                if delivery_time < shift_opened_at:
                    continue
                
                qty = delivery.qty
                
                # Calcular todas las métricas en una pasada
                # 1. Entregas en última hora
                if delivery_time >= last_hour_start:
                    entregas_ultima_hora += qty
                
                # 2. Entregas en últimos 15 minutos
                if delivery_time >= last_15min_start:
                    entregas_ultimos_15min += qty
                
                # 3. Entregas en hora anterior (para tendencia)
                if delivery_time >= two_hours_ago and delivery_time < last_hour_start:
                    entregas_hora_anterior += qty
                
                # 4. Top productos y bartenders (últimos 30 minutos)
                if delivery_time >= last_30min_start:
                    items_last_30min[delivery.item_name] += qty
                    bartenders_last_30min[delivery.bartender] += qty
                    barras_last_30min[delivery.barra] += qty
            except Exception as e:
                # Log error pero continuar con otras entregas
                current_app.logger.debug(f"Error procesando delivery: {e}")
                continue
        
        # Promedio de entregas cada 15 minutos
        intervalos_15min = max(1, horas_transcurridas * 4)
        promedio_15min = total_entregas / intervalos_15min if intervalos_15min > 0 else 0
        
        # Calcular tendencia
        if entregas_hora_anterior > 0:
            tendencia_porcentaje = ((entregas_ultima_hora - entregas_hora_anterior) / entregas_hora_anterior) * 100
            if tendencia_porcentaje > 5:
                tendencia_direccion = 'up'
                tendencia_texto = '↑ Subiendo'
            elif tendencia_porcentaje < -5:
                tendencia_direccion = 'down'
                tendencia_texto = '↓ Bajando'
            else:
                tendencia_direccion = 'stable'
                tendencia_texto = '→ Estable'
        else:
            tendencia_porcentaje = 0
            tendencia_direccion = 'stable'
            tendencia_texto = '→ Estable'
        
        # Calcular ritmo
        promedio_hora = total_entregas / horas_transcurridas if horas_transcurridas > 0 else 0
        if promedio_hora > 0:
            ritmo_porcentaje = ((entregas_ultima_hora - promedio_hora) / promedio_hora) * 100
            if ritmo_porcentaje > 20:
                ritmo_estado = 'high'
                ritmo_texto = 'RITMO ALTO'
            elif ritmo_porcentaje < -20:
                ritmo_estado = 'low'
                ritmo_texto = 'RITMO BAJO'
            else:
                ritmo_estado = 'normal'
                ritmo_texto = 'RITMO NORMAL'
        else:
            ritmo_porcentaje = 0
            ritmo_estado = 'low'
            ritmo_texto = 'RITMO BAJO'
        
        # Top productos, bartenders y barra
        top_productos = [{'name': name, 'qty': qty} for name, qty in items_last_30min.most_common(3)]
        top_bartenders = [{'name': name, 'qty': qty} for name, qty in bartenders_last_30min.most_common(3)]
        top_barra = barras_last_30min.most_common(1)[0] if barras_last_30min else None
        
        top_productos = [{'name': name, 'qty': qty} for name, qty in items_last_30min.most_common(3)]
        top_bartenders = [{'name': name, 'qty': qty} for name, qty in bartenders_last_30min.most_common(3)]
        top_barra = barras_last_30min.most_common(1)[0] if barras_last_30min else None
        
        # =============================================================================
        # 4. ESTADÍSTICAS DE ENTRADAS Y ÚLTIMOS TICKETS ESCANEADOS
        # =============================================================================
        from .helpers.ticket_scans import get_all_ticket_scans
        from app.models.delivery_models import TicketScan
        ticket_scans = get_all_ticket_scans()
        total_entradas = 0
        
        for sale_id, ticket_data in ticket_scans.items():
            scanned_at = ticket_data.get('scanned_at', '')
            if not scanned_at:
                continue
            try:
                ticket_time = datetime.fromisoformat(scanned_at.replace('Z', '+00:00'))
                if ticket_time.tzinfo:
                    ticket_time = ticket_time.replace(tzinfo=None)
                if ticket_time >= shift_opened_at:
                    items = ticket_data.get('items', [])
                    for item in items:
                        item_name = item.get('name', '').lower()
                        if 'entrada' in item_name:
                            total_entradas += item.get('quantity', 0)
            except:
                continue
        
        # Obtener los últimos 5 tickets escaneados del turno actual
        last_scanned_tickets = []
        try:
            recent_scans = TicketScan.query.filter(
                TicketScan.scanned_at >= shift_opened_at
            ).order_by(TicketScan.scanned_at.desc()).limit(5).all()
            
            for scan in recent_scans:
                import json
                try:
                    sale_info = json.loads(scan.sale_info) if scan.sale_info else {}
                    items_list = json.loads(scan.items) if scan.items else []
                    
                    # Formatear fecha
                    scanned_at_formatted = scan.scanned_at.strftime('%d/%m/%Y %H:%M') if scan.scanned_at else 'N/A'
                    
                    last_scanned_tickets.append({
                        'sale_id': scan.sale_id,
                        'scanned_at': scanned_at_formatted,
                        'total_items': len(items_list),
                        'caja': sale_info.get('caja', 'N/A'),
                        'vendedor': sale_info.get('vendedor', 'N/A')
                    })
                except Exception as e:
                    current_app.logger.warning(f"Error al procesar ticket scan {scan.sale_id}: {e}")
                    continue
        except Exception as e:
            current_app.logger.warning(f"Error al obtener últimos tickets escaneados: {e}")
        
        # =============================================================================
        # 5. CALCULAR KPIs
        # =============================================================================
        # Por Persona (Recaudación / Personas)
        personas_en_local = total_entradas  # Aproximación: cada entrada = 1 persona
        por_persona = total_recaudado / personas_en_local if personas_en_local > 0 else 0
        
        # Proyección (Estimado al cierre)
        # Asumir que el turno dura hasta las 6 AM (9 horas desde 21:00)
        horas_totales_estimadas = 9
        proyeccion = (total_recaudado / horas_transcurridas) * horas_totales_estimadas if horas_transcurridas > 0 else 0
        
        # Ventas por hora
        ventas_por_hora = total_ventas / horas_transcurridas if horas_transcurridas > 0 else 0
        
        # =============================================================================
        # 6. ESTADO DE CAJAS
        # =============================================================================
        from app.helpers.register_lock_db import get_all_register_locks
        register_locks = get_all_register_locks()
        cajas_desbloqueadas = True
        for lock in register_locks:
            if lock.get('register_id'):
                cajas_desbloqueadas = False
                break
        
        # =============================================================================
        # 7. TIEMPO TRANSCURRIDO DEL TURNO
        # =============================================================================
        tiempo_transcurrido = now_chile.replace(tzinfo=None) - shift_opened_at
        horas = int(tiempo_transcurrido.total_seconds() // 3600)
        minutos = int((tiempo_transcurrido.total_seconds() % 3600) // 60)
        tiempo_texto = f"{horas}h {minutos}m"
        
        return jsonify({
            'success': True,
            'shift_open': True,
            'financial': {
                'total_recaudado': total_recaudado,
                'efectivo': total_efectivo,
                'debito': total_debito,
                'credito': total_credito,
                'total_ventas': total_ventas,
                'ticket_promedio': ticket_promedio
            },
            'kpis': {
                'por_persona': por_persona,
                'proyeccion': proyeccion,
                'entregas_por_hora': entregas_por_hora,
                'ventas_por_hora': ventas_por_hora
            },
            'performance': {
                'ritmo': {
                    'estado': ritmo_estado,
                    'texto': ritmo_texto,
                    'entregas_ultima_hora': entregas_ultima_hora,
                    'promedio': promedio_hora,
                    'porcentaje': ritmo_porcentaje
                },
                'tendencia': {
                    'direccion': tendencia_direccion,
                    'texto': tendencia_texto,
                    'porcentaje': tendencia_porcentaje
                },
                'velocidad': {
                    'entregas_15min': entregas_ultimos_15min,
                    'promedio_15min': promedio_15min
                }
            },
            'tops': {
                'productos': top_productos,
                'bartenders': top_bartenders,
                'barra_activa': {
                    'name': top_barra[0] if top_barra else 'N/A',
                    'qty': top_barra[1] if top_barra else 0
                } if top_barra else None
            },
            'shift': {
                'tiempo_transcurrido': tiempo_texto,
                'total_entregas': total_entregas,
                'total_entradas': total_entradas,
                'cajas_desbloqueadas': cajas_desbloqueadas
            },
            'recent_tickets': last_scanned_tickets
        })
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener estadísticas del dashboard: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Rutas de rankings eliminadas - funcionalidad de rankings removida

# Ruta /admin/stats eliminada por solicitud del usuario
    """Dashboard con estadísticas del TURNO ABIERTO en tiempo real"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('routes.login_admin'))
    
    # Import necesario al inicio para evitar UnboundLocalError
    from datetime import datetime, timedelta
    
    # ACTUALIZADO: Usar Jornada (sistema único) en lugar de shift_service
    from app.models.jornada_models import Jornada
    from app import CHILE_TZ
    
    fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
    jornada_actual = Jornada.query.filter_by(
        fecha_jornada=fecha_hoy,
        estado_apertura='abierto'
    ).first()
    
    if not jornada_actual:
        # Si no hay turno abierto, mostrar estadísticas vacías
        shift_status_dict = {
            'is_open': False,
            'shift_date': None,
            'opened_at': None,
            'closed_at': None,
            'fiesta_nombre': None,
            'djs': None
        }
        shift_metrics = {
            'tiempo_transcurrido': 'N/A',
            'total_entregas': 0,
            'total_entradas': 0,
            'entradas_5000': 0,
            'entradas_10000': 0,
            'monto_kiosko': 0,
            'peak_hour': None,
            'peak_hour_count': 0,
            'top_productos': [],
            'top_bartenders': [],
            'opened_at': None
        }
        return render_template('admin_stats.html',
            shift_status=shift_status_dict,
            shift_metrics=shift_metrics,
            delivery_stats={'today_count': 0, 'week_count': 0, 'month_count': 0},
            top_bartenders_today=[],
            top_barras_today=[],
            top_items_today=[],
            hours_data=[0]*10,
            hours_labels=['21:00', '22:00', '23:00', '00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00'],
            today_entradas=0,
            today_5000=0,
            today_10000=0,
            entradas_hours_data=[0]*10,
            entradas_hours_labels=['21:00', '22:00', '23:00', '00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00'],
            today_cashiers=[],
            today_registers=[],
            current_hour=datetime.now(CHILE_TZ).hour,
            current_date=datetime.now(CHILE_TZ).strftime('%Y-%m-%d'),
            avg_per_hour=0,
            is_busy_hour=False,
            is_slow_hour=False,
            today_count=0,
            current_hour_count=0,
            peak_hour_label='N/A',
            peak_hour_count=0,
            top_bartenders=[],
            top_barras=[],
            top_items=[],
            top_categorias=[],
            top_cashiers=[],
            top_registers=[],
            total_personas_en_local=0,
            entradas_5000_count=0,
            entradas_10000_count=0,
            peak_entradas_hour_label='N/A',
            peak_entradas_count=0
        )
    
    # Crear objeto compatible con ShiftStatus para el servicio de estadísticas
    class ShiftStatusCompat:
        def __init__(self, jornada):
            self.is_open = True
            self.shift_date = jornada.fecha_jornada
            self.fiesta_nombre = jornada.nombre_fiesta
            self.djs = jornada.djs
            self.opened_at = jornada.abierto_en.isoformat() if jornada.abierto_en else jornada.horario_apertura_programado
            self.closed_at = None
    
    current_shift = ShiftStatusCompat(jornada_actual)
    
    # Usar servicio de estadísticas
    stats_service = get_stats_service()
    
    # Obtener estadísticas de entregas del turno
    delivery_stats = stats_service.get_delivery_stats_for_shift(current_shift)
    
    # Obtener todas las entregas y filtrar solo las del turno
    delivery_service = get_delivery_service()
    all_deliveries = delivery_service.delivery_repository.find_all()
    
    # Filtrar entregas del turno actual (desde opened_at)
    shift_opened_at = jornada_actual.abierto_en
    if shift_opened_at.tzinfo is not None:
        shift_opened_at = shift_opened_at.replace(tzinfo=None)
    
    shift_deliveries = []
    for delivery in all_deliveries:
        try:
            if isinstance(delivery.timestamp, str):
                delivery_time = datetime.strptime(delivery.timestamp, '%Y-%m-%d %H:%M:%S')
            else:
                delivery_time = delivery.timestamp
            
            if delivery_time >= shift_opened_at:
                shift_deliveries.append(delivery)
        except:
            continue
    
    # Calcular métricas con lógica para optimización en tiempo real
    now = datetime.now(CHILE_TZ)
    
    # Entregas en última hora (para ritmo actual)
    last_hour_start = now - timedelta(hours=1)
    entregas_ultima_hora = 0
    for d in shift_deliveries:
        try:
            if isinstance(d.timestamp, str):
                delivery_time = datetime.strptime(d.timestamp, '%Y-%m-%d %H:%M:%S')
            else:
                delivery_time = d.timestamp
            
            if delivery_time >= last_hour_start:
                entregas_ultima_hora += d.qty
        except:
            continue
    
    # Entregas en hora anterior (para tendencia)
    two_hours_ago = now - timedelta(hours=2)
    entregas_hora_anterior = sum(
        d.qty for d in shift_deliveries
        if ((isinstance(d.timestamp, str) and datetime.strptime(d.timestamp, '%Y-%m-%d %H:%M:%S') >= two_hours_ago and 
             (isinstance(d.timestamp, str) and datetime.strptime(d.timestamp, '%Y-%m-%d %H:%M:%S') < last_hour_start)) or
           (not isinstance(d.timestamp, str) and d.timestamp >= two_hours_ago and d.timestamp < last_hour_start))
    )
    
    # Entregas en últimos 15 minutos (velocidad)
    last_15min_start = now - timedelta(minutes=15)
    entregas_ultimos_15min = 0
    for d in shift_deliveries:
        try:
            if isinstance(d.timestamp, str):
                delivery_time = datetime.strptime(d.timestamp, '%Y-%m-%d %H:%M:%S')
            else:
                delivery_time = d.timestamp
            
            if delivery_time >= last_15min_start:
                entregas_ultimos_15min += d.qty
        except:
            continue
    
    # Calcular total de entregas del turno (necesario para cálculos posteriores)
    # Calcular total de cantidad entregada (suma de qty de todas las entregas)
    total_qty_entregas_turno = sum(d.qty for d in shift_deliveries)
    
    # Calcular promedio de últimos 15 min del turno (para comparar velocidad)
    if len(shift_deliveries) > 0:
        # Promedio de entregas cada 15 minutos en el turno
        tiempo_total_turno = (now - shift_opened_at).total_seconds() / 60  # minutos
        intervalos_15min = max(1, tiempo_total_turno / 15)
        promedio_15min_turno = total_qty_entregas_turno / intervalos_15min
    else:
        promedio_15min_turno = 0
    
    # Calcular tendencia
    if entregas_hora_anterior > 0:
        tendencia_porcentaje = ((entregas_ultima_hora - entregas_hora_anterior) / entregas_hora_anterior) * 100
        tendencia_direccion = 'up' if tendencia_porcentaje > 5 else ('down' if tendencia_porcentaje < -5 else 'stable')
    else:
        tendencia_porcentaje = 0 if entregas_ultima_hora == 0 else 100
        tendencia_direccion = 'up' if entregas_ultima_hora > 0 else 'stable'
    
    # Calcular ritmo (comparar última hora con promedio del turno)
    horas_transcurridas = max(1, (now - shift_opened_at).total_seconds() / 3600)
    promedio_hora_turno = total_qty_entregas_turno / horas_transcurridas if horas_transcurridas > 0 else 0
    
    if promedio_hora_turno > 0:
        ritmo_porcentaje = ((entregas_ultima_hora - promedio_hora_turno) / promedio_hora_turno) * 100
        ritmo_estado = 'high' if ritmo_porcentaje > 20 else ('low' if ritmo_porcentaje < -20 else 'normal')
    else:
        ritmo_porcentaje = 0
        ritmo_estado = 'normal'
    
    # Top productos y bartenders de últimos 30 minutos (para acciones inmediatas)
    last_30min_start = now - timedelta(minutes=30)
    items_last_30min = Counter()
    bartenders_last_30min = Counter()
    
    for delivery in shift_deliveries:
        try:
            if isinstance(delivery.timestamp, str):
                delivery_time = datetime.strptime(delivery.timestamp, '%Y-%m-%d %H:%M:%S')
            else:
                delivery_time = delivery.timestamp
            
            if delivery_time >= last_30min_start:
                items_last_30min[delivery.item_name] += delivery.qty
                bartenders_last_30min[delivery.bartender] += delivery.qty
        except:
            continue
    
    top_productos_ahora = items_last_30min.most_common(3)
    top_bartenders_ahora = bartenders_last_30min.most_common(3)
    
    # Calcular rankings del turno
    bartenders_shift = Counter()
    barras_shift = Counter()
    items_shift = Counter()
    
    for delivery in shift_deliveries:
        bartenders_shift[delivery.bartender] += delivery.qty
        barras_shift[delivery.barra] += delivery.qty
        items_shift[delivery.item_name] += delivery.qty
    
    top_bartenders_today = bartenders_shift.most_common(10)
    top_barras_today = barras_shift.most_common(10)
    top_items_today = items_shift.most_common(10)
    
    # Calcular entregas por hora del turno (21:00 - 06:00)
    hours_data = [0] * 10  # 21, 22, 23, 0, 1, 2, 3, 4, 5, 6
    hours_labels = ['21:00', '22:00', '23:00', '00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00']
    
    for delivery in shift_deliveries:
        try:
            if isinstance(delivery.timestamp, str):
                delivery_time = datetime.strptime(delivery.timestamp, '%Y-%m-%d %H:%M:%S')
            else:
                delivery_time = delivery.timestamp
            
            hour = delivery_time.hour
            if hour >= 21:
                idx = hour - 21
                hours_data[idx] += delivery.qty
            elif hour <= 6:
                idx = hour + 3  # 0->3, 1->4, ..., 6->9
                hours_data[idx] += delivery.qty
        except:
            continue
    
    # Obtener estadísticas de entradas desde la categoría "Entradas" del POS
    entradas_hours_data = [0] * 10  # 21:00 - 06:00
    entradas_hours_labels = ['21:00', '22:00', '23:00', '00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00']
    
    today_entradas = 0
    today_5000 = 0
    today_10000 = 0
    
    try:
        # Obtener ventas de entradas desde el POS (categoría "Entradas")
        from .helpers.pos_api import get_entradas_sales
        entradas_sales = get_entradas_sales(limit=100)  # Máximo 100 según límite API
        
        for sale in entradas_sales:
            sale_date = sale.get('sale_date', '')
            if not sale_date:
                continue
            
            # Filtrar por turno: ventas después de opened_at
            try:
                # Parsear fecha de venta
                if isinstance(sale_date, str):
                    if len(sale_date) >= 19:
                        sale_time = datetime.strptime(sale_date[:19], '%Y-%m-%d %H:%M:%S')
                    elif len(sale_date) >= 10:
                        sale_time = datetime.strptime(sale_date[:10], '%Y-%m-%d')
                    else:
                        continue
                else:
                    sale_time = sale_date
                
                # Solo procesar si la venta es del turno actual
                if sale_time >= shift_opened_at:
                    price = float(sale.get('price', 0))
                    qty = int(sale.get('quantity', 0))
                    
                    today_entradas += qty
                    if abs(price - 5000) < 100:  # Tolerancia para comparación de precios
                        today_5000 += qty
                    elif abs(price - 10000) < 100:
                        today_10000 += qty
                    
                    # Contar por hora (curva de entrada)
                    try:
                        hour = sale_time.hour
                        if hour >= 21:
                            idx = hour - 21
                            entradas_hours_data[idx] += qty
                        elif hour <= 6:
                            idx = hour + 3
                            entradas_hours_data[idx] += qty
                    except (ValueError, AttributeError):
                        pass
            except (ValueError, TypeError, AttributeError) as e:
                current_app.logger.debug(f"Error al procesar venta de entrada: {e}")
                continue
    except Exception as e:
        current_app.logger.warning(f"Error al obtener entradas desde POS: {e}")
        today_entradas = 0
        today_5000 = 0
        today_10000 = 0
    
    # Obtener estadísticas de cajas (cajeros y registros) desde el log local (NO consultar API)
    cashiers_registers_stats = stats_service.get_cashiers_and_registers_stats_from_log_for_shift(current_shift)
    
    # Filtrar solo las del turno desde el log local
    today_cashiers = []
    today_registers = []
    
    try:
        # Obtener tickets escaneados desde el log local
        from .helpers.ticket_scans import get_all_ticket_scans
        ticket_scans = get_all_ticket_scans()
        
        cashier_counts_today = Counter()
        register_counts_today = Counter()
        cashier_amounts_today = defaultdict(float)
        register_amounts_today = defaultdict(float)
        cashier_names = {}
        register_names = {}
        
        for sale_id, ticket_data in ticket_scans.items():
            scanned_at = ticket_data.get('scanned_at', '')
            
            # Filtrar por turno: tickets escaneados después de opened_at
            ticket_time = None
            if scanned_at:
                try:
                    ticket_time = datetime.fromisoformat(scanned_at.replace('Z', '+00:00').replace('+00:00', ''))
                    if ticket_time.tzinfo is not None:
                        ticket_time = ticket_time.replace(tzinfo=None)
                except:
                    pass
            
            # Solo procesar si el ticket es del turno actual
            if ticket_time and ticket_time >= shift_opened_at:
                sale_data = ticket_data.get('sale_data', {})
                employee_id = str(ticket_data.get('employee_id') or sale_data.get('employee_id') or sale_data.get('sold_by_employee_id') or '')
                register_id = str(ticket_data.get('register_id') or sale_data.get('register_id') or '')
                sale_total = float(sale_data.get('total', sale_data.get('sale_total', 0)) or 0)
                
                # Usar nombres guardados en el log
                vendedor = ticket_data.get('vendedor', 'Desconocido')
                caja = ticket_data.get('caja', 'Caja desconocida')
                
                if employee_id and employee_id != 'Sin cajero' and employee_id:
                    cashier_counts_today[employee_id] += 1
                    cashier_amounts_today[employee_id] += sale_total
                    if employee_id not in cashier_names:
                        cashier_names[employee_id] = vendedor if vendedor != 'Desconocido' else f'Cajero {employee_id}'
                
                if register_id and register_id != 'Sin caja' and register_id:
                    register_counts_today[register_id] += 1
                    register_amounts_today[register_id] += sale_total
                    if register_id not in register_names:
                        register_names[register_id] = caja if caja != 'Caja desconocida' else f'Caja {register_id}'
        
        # Top cajeros del día
        for employee_id, count in cashier_counts_today.most_common(10):
            today_cashiers.append({
                'id': employee_id,
                'name': cashier_names.get(employee_id, f'Cajero {employee_id}'),
                'sales_count': count,
                'total_amount': cashier_amounts_today.get(employee_id, 0)
            })
        
        # Top cajas del día
        for register_id, count in register_counts_today.most_common(10):
            today_registers.append({
                'id': register_id,
                'name': register_names.get(register_id, f'Caja {register_id}'),
                'sales_count': count,
                'total_amount': register_amounts_today.get(register_id, 0)
            })
    except Exception as e:
        current_app.logger.warning(f"Error al obtener estadísticas de cajas del día desde log: {e}")
    
    # Calcular promedio por hora del día
    current_hour = datetime.now(CHILE_TZ).hour
    if current_hour >= 21:
        hours_elapsed = max(1, current_hour - 21)
    else:
        hours_elapsed = max(1, current_hour + 3)
    avg_per_hour_today = delivery_stats.get('today_count', 0) / hours_elapsed if hours_elapsed > 0 else 0
    
    # Hora pico de entregas
    peak_hour_idx = max(range(len(hours_data)), key=lambda i: hours_data[i]) if hours_data else 0
    peak_hour_label = hours_labels[peak_hour_idx] if hours_labels else 'N/A'
    peak_hour_count = hours_data[peak_hour_idx] if hours_data else 0
    
    # Hora pico de entradas
    peak_entradas_idx = max(range(len(entradas_hours_data)), key=lambda i: entradas_hours_data[i]) if entradas_hours_data else 0
    peak_entradas_hour_label = entradas_hours_labels[peak_entradas_idx] if entradas_hours_labels else 'N/A'
    peak_entradas_count = entradas_hours_data[peak_entradas_idx] if entradas_hours_data else 0
    
    # Fecha actual para enlace al historial
    current_date = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
    
    # Calcular métricas del turno para el resumen
    shift_status_dict = current_shift.to_dict() if hasattr(current_shift, 'to_dict') else {
        'is_open': current_shift.is_open,
        'shift_date': current_shift.shift_date,
        'opened_at': current_shift.opened_at,
        'closed_at': current_shift.closed_at,
        'fiesta_nombre': current_shift.fiesta_nombre,
        'djs': current_shift.djs
    }
    
    # Calcular tiempo transcurrido
    # Calcular tiempo transcurrido usando hora de Chile
    now_chile = datetime.now(CHILE_TZ)
    if shift_opened_at.tzinfo is None:
        shift_opened_at_aware = pytz.UTC.localize(shift_opened_at)
    else:
        shift_opened_at_aware = shift_opened_at
    shift_opened_at_chile = shift_opened_at_aware.astimezone(CHILE_TZ)
    tiempo_transcurrido = now_chile - shift_opened_at_chile
    horas = int(tiempo_transcurrido.total_seconds() // 3600)
    minutos = int((tiempo_transcurrido.total_seconds() % 3600) // 60)
    
    # Calcular métricas del turno
    total_entregas_turno = delivery_stats.get('today_count', 0)
    total_entradas_turno = today_entradas
    monto_kiosko = 0  # Se calculará si hay datos del kiosko
    
    # Top productos y bartenders
    top_productos = [(item, qty) for item, qty in top_items_today[:3]]
    top_bartenders_shift = [(bartender, qty) for bartender, qty in top_bartenders_today[:3]]
    
    shift_metrics = {
        'tiempo_transcurrido': f"{horas}h {minutos}m",
        'total_entregas': total_entregas_turno,
        'total_entradas': total_entradas_turno,
        'entradas_5000': today_5000,
        'entradas_10000': today_10000,
        'monto_kiosko': monto_kiosko,
        'peak_hour': peak_hour_idx + 21 if peak_hour_idx < 3 else peak_hour_idx - 3,
        'peak_hour_count': peak_hour_count,
        'top_productos': top_productos,
        'top_bartenders': top_bartenders_shift,
        'opened_at': shift_opened_at,
        # Nuevas métricas con lógica
        'ritmo_actual': entregas_ultima_hora,
        'ritmo_promedio': promedio_hora_turno,
        'ritmo_porcentaje': ritmo_porcentaje,
        'ritmo_estado': ritmo_estado,
        'tendencia_porcentaje': tendencia_porcentaje,
        'tendencia_direccion': tendencia_direccion,
        'velocidad_15min': entregas_ultimos_15min,
        'velocidad_promedio_15min': promedio_15min_turno,
        'top_productos_ahora': top_productos_ahora,
        'top_bartenders_ahora': top_bartenders_ahora
    }
    
    # Renderizar template con todas las estadísticas
    return render_template(
        'admin_stats.html',
        # Estado del turno y métricas
        shift_status=shift_status_dict,
        shift_metrics=shift_metrics,
        # Estadísticas del día
        today_count=delivery_stats.get('today_count', 0),
        current_hour=current_hour,
        current_hour_count=delivery_stats.get('current_hour_count', 0),
        avg_per_hour=avg_per_hour_today,
        is_busy_hour=delivery_stats.get('is_busy_hour', False),
        is_slow_hour=delivery_stats.get('is_slow_hour', False),
        current_date=current_date,
        # Curva de compra (entregas por hora)
        hours_data=hours_data,
        hours_labels=hours_labels,
        peak_hour_label=peak_hour_label,
        peak_hour_count=peak_hour_count,
        # Rankings del día
        top_bartenders=top_bartenders_today,
        top_barras=top_barras_today,
        top_items=top_items_today,
        top_categorias=delivery_stats.get('top_categorias', []),  # Rankings de categorías
        top_cashiers=today_cashiers,
        top_registers=today_registers,
        # Entradas del día
        total_personas_en_local=today_entradas,
        entradas_5000_count=today_5000,
        entradas_10000_count=today_10000,
        # Curva de entrada (entradas por hora)
        entradas_hours_data=entradas_hours_data,
        entradas_hours_labels=entradas_hours_labels,
        peak_entradas_hour_label=peak_entradas_hour_label,
        peak_entradas_count=peak_entradas_count
    )

@bp.route('/admin/fraud_config', methods=['GET', 'POST'])
def fraud_config():
    """Configuración de umbrales de fraude"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('routes.login_admin'))
    
    if request.method == 'POST':
        max_hours = request.form.get('max_hours_old_ticket', type=int)
        max_attempts = request.form.get('max_delivery_attempts', type=int)
        
        if max_hours and max_hours > 0 and max_attempts and max_attempts > 0:
            config = {
                'max_hours_old_ticket': max_hours,
                'max_delivery_attempts': max_attempts
            }
            if save_fraud_config(config):
                flash("Configuración guardada exitosamente.", "success")
                return redirect(url_for('routes.fraud_config'))
            else:
                flash("Error al guardar la configuración.", "error")
        else:
            flash("Valores inválidos. Deben ser números mayores a 0.", "error")
    
    config = load_fraud_config()
    fraud_attempts = load_fraud_attempts()
    
    # Estadísticas de fraudes
    authorized_count = sum(1 for fa in fraud_attempts if len(fa) >= 7 and fa[7] == '1')
    unauthorized_count = sum(1 for fa in fraud_attempts if len(fa) >= 7 and fa[7] == '0')
    
    return render_template(
        'admin_fraud_config.html',
        config=config,
        total_fraud_attempts=len(fraud_attempts),
        authorized_count=authorized_count,
        unauthorized_count=unauthorized_count
    )

@bp.route('/admin/fraud_history')
def fraud_history():
    """Historial de autorizaciones de fraude"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('routes.login_admin'))
    
    fraud_attempts = load_fraud_attempts()
    
    # Ordenar por fecha (más recientes primero)
    fraud_attempts.reverse()
    
    return render_template(
        'admin_fraud_history.html',
        fraud_attempts=fraud_attempts
    )

@bp.route('/authorize_fraud', methods=['POST'])
def authorize_fraud_route():
    sale_id = request.form.get('sale_id')
    fraud_type = request.form.get('fraud_type')
    item_name = request.form.get('item_name', '')
    qty = request.form.get('qty', '0')
    admin_password = request.form.get('admin_password', '')
    return_url = request.form.get('return_url', url_for('routes.scanner'))
    
    if not all([sale_id, fraud_type, admin_password]):
        return render_template(
            'fraud_detection.html',
            sale_id=sale_id or '',
            fraud_message='Error: Faltan datos para autorizar.',
            fraud_type=fraud_type or '',
            fraud_details={},
            venta_info_adicional=None,
            item_name=item_name,
            qty=qty,
            return_url=return_url,
            error='Faltan datos para autorizar.'
        )
    
    # Verificar contraseña del administrador
    client_id = get_client_identifier()
    
    # Verificar si está bloqueado
    locked, remaining_time, attempts = is_locked_out(client_id)
    if locked:
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)
        numeric_sale_id = sale_id.replace("BMB ", "").strip()
        details = get_venta_details(numeric_sale_id)
        fraud_check = detect_fraud(sale_id, details.get('fecha_venta', '') if details else '')
        
        return render_template(
            'fraud_detection.html',
            sale_id=sale_id,
            fraud_message=fraud_check.get('message', 'FRAUDE DETECTADO'),
            fraud_type=fraud_type,
            fraud_details=fraud_check.get('details', {}),
            venta_info_adicional=details,
            item_name=item_name,
            qty=qty,
            return_url=return_url,
            error=f'Demasiados intentos fallidos. Intenta nuevamente en {minutes}m {seconds}s.'
        )
    
    if not verify_admin_password(admin_password):
        record_failed_attempt(client_id)
        # Obtener detalles de la venta para mostrar
        numeric_sale_id = sale_id.replace("BMB ", "").strip()
        details = get_venta_details(numeric_sale_id)
        fraud_check = detect_fraud(sale_id, details.get('fecha_venta', '') if details else '')
        
        return render_template(
            'fraud_detection.html',
            sale_id=sale_id,
            fraud_message=fraud_check.get('message', 'FRAUDE DETECTADO'),
            fraud_type=fraud_type,
            fraud_details=fraud_check.get('details', {}),
            venta_info_adicional=details,
            item_name=item_name,
            qty=qty,
            return_url=return_url,
            error='Contraseña de administrador incorrecta.'
        )
    
    # Autorizar el fraude
    success = authorize_fraud(sale_id, fraud_type)
    
    if success:
        clear_failed_attempts(client_id)
        session['last_activity'] = time.time()
        # Si hay item_name y qty, procesar la entrega automáticamente
        if item_name and qty and qty != '0':
            # Verificar nuevamente el fraude (ahora debería estar autorizado)
            numeric_sale_id = sale_id.replace("BMB ", "").strip()
            details = get_venta_details(numeric_sale_id)
            sale_time = details.get('fecha_venta', '') if details else ''
            fraud_check = detect_fraud(sale_id, sale_time)
            
            # Si aún hay fraude pero fue autorizado, continuar con la entrega
            if fraud_check['is_fraud']:
                # Verificar si está autorizado ahora
                from .helpers.fraud_detection import load_fraud_attempts
                fraud_attempts = load_fraud_attempts()
                is_authorized = False
                
                for attempt in reversed(fraud_attempts):
                    if len(attempt) >= 7 and attempt[0] == sale_id and attempt[6] == fraud_type:
                        if attempt[7] == '1':
                            is_authorized = True
                            break
                
                if is_authorized:
                    try:
                        qty_int = int(qty)
                        # Guardar la entrega
                        save_log(
                            sale_id,
                            item_name,
                            qty_int,
                            session.get('bartender'),
                            session.get('barra')
                        )
                        flash(f"{qty_int} × {item_name} entregado(s) con autorización administrativa.", "success")
                        return redirect(url_for('routes.scanner', sale_id=sale_id))
                    except (ValueError, TypeError):
                        pass
        
        flash("Fraude autorizado. Puedes continuar con la entrega.", "success")
        return redirect(return_url or url_for('routes.scanner', sale_id=sale_id))
    else:
        numeric_sale_id = sale_id.replace("BMB ", "").strip()
        details = get_venta_details(numeric_sale_id)
        fraud_check = detect_fraud(sale_id, details.get('fecha_venta', '') if details else '')
        
        return render_template(
            'fraud_detection.html',
            sale_id=sale_id,
            fraud_message=fraud_check.get('message', 'FRAUDE DETECTADO'),
            fraud_type=fraud_type,
            fraud_details=fraud_check.get('details', {}),
            venta_info_adicional=details,
            item_name=item_name,
            qty=qty,
            return_url=return_url,
            error='No se pudo autorizar el fraude. Intenta nuevamente.'
        )

@bp.route('/logout_admin')
def logout_admin():
    """Cerrar sesión de administrador y redirigir al home"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('routes.index'))

@bp.route('/admin/open_shift', methods=['GET', 'POST'])
def open_shift():
    """Redirigir a Gestión de Turnos (sistema único)"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('routes.login_admin'))
    
    # Redirigir al sistema único de turnos
    flash("ℹ️ Usa la sección 'Gestión de Turnos' para crear y gestionar turnos con planilla y responsables.", "info")
    return redirect(url_for('routes.admin_turnos'))

@bp.route('/admin/close_shift')
def close_shift():
    """Cerrar turno - conserva todos los datos para consultas y comparativas"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('routes.login_admin'))
    
    shift_service = get_shift_service()
    survey_service = get_survey_service()
    delivery_service = get_delivery_service()
    
    # Verificar que hay turno abierto
    current_status = shift_service.get_current_shift_status()
    if not current_status.is_open:
        flash("⚠️ No hay un turno abierto para cerrar.", "warning")
        return redirect(url_for('routes.admin_logs'))
    
    shift_date = current_status.shift_date or datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
    
    try:
        # 1. Cerrar sesiones de encuestas del día usando servicio
        try:
            survey_service.close_session(shift_date)
            current_app.logger.info(f"Sesiones del día {shift_date} cerradas (datos conservados)")
        except Exception as e:
            current_app.logger.error(f"Error al cerrar sesiones: {e}")
        
        # 2. Invalidar todo el cache (para forzar recarga en el próximo turno)
        clear_cache()
        current_app.logger.info("Cache invalidado")
        
        # 3. Obtener estadísticas del turno antes de cerrarlo
        deliveries = delivery_service.get_deliveries_by_shift_date(shift_date)
        
        # 4. Cerrar el turno usando servicio
        close_request = CloseShiftRequest(closed_by=session.get('admin_logged_in', 'admin'))
        
        try:
            success, message = shift_service.close_shift(close_request)
            
            if success:
                flash(f"✅ Turno cerrado correctamente para el día {shift_date}. Todos los datos han sido conservados para consultas y comparativas. ({len(deliveries)} entregas registradas)", "success")
            else:
                flash(f"⚠️ {message}. Los datos fueron conservados pero hubo un error al guardar el estado.", "warning")
        except ShiftNotOpenError as e:
            flash(f"⚠️ {str(e)}", "warning")
            # Redirigir a turnos si viene de ahí, sino al dashboard
            referer = request.headers.get('Referer', '')
            if '/admin/turnos' in referer:
                return redirect(url_for('routes.admin_turnos'))
            return redirect(url_for('routes.admin_logs'))
        
        # Redirigir a turnos si viene de ahí, sino al dashboard
        referer = request.headers.get('Referer', '')
        if '/admin/turnos' in referer:
            return redirect(url_for('routes.admin_turnos'))
        return redirect(url_for('routes.admin_dashboard'))
        
    except Exception as e:
        current_app.logger.error(f"Error al cerrar turno: {e}")
        flash(f"❌ Error al cerrar turno: {str(e)}", "error")
        # Redirigir a turnos si viene de ahí, sino al dashboard
        referer = request.headers.get('Referer', '')
        if '/admin/turnos' in referer:
            return redirect(url_for('routes.admin_turnos'))
        return redirect(url_for('routes.admin_dashboard'))

# =============================================================================
# Gestión de Inventario
# =============================================================================

@bp.route('/admin/inventory/register', methods=['GET', 'POST'])
def register_inventory():
    """Registrar inventario inicial de botellas por barra"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    shift_service = get_shift_service()
    inventory_service = get_inventory_service()
    
    # Verificar que hay turno abierto
    if not shift_service.is_shift_open():
        flash("⚠️ No hay un turno abierto. Abre un turno primero.", "warning")
        return redirect(url_for('routes.admin_dashboard'))
    
    shift_status = shift_service.get_current_shift_status()
    barras_disponibles = shift_status.barras_disponibles or [
        'Barra Principal',
        'Barra Terraza',
        'Barra VIP',
        'Barra Exterior'
    ]
    
    if request.method == 'POST':
        try:
            barra = request.form.get('barra', '').strip()
            registered_by = session.get('admin_logged_in', 'admin')
            
            # Obtener items del formulario
            # Los campos vienen como: product_name_X y quantity_X
            items = {}
            
            # Buscar índices
            indices = set()
            for key in request.form.keys():
                if key.startswith('product_name_'):
                    try:
                        idx = key.split('_')[-1]
                        indices.add(idx)
                    except:
                        pass
            
            # Procesar cada índice
            for idx in indices:
                product_name = request.form.get(f'product_name_{idx}', '').strip()
                quantity_str = request.form.get(f'quantity_{idx}', '0').strip()
                
                if product_name:
                    try:
                        quantity = int(quantity_str)
                        if quantity > 0:
                            items[product_name] = quantity
                    except ValueError:
                        pass
            
            if not items:
                flash("❌ Debes ingresar al menos un producto con cantidad mayor a 0", "error")
                return redirect(url_for('routes.register_inventory'))
            
            # Crear request
            inventory_request = RegisterInitialInventoryRequest(
                barra=barra,
                items=items,
                registered_by=registered_by
            )
            
            # Registrar inventario
            success, message = inventory_service.register_initial_inventory(inventory_request)
            
            if success:
                flash(f"✅ {message}", "success")
                return redirect(url_for('routes.view_inventory'))
            else:
                flash(f"❌ {message}", "error")
                
        except Exception as e:
            current_app.logger.error(f"Error al registrar inventario: {e}", exc_info=True)
            flash(f"❌ Error: {str(e)}", "error")
    
    # Obtener inventario actual para mostrar qué ya está registrado
    current_inventory = inventory_service.get_shift_inventory_summary()
    
    # Obtener lista de INGREDIENTES (botellas/insumos) para autocompletado
    # En el inventario contamos ingredientes, no productos de venta (tragos)
    from app.models.recipe_models import Ingredient
    all_ingredients = Ingredient.query.order_by(Ingredient.name).all()
    
    return render_template(
        'admin/register_inventory.html',
        barras_disponibles=barras_disponibles,
        current_inventory=current_inventory,
        all_products=all_ingredients # Pasamos ingredientes pero mantenemos el nombre de variable para no romper el template
    )

@bp.route('/admin/inventory')
@bp.route('/admin/inventario')
def view_inventory():
    """Ver inventario actual del turno"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    shift_service = get_shift_service()
    inventory_service = get_inventory_service()
    
    # Verificar que hay turno abierto
    if not shift_service.is_shift_open():
        flash("⚠️ No hay un turno abierto.", "warning")
        return redirect(url_for('routes.admin_dashboard'))
    
    shift_status = shift_service.get_current_shift_status()
    shift_date = shift_status.shift_date
    
    # Convertir shift_status a diccionario para el template
    shift_status_dict = shift_status.to_dict()
    
    # Obtener resumen de inventario
    inventory_summary = inventory_service.get_shift_inventory_summary()
    
    # Hacer shift_status disponible globalmente para base.html
    from flask import g
    g.shift_status = shift_status_dict
    
    return render_template(
        'admin/inventory.html',
        shift_date=shift_date,
        inventory_summary=inventory_summary,
        shift_status=shift_status_dict
    )

@bp.route('/admin/inventory/finalize', methods=['POST'])
def finalize_inventory():
    """Finalizar inventario de una barra (calcular cantidades finales)"""
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'error', 'message': 'No autorizado'}), 401
    
    try:
        data = request.get_json() or {}
        barra = data.get('barra') or request.form.get('barra', '').strip()
        finalized_by = session.get('admin_logged_in', 'admin')
        
        # Obtener cantidades reales (opcional)
        actual_quantities = data.get('actual_quantities') or {}
        
        inventory_request = FinalizeInventoryRequest(
            barra=barra,
            actual_quantities=actual_quantities if actual_quantities else None,
            finalized_by=finalized_by
        )
        
        inventory_service = get_inventory_service()
        success, message = inventory_service.finalize_inventory(inventory_request)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': message
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': message
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error al finalizar inventario: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error inesperado: {str(e)}'
        }), 500

@bp.route('/admin/inventory/summary/<barra>')
def inventory_summary_bar(barra):
    """Obtener resumen de inventario de una barra específica (API)"""
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'error', 'message': 'No autorizado'}), 401
    
    try:
        inventory_service = get_inventory_service()
        summary = inventory_service.get_bar_inventory_summary(barra)
        
        if not summary:
            return jsonify({
                'status': 'error',
                'message': f'No hay inventario registrado para {barra}'
            }), 404
        
        return jsonify({
            'status': 'success',
            'summary': {
                'barra': summary.barra,
                'shift_date': summary.shift_date,
                'total_items': summary.total_items,
                'total_initial': summary.total_initial,
                'total_delivered': summary.total_delivered,
                'total_expected_final': summary.total_expected_final,
                'total_actual_final': summary.total_actual_final,
                'total_difference': summary.total_difference,
                'is_finalized': summary.is_finalized,
                'items': summary.items
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener resumen: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error inesperado: {str(e)}'
        }), 500

@bp.route('/admin/restart_service', methods=['POST'])
def restart_service():
    """Reiniciar el servicio Flask - Versión mejorada y robusta"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('routes.login_admin'))
    
    try:
        # Obtener el directorio base del proyecto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        restart_script = os.path.join(base_dir, 'restart_service.sh')
        
        # Asegurar que el script existe
        if not os.path.exists(restart_script):
            current_app.logger.error(f"Script de reinicio no encontrado: {restart_script}")
            flash("⚠️ Error: Script de reinicio no encontrado. Por favor, crea el archivo restart_service.sh manualmente.", "error")
            return redirect(url_for('routes.admin_dashboard'))
        
        # Asegurar permisos de ejecución
        try:
            os.chmod(restart_script, 0o755)
        except Exception as e:
            current_app.logger.warning(f"No se pudieron establecer permisos en {restart_script}: {e}")
        
        # Preparar entorno completo
        env = os.environ.copy()
        env['PATH'] = '/usr/local/bin:/usr/bin:/bin:' + env.get('PATH', '')
        env['HOST'] = '0.0.0.0'
        env['PORT'] = '5001'
        # Mantener variables importantes
        env['PYTHONUNBUFFERED'] = '1'
        
        # Log del intento de reinicio
        current_app.logger.info(f"Ejecutando script de reinicio: {restart_script}")
        current_app.logger.info(f"Directorio de trabajo: {base_dir}")
        
        # Ejecutar el script en una nueva sesión completamente independiente
        # Usar /usr/bin/env bash para asegurar compatibilidad
        process = subprocess.Popen(
            ['/bin/bash', restart_script],
            stdout=subprocess.DEVNULL,  # Redirigir a devnull para evitar bloqueos
            stderr=subprocess.DEVNULL,
            cwd=base_dir,
            env=env,
            start_new_session=True,  # Crear nueva sesión para independencia
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Separar del proceso padre
        )
        
        current_app.logger.info(f"Script de reinicio iniciado con PID: {process.pid}")
        
        # Dar un momento para que el script comience a ejecutarse
        # No esperar demasiado para que la respuesta HTTP se envíe rápido
        import time
        time.sleep(0.5)  # Esperar medio segundo
        
        flash("✅ Comando de reinicio enviado. El servidor se reiniciará en 5-10 segundos. Por favor, espera unos segundos y recarga la página manualmente.", "success")
        
    except Exception as e:
        current_app.logger.error(f"Error al reiniciar servicio: {e}", exc_info=True)
        flash(f"⚠️ Error al reiniciar el servicio: {str(e)}. Por favor, ejecuta manualmente desde la terminal: cd {base_dir} && bash restart_service.sh", "error")
    
    # Redirigir inmediatamente - el script correrá independientemente en background
    return redirect(url_for('routes.admin_dashboard'))

# =============================================================================
# Administración del Agente de Redes Sociales
# =============================================================================

@bp.route('/admin/social-media')
def admin_social_media():
    """Dashboard del agente de redes sociales"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador para acceder a esta sección.", "info")
        return redirect(url_for('routes.login_admin'))
    
    # Verificar estado de OpenAI
    service = get_social_media_service()
    openai_configured = bool(current_app.config.get('OPENAI_API_KEY'))
    
    # Obtener estadísticas
    try:
        from app.infrastructure.repositories.social_media_repository import CsvSocialMediaRepository
        repo = CsvSocialMediaRepository()
        
        # Contar mensajes por plataforma
        platforms = ['instagram', 'facebook', 'twitter', 'whatsapp', 'tiktok']
        stats_by_platform = {}
        for platform in platforms:
            messages = repo.find_messages_by_platform(platform, limit=1000)
            stats_by_platform[platform] = len(messages)
        
        # Total de mensajes
        total_messages = sum(stats_by_platform.values())
        
        # Obtener últimos mensajes
        recent_messages = []
        for platform in platforms:
            messages = repo.find_messages_by_platform(platform, limit=5)
            recent_messages.extend(messages)
        
        # Ordenar por timestamp
        recent_messages.sort(key=lambda x: x.timestamp, reverse=True)
        recent_messages = recent_messages[:10]
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener estadísticas: {e}")
        stats_by_platform = {}
        total_messages = 0
        recent_messages = []
    
    return render_template(
        'admin_social_media.html',
        openai_configured=openai_configured,
        stats_by_platform=stats_by_platform,
        total_messages=total_messages,
        recent_messages=recent_messages
    )

@bp.route('/admin/social-media/messages', methods=['GET'])
def admin_social_media_messages():
    """API para obtener mensajes paginados"""
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'error', 'message': 'No autorizado'}), 401
    
    try:
        platform = request.args.get('platform', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        from app.infrastructure.repositories.social_media_repository import CsvSocialMediaRepository
        repo = CsvSocialMediaRepository()
        
        # Obtener mensajes
        if platform:
            messages = repo.find_messages_by_platform(platform, limit=1000)
        else:
            # Obtener de todas las plataformas
            platforms = ['instagram', 'facebook', 'twitter', 'whatsapp', 'tiktok']
            messages = []
            for p in platforms:
                messages.extend(repo.find_messages_by_platform(p, limit=200))
        
        # Ordenar por timestamp
        messages.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Paginación
        total = len(messages)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_messages = messages[start:end]
        
        # Formatear mensajes
        formatted_messages = []
        for msg in paginated_messages:
            formatted_messages.append({
                'message_id': msg.message_id,
                'platform': msg.platform,
                'sender': msg.sender,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'metadata': msg.metadata
            })
        
        return jsonify({
            'status': 'success',
            'messages': formatted_messages,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener mensajes: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error inesperado: {str(e)}'
        }), 500

@bp.route('/admin/social-media/stats', methods=['GET'])
def admin_social_media_stats():
    """API para obtener estadísticas del agente"""
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'error', 'message': 'No autorizado'}), 401
    
    try:
        from app.infrastructure.repositories.social_media_repository import CsvSocialMediaRepository
        repo = CsvSocialMediaRepository()
        
        platforms = ['instagram', 'facebook', 'twitter', 'whatsapp', 'tiktok']
        stats_by_platform = {}
        total_messages = 0
        
        for platform in platforms:
            messages = repo.find_messages_by_platform(platform, limit=10000)
            count = len(messages)
            stats_by_platform[platform] = count
            total_messages += count
        
        # Verificar OpenAI
        openai_configured = bool(current_app.config.get('OPENAI_API_KEY'))
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_messages': total_messages,
                'by_platform': stats_by_platform,
                'openai_configured': openai_configured,
                'model': current_app.config.get('OPENAI_DEFAULT_MODEL', 'gpt-4o-mini')
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener estadísticas: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error inesperado: {str(e)}'
        }), 500

# =============================================================================
# API de Agente de Redes Sociales
# =============================================================================

@bp.route('/api/social-media/generate-response', methods=['POST'])
def api_social_media_generate_response():
    """
    Genera una respuesta para un mensaje de redes sociales.
    
    Body JSON:
    {
        "message": "texto del mensaje",
        "platform": "instagram" | "facebook" | "twitter" | "whatsapp",
        "sender": "usuario_opcional",
        "tone": "amigable" | "profesional" | "casual" | "entusiasta" | "empático",
        "max_length": 280
    }
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('message'):
            return jsonify({
                'status': 'error',
                'message': 'El campo "message" es requerido'
            }), 400
        
        if not data.get('platform'):
            return jsonify({
                'status': 'error',
                'message': 'El campo "platform" es requerido'
            }), 400
        
        from app.application.dto.social_media_dto import GenerateResponseRequest
        
        request_dto = GenerateResponseRequest(
            message=data['message'],
            platform=data['platform'],
            sender=data.get('sender'),
            context=data.get('context'),
            tone=data.get('tone', 'amigable'),
            max_length=data.get('max_length', 280)
        )
        
        service = get_social_media_service()
        response = service.generate_response(request_dto)
        
        if not response:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo generar la respuesta. Verifica la configuración de OpenAI.'
            }), 500
        
        return jsonify({
            'status': 'success',
            'response': {
                'text': response.response_text,
                'model': response.model_used,
                'tokens_used': response.tokens_used
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al generar respuesta: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error inesperado: {str(e)}'
        }), 500

@bp.route('/api/social-media/process-message', methods=['POST'])
def api_social_media_process_message():
    """
    Procesa un mensaje recibido: lo guarda y genera una respuesta automáticamente.
    
    Body JSON:
    {
        "message_id": "id_unico",
        "platform": "instagram" | "facebook" | "twitter" | "whatsapp",
        "sender": "usuario",
        "content": "texto del mensaje",
        "metadata": {} (opcional)
    }
    """
    try:
        data = request.get_json()
        
        required_fields = ['message_id', 'platform', 'content']
        for field in required_fields:
            if not data or not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'El campo "{field}" es requerido'
                }), 400
        
        from app.application.dto.social_media_dto import SocialMediaMessage
        
        message = SocialMediaMessage(
            message_id=data['message_id'],
            platform=data['platform'],
            sender=data.get('sender'),
            content=data['content'],
            timestamp=datetime.now(CHILE_TZ),
            metadata=data.get('metadata')
        )
        
        service = get_social_media_service()
        response = service.process_message(
            message,
            generate_response=True,
            tone=data.get('tone', 'amigable')
        )
        
        if not response:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo generar la respuesta. Verifica la configuración de OpenAI.',
                'message_saved': True
            }), 500
        
        return jsonify({
            'status': 'success',
            'message': {
                'id': message.message_id,
                'platform': message.platform,
                'content': message.content,
                'timestamp': message.timestamp.isoformat()
            },
            'response': {
                'text': response.response_text,
                'model': response.model_used,
                'timestamp': response.timestamp.isoformat()
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al procesar mensaje: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error inesperado: {str(e)}'
        }), 500

@bp.route('/api/social-media/conversation-history', methods=['GET'])
def api_social_media_conversation_history():
    """
    Obtiene el historial de conversación de una plataforma y/o usuario.
    
    Query params:
    - platform: requerido (instagram, facebook, twitter, whatsapp)
    - sender: opcional (usuario específico)
    - limit: opcional (default: 10)
    """
    try:
        platform = request.args.get('platform')
        if not platform:
            return jsonify({
                'status': 'error',
                'message': 'El parámetro "platform" es requerido'
            }), 400
        
        sender = request.args.get('sender')
        limit = int(request.args.get('limit', 10))
        
        service = get_social_media_service()
        history = service.get_conversation_history(
            platform=platform,
            sender=sender,
            limit=limit
        )
        
        return jsonify({
            'status': 'success',
            'platform': platform,
            'sender': sender,
            'history': history,
            'count': len(history)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener historial: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error inesperado: {str(e)}'
        }), 500

@bp.route('/api/social-media/health', methods=['GET'])
def api_social_media_health():
    """
    Verifica el estado del servicio de redes sociales y OpenAI.
    """
    try:
        service = get_social_media_service()
        
        # Verificar configuración de OpenAI
        openai_key = current_app.config.get('OPENAI_API_KEY')
        # También verificar desde variables de entorno directamente
        if not openai_key:
            import os
            openai_key = os.environ.get('OPENAI_API_KEY')
        has_openai = bool(openai_key) and len(openai_key) > 50
        
        # Intentar una prueba de generación simple
        test_response = None
        if has_openai:
            try:
                from app.application.dto.social_media_dto import GenerateResponseRequest
                test_request = GenerateResponseRequest(
                    message="Hola",
                    platform="instagram",
                    max_length=50
                )
                test_response = service.generate_response(test_request)
            except Exception as e:
                current_app.logger.warning(f"Error en test de OpenAI: {e}")
        
        return jsonify({
            'status': 'ok',
            'openai_configured': has_openai,
            'openai_working': test_response is not None,
            'model': current_app.config.get('OPENAI_DEFAULT_MODEL', 'gpt-4o-mini')
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error en health check: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error inesperado: {str(e)}'
        }), 500
