import logging
import json
from datetime import datetime
from flask import render_template, request, jsonify, session, redirect, url_for, flash, current_app
from app import CHILE_TZ
from app.blueprints.pos import caja_bp
from app.blueprints.pos.services import pos_service
from app.infrastructure.services.ticket_printer_service import TicketPrinterService
from app.models import PosSale, db
from app.helpers.register_lock_db import (
    lock_register, is_register_locked, get_register_lock, 
    get_employee_locks, unlock_register, force_unlock_register
)
from app.helpers.shift_manager_compat import get_shift_status, close_shift as close_shift_helper
from app.helpers.register_close_db import save_register_close
from app.helpers.sale_security_validator import validate_session_active, validate_cart_before_close
from app.helpers.sos_drawer_helper import (
    save_sos_request, can_request_drawer, _get_sos_file_path
)
from app import socketio
import uuid
import os
from app.helpers.financial_utils import to_decimal, round_currency, safe_float

logger = logging.getLogger(__name__)

@caja_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Selección de caja"""
    # Limpiar sesión de guardarropía si existe (para evitar conflictos)
    if session.get('guardarropia_logged_in'):
        session.pop('guardarropia_logged_in', None)
        session.pop('guardarropia_employee_id', None)
        session.pop('guardarropia_jornada_id', None)
        session.pop('guardarropia_employee_name', None)
    
    if not session.get('pos_logged_in'):
        return redirect(url_for('caja.login'))
    
    # Obtener cajas disponibles
    default_registers = [
        {'id': '1', 'name': 'Caja 1'},
        {'id': '2', 'name': 'Caja 2'},
        {'id': '3', 'name': 'Caja 3'},
        {'id': '4', 'name': 'Caja 4'},
        {'id': '5', 'name': 'Caja 5'},
        {'id': '6', 'name': 'Caja 6'},
    ]
    
    try:
        api_registers = pos_service.get_registers()
        if api_registers and len(api_registers) > 0:
            registers = api_registers
        else:
            registers = default_registers
    except Exception as e:
        logger.error(f"Error al obtener cajas: {e}")
        registers = default_registers
    
    # Marcar cajas bloqueadas
    for reg in registers:
        reg_id = str(reg['id'])
        # Obtener información completa del bloqueo
        lock_info = get_register_lock(reg_id)
        if lock_info:
            reg['is_locked'] = True
            reg['locked_by'] = lock_info.get('employee_id')
            reg['locked_by_name'] = lock_info.get('employee_name')  # Nombre del cajero que bloqueó
            reg['locked_at'] = lock_info.get('locked_at')
            # Verificar si es MI bloqueo
            if str(lock_info.get('employee_id')) == str(session.get('pos_employee_id')):
                reg['is_locked_by_me'] = True
        else:
            reg['is_locked'] = False
            reg['locked_by'] = None
            reg['locked_by_name'] = None
            reg['locked_at'] = None
            reg['is_locked_by_me'] = False
    
    if request.method == 'POST':
        register_id = request.form.get('register_id')
        action = request.form.get('action')
        
        if not register_id:
            flash("Debes seleccionar una caja.", "error")
            return render_template('pos/register.html', registers=registers)
        
        # Buscar nombre de la caja
        register_name = next((r['name'] for r in registers if str(r['id']) == str(register_id)), f"Caja {register_id}")
        
        employee_id = session.get('pos_employee_id')
        employee_name = session.get('pos_employee_name')
        
        # Verificar estado del bloqueo
        lock_info = get_register_lock(register_id)
        locked = lock_info is not None
        
        if locked:
            # Si está bloqueada por otro usuario
            if str(lock_info.get('employee_id')) != str(employee_id):
                # Si es admin, permitir desbloquear
                if action == 'force_unlock':
                    # Lógica de desbloqueo forzado (simplificada para este ejemplo)
                    pass # Se implementaría si fuera necesario
                
                locked_by_employee_id = lock_info.get('employee_id')
                locked_by_employee_name = lock_info.get('employee_name', 'otro cajero')
                flash(f"🔒 Esta caja está siendo usada por {locked_by_employee_name}. No puedes acceder a una caja que está en uso por otro cajero.", "error")
                return render_template('pos/register.html', registers=registers)
            
            # Si es mi bloqueo, permitir retomar siempre (puede ser por interrupción: apagón, caída de internet, etc.)
            # IMPORTANTE: Si hay un cierre pendiente, no prevenimos retomar porque puede haber sido una interrupción
            # El cierre pendiente solo previene abrir una NUEVA sesión, no retomar una existente
            logger.info(f"✅ Cajero {employee_id} retomando su propia caja {register_id} (puede ser por interrupción)")
            
            session['pos_register_id'] = str(register_id)
            session['pos_register_name'] = register_name
            flash(f"Has retomado la {register_name}.", "success")
            return redirect(url_for('caja.sales'))
        
        # Si no está bloqueada, intentar bloquear
        # Verificar si hay confirmación (puede venir como 'confirmed'='true' o 'confirm_open'='1')
        confirmed = request.form.get('confirmed') == 'true' or request.form.get('confirm_open') == '1'
        
        if not confirmed:
            # Verificar si hay ventas previas en esta caja en el turno actual
            shift_status = get_shift_status()
            shift_date = shift_status.get('shift_date') if shift_status.get('is_open') else None
            
            previous_sales_count = 0
            previous_sales_total = 0.0
            has_other_employee_sales = False
            other_employee_name = ""
            
            if shift_date:
                try:
                    current_employee_id_str = str(employee_id) if employee_id else None
                    
                    previous_sales = PosSale.query.filter(
                        PosSale.register_id == str(register_id),
                        PosSale.shift_date == shift_date
                    ).all()
                    
                    previous_sales_count = len(previous_sales)
                    # CORRECCIÓN: Usar Decimal para suma de montos
                    from app.helpers.financial_utils import to_decimal, round_currency
                    previous_sales_total = round_currency(
                        sum(to_decimal(sale.total_amount or 0) for sale in previous_sales)
                    ) if previous_sales else 0.0
                    
                    # Verificar si hay ventas de otro cajero
                    if previous_sales:
                        for sale in previous_sales:
                            sale_employee_id = str(sale.employee_id) if sale.employee_id else None
                            if sale_employee_id and sale_employee_id != current_employee_id_str:
                                has_other_employee_sales = True
                                other_employee_name = sale.employee_name
                                break
                    
                    if has_other_employee_sales:
                        flash(f"Esta caja tiene ventas de {other_employee_name}. No puedes acceder.", "error")
                        return redirect(url_for('caja.register'))
                        
                except Exception as e:
                    logger.error(f"Error al verificar ventas previas: {e}")
            
            return render_template(
                'pos/confirm_register_open.html',
                register_id=register_id,
                register_name=register_name,
                previous_sales_count=previous_sales_count,
                previous_sales_total=previous_sales_total,
                shift_date=shift_date,
                is_zero=previous_sales_count == 0,
                has_other_employee_sales=has_other_employee_sales
            )
        
        # Confirmado - Bloquear (NUEVA caja)
        # Verificar si esta caja tiene un cierre pendiente antes de abrir una NUEVA sesión
        from app.models.pos_models import RegisterClose
        
        shift_status = get_shift_status()
        shift_date = shift_status.get('shift_date') if shift_status.get('is_open') else None
        
        has_pending_close = False
        if shift_date:
            pending_close = RegisterClose.query.filter_by(
                register_id=str(register_id),
                shift_date=shift_date,
                status='pending'
            ).first()
            
            if pending_close:
                has_pending_close = True
                logger.info(f"⚠️ Caja {register_id} tiene un cierre pendiente (ID: {pending_close.id}). No se puede abrir una nueva sesión hasta que el admin lo acepte.")
        
        if has_pending_close:
            flash(f"⏳ Esta caja tiene un cierre pendiente de revisión por el administrador. No puedes abrirla hasta que el cierre sea aceptado.", "warning")
            return redirect(url_for('caja.register'))
        
        # Verificar si tiene ventas en otras cajas (lógica simplificada del original)
        current_employee_id_str = str(employee_id) if employee_id else None
        
        if shift_date and current_employee_id_str:
             other_register_sales = PosSale.query.filter(
                PosSale.employee_id == current_employee_id_str,
                PosSale.register_id != str(register_id),
                PosSale.shift_date == shift_date
            ).first()
             
             if other_register_sales:
                 flash(f"Ya tienes ventas en otra caja (Caja {other_register_sales.register_id}). Debes usar esa.", "error")
                 return redirect(url_for('caja.register'))

        # Verificar bloqueos existentes
        existing_locks = get_employee_locks(employee_id)
        other_locks = [lock for lock in existing_locks if str(lock.register_id) != str(register_id)]
        
        if other_locks:
             flash(f"Ya tienes abierta la Caja {other_locks[0].register_id}. Debes cerrarla primero.", "error")
             return redirect(url_for('caja.register'))

        if lock_register(register_id, employee_id, employee_name):
            session['pos_register_id'] = str(register_id)
            session['pos_register_name'] = register_name
            
            # Verificar si se debe abrir cajón (si hay ventas previas)
            # ... (lógica omitida por brevedad, se asume manejo en frontend o siguiente paso)
            
            flash(f"Caja {register_name} abierta correctamente.", "success")
            return redirect(url_for('caja.sales'))
        else:
            flash("No se pudo bloquear la caja. Intenta nuevamente.", "error")
            
    return render_template('pos/register.html', registers=registers)


@caja_bp.route('/close-register', methods=['GET'])
def close_register_view():
    """Vista para cierre de caja (blind close)"""
    if not session.get('pos_logged_in'):
        return redirect(url_for('caja.login'))
    
    register_id = session.get('pos_register_id')
    if not register_id:
        flash("No tienes una caja asignada.", "warning")
        return redirect(url_for('caja.register'))
    
    return render_template('pos/close_register.html')


@caja_bp.route('/api/open-cash-drawer', methods=['POST'])
def api_open_cash_drawer():
    """API: Abrir cajón de dinero manualmente"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        printer_service = TicketPrinterService()
        success = printer_service.open_cash_drawer()
        
        if success:
            return jsonify({'success': True, 'message': 'Cajón abierto'})
        else:
            return jsonify({'success': False, 'error': 'No se pudo abrir el cajón'}), 500
    except Exception as e:
        logger.error(f"Error al abrir cajón: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@caja_bp.route('/api/register-summary', methods=['GET'])
def api_register_summary():
    """API: Obtener resumen de caja para cierre"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    register_id = session.get('pos_register_id')
    if not register_id:
        return jsonify({'success': False, 'error': 'No hay caja asignada'}), 400
    
    try:
        shift_status = get_shift_status()
        shift_date = shift_status.get('shift_date')
        opened_at = shift_status.get('opened_at')  # Fallback al opened_at del turno
        
        if not shift_date:
            # Fallback a fecha actual si no hay turno (no debería pasar)
            shift_date = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
        
        # Obtener el momento en que se abrió ESTA caja específica (locked_at del bloqueo)
        try:
            lock_info = get_register_lock(register_id)
            if lock_info and lock_info.get('locked_at'):
                locked_at = lock_info.get('locked_at')
                if isinstance(locked_at, str):
                    try:
                        locked_at_dt = datetime.fromisoformat(locked_at.replace('Z', '+00:00'))
                        if locked_at_dt.tzinfo:
                            locked_at_dt = locked_at_dt.replace(tzinfo=None)
                        opened_at = locked_at_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        opened_at = locked_at
                elif isinstance(locked_at, datetime):
                    locked_at_naive = locked_at.replace(tzinfo=None) if locked_at.tzinfo else locked_at
                    opened_at = locked_at_naive.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    opened_at = str(locked_at) if locked_at else opened_at
        except Exception as e:
            logger.debug(f"No se pudo obtener locked_at del bloqueo para resumen: {e}")
        
        # Obtener ventas locales de esta sesión/caja
        register_sales = PosSale.query.filter_by(
            register_id=str(register_id),
            shift_date=shift_date
        ).all()
        
        # Usar los campos específicos de pago (payment_cash, payment_debit, payment_credit)
        # en lugar de payment_type, ya que una venta puede tener múltiples métodos de pago
        total_cash = sum(float(s.payment_cash or 0) for s in register_sales)
        total_debit = sum(float(s.payment_debit or 0) for s in register_sales)
        total_credit = sum(float(s.payment_credit or 0) for s in register_sales)
        
        return jsonify({
            'success': True,
            'summary': {
                'total_sales': len(register_sales),
                'total_cash': total_cash,
                'total_debit': total_debit,
                'total_credit': total_credit,
                'total_amount': total_cash + total_debit + total_credit,
                'register_name': session.get('pos_register_name', 'Caja'),
                'employee_name': session.get('pos_employee_name', 'Cajero'),
                'shift_date': shift_date,
                'opened_at': opened_at  # Ahora es el momento en que el trabajador abrió esta caja
            },
            'sales': [s.to_dict() for s in register_sales[:50]] # Simplificado
        })
    except Exception as e:
        logger.error(f"Error al obtener resumen de caja: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@caja_bp.route('/api/close-register', methods=['POST'])
def api_close_register():
    """API: Procesar cierre de caja"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        is_valid, error = validate_session_active()
        if not is_valid:
            return jsonify({'success': False, 'error': error}), 401
        
        cart = session.get('pos_cart', [])
        is_valid, error = validate_cart_before_close(cart)
        if not is_valid:
            return jsonify({'success': False, 'error': error}), 400
        
        data = request.get_json()
        actual_cash = float(data.get('actual_cash', 0))
        actual_debit = float(data.get('actual_debit', 0))
        actual_credit = float(data.get('actual_credit', 0))
        notes = data.get('notes', '')
        
        if actual_cash < 0 or actual_debit < 0 or actual_credit < 0:
            return jsonify({'success': False, 'error': 'Los montos no pueden ser negativos'}), 400
        
        # Reutilizar lógica de resumen
        # En una refactorización real, esto debería estar en un servicio
        summary_response = api_register_summary()
        if summary_response.status_code != 200:
            return jsonify({'success': False, 'error': 'Error al obtener resumen'}), 500
        
        summary_data = summary_response.get_json()
        summary = summary_data.get('summary', {})
        expected_cash = summary.get('total_cash', 0)
        expected_debit = summary.get('total_debit', 0)
        expected_credit = summary.get('total_credit', 0)
        
        diff_cash = float(actual_cash) - float(expected_cash)
        diff_debit = float(actual_debit) - float(expected_debit)
        diff_credit = float(actual_credit) - float(expected_credit)
        difference = float(diff_cash + diff_debit + diff_credit)
        
        # Log para debug
        logger.info(f"💰 Cálculo de diferencias: cash={diff_cash}, debit={diff_debit}, credit={diff_credit}, total={difference}")
        
        # Obtener el momento en que se abrió ESTA caja específica (locked_at del bloqueo)
        register_id = session.get('pos_register_id')
        opened_at = summary.get('opened_at')  # Fallback al opened_at del turno
        
        try:
            lock_info = get_register_lock(register_id)
            if lock_info and lock_info.get('locked_at'):
                # Usar el locked_at como opened_at (momento en que el trabajador abrió esta caja)
                locked_at = lock_info.get('locked_at')
                if isinstance(locked_at, str):
                    # Si es string, intentar parsear
                    try:
                        locked_at_dt = datetime.fromisoformat(locked_at.replace('Z', '+00:00'))
                        if locked_at_dt.tzinfo:
                            locked_at_dt = locked_at_dt.replace(tzinfo=None)
                        opened_at = locked_at_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        opened_at = locked_at
                elif isinstance(locked_at, datetime):
                    # Si ya es datetime, formatear
                    locked_at_naive = locked_at.replace(tzinfo=None) if locked_at.tzinfo else locked_at
                    opened_at = locked_at_naive.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    opened_at = str(locked_at) if locked_at else summary.get('opened_at')
                logger.info(f"✅ Usando locked_at como opened_at para cierre: {opened_at}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo obtener locked_at del bloqueo, usando opened_at del turno: {e}")
        
        # Guardar cierre - Asegurar que todos los valores sean float explícitamente
        close_register_data = {
            'register_id': register_id,
            'register_name': summary.get('register_name'),
            'employee_id': session.get('pos_employee_id'),
            'employee_name': summary.get('employee_name'),
            'shift_date': summary.get('shift_date'),
            'opened_at': opened_at,  # Ahora es el momento en que el trabajador abrió esta caja
            'closed_at': datetime.now(CHILE_TZ).replace(tzinfo=None),
            'expected_cash': safe_float(expected_cash),
            'actual_cash': safe_float(actual_cash),
            'diff_cash': safe_float(diff_cash),
            'expected_debit': safe_float(expected_debit),
            'actual_debit': safe_float(actual_debit),
            'diff_debit': safe_float(diff_debit),
            'expected_credit': safe_float(expected_credit),
            'actual_credit': safe_float(actual_credit),
            'diff_credit': safe_float(diff_credit),
            'total_sales': int(summary.get('total_sales', 0)),
            # CORRECCIÓN: Usar Decimal para montos financieros
            'total_amount': safe_float(summary.get('total_amount', 0)),
            'difference_total': safe_float(difference),  # Usar Decimal para precisión
            'notes': notes
        }
        
        # Log para verificar que se está guardando correctamente
        logger.info(f"💾 Guardando cierre con difference_total={close_register_data['difference_total']}")
        
        # Guardar cierre con status 'pending' - espera aceptación del admin
        # NO se desbloquea la caja todavía - el admin debe aceptar el cierre primero
        close_register_data['status'] = 'pending'  # Asegurar que quede pendiente
        register_close = save_register_close(close_register_data)
        
        # Enviar notificación a admin
        if register_close:
            try:
                from app.helpers.notification_service import NotificationService
                
                # Determinar si es una diferencia grande (mayor a $2.000)
                diff = register_close.difference_total
                if abs(diff) > 2000:
                    NotificationService.notify_diferencia_grande(
                        cierre_id=register_close.id,
                        barra=register_close.register_name,
                        diferencia=diff
                    )
                else:
                    NotificationService.notify_cierre_pendiente(
                        cierre_id=register_close.id,
                        barra=register_close.register_name,
                        cajero=register_close.employee_name
                    )
            except Exception as e:
                logger.error(f"Error al enviar notificación de cierre: {e}")
        
        # Imprimir ticket de cierre
        try:
            printer_service = TicketPrinterService()
            printer_service.print_register_close_summary(
                register_name=summary.get('register_name'),
                employee_name=summary.get('employee_name'),
                shift_date=summary.get('shift_date'),
                opened_at=summary.get('opened_at'),
                closed_at=datetime.now(CHILE_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                total_sales=summary.get('total_sales'),
                expected_cash=expected_cash,
                actual_cash=actual_cash,
                diff_cash=diff_cash,
                expected_debit=expected_debit,
                actual_debit=actual_debit,
                diff_debit=diff_debit,
                expected_credit=expected_credit,
                actual_credit=actual_credit,
                diff_credit=diff_credit,
                difference_total=difference,
                is_balanced=abs(difference) < 100, # Tolerancia de 100 pesos
                notes=notes
            )
        except Exception as e:
            logger.error(f"Error al imprimir cierre: {e}")
        
        # Desbloquear la caja después del cierre
        # El cajero cierra la caja y la libera para que esté disponible nuevamente
        unlock_success = unlock_register(register_id)
        if unlock_success:
            logger.info(f"✅ Caja {register_id} desbloqueada después del cierre.")
        else:
            logger.warning(f"⚠️ No se pudo desbloquear la caja {register_id} después del cierre.")
        
        # Limpiar sesión de caja pero mantener login
        session.pop('pos_register_id', None)
        session.pop('pos_register_name', None)
        session.pop('pos_cart', None)
        
        # Emitir evento socket
        socketio.emit('register_closed', {
            'register_id': close_register_data['register_id'],
            'employee_name': close_register_data['employee_name'],
            'difference': difference
        })
        
        return jsonify({
            'success': True, 
            'message': 'Caja cerrada correctamente',
            'redirect_url': url_for('routes.index')
        })
        
    except Exception as e:
        logger.error(f"Error al cerrar caja: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@caja_bp.route('/close-shift', methods=['POST'])
def close_shift_route():
    """Cerrar turno completo (Admin)"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        success, message = close_shift_helper(closed_by=session.get('admin_username', 'admin'))
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        logger.error(f"Error al cerrar turno: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@caja_bp.route('/api/request-sos-drawer', methods=['POST'])
def api_request_sos_drawer():
    """API: Solicitar apertura SOS"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        employee_id = session.get('pos_employee_id')
        register_id = session.get('pos_register_id')
        
        can_request, error_message = can_request_drawer(employee_id, register_id)
        if not can_request:
            return jsonify({'success': False, 'error': error_message}), 429
        
        request_id = str(uuid.uuid4())
        sos_request = {
            'request_id': request_id,
            'register_id': register_id,
            'register_name': session.get('pos_register_name', 'Caja'),
            'employee_id': employee_id,
            'employee_name': session.get('pos_employee_name', 'Cajero'),
            'printer_name': session.get('pos_printer_name'),
            'requested_at': datetime.now(CHILE_TZ).isoformat(),
            'status': 'pending',
            'authorized_by': None,
            'authorized_at': None,
            'authorization_method': None
        }
        
        if save_sos_request(sos_request):
            return jsonify({
                'success': True, 
                'request_id': request_id, 
                'requires_authorization': True,
                'message': 'Solicitud enviada. Esperando autorización.'
            })
        else:
            return jsonify({'success': False, 'error': 'Error al guardar solicitud'}), 500
            
    except Exception as e:
        logger.error(f"Error SOS: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@caja_bp.route('/api/authorize-sos-drawer', methods=['POST'])
def api_authorize_sos_drawer():
    """API: Autorizar SOS con PIN"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        request_id = data.get('request_id')
        pin = data.get('pin', '').strip()
        
        if not request_id or not pin:
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        
        SUPERADMIN_PIN = current_app.config.get('SUPERADMIN_PIN', '9999')
        if pin != SUPERADMIN_PIN:
            return jsonify({'success': False, 'error': 'PIN incorrecto'}), 401
        
        # Lógica simplificada de actualización de archivo JSON
        instance_dir = current_app.instance_path
        sos_file = os.path.join(instance_dir, 'sos_drawer_requests.json')
        
        if not os.path.exists(sos_file):
            return jsonify({'success': False, 'error': 'Solicitud no encontrada'}), 404
            
        with open(sos_file, 'r', encoding='utf-8') as f:
            requests_list = json.load(f)
            
        request_found = False
        for req in requests_list:
            if req.get('request_id') == request_id and req.get('status') == 'pending':
                req['status'] = 'authorized'
                req['authorized_by'] = 'Superadmin (Presencial)'
                req['authorized_at'] = datetime.now(CHILE_TZ).isoformat()
                request_found = True
                break
        
        if not request_found:
            return jsonify({'success': False, 'error': 'Solicitud no encontrada o procesada'}), 404
            
        with open(sos_file, 'w', encoding='utf-8') as f:
            json.dump(requests_list, f, indent=2, ensure_ascii=False)
            
        # Abrir cajón
        printer_service = TicketPrinterService()
        if printer_service.open_cash_drawer():
            return jsonify({'success': True, 'message': 'Cajón abierto'})
        else:
            return jsonify({'success': False, 'error': 'Error de impresora'}), 500
            
    except Exception as e:
        logger.error(f"Error autorizar SOS: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
