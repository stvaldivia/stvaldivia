import logging
from flask import render_template, request, jsonify, session, redirect, url_for, flash, current_app
from app.blueprints.pos import caja_bp
from app.helpers.pos_api import authenticate_employee, get_employees
from app.helpers.puesto_validator import puede_abrir_puesto, obtener_empleados_habilitados_para_puesto
from app.helpers.session_manager import init_session
from app.models import db
from datetime import datetime
from app.helpers.motivational_messages import get_welcome_message, get_time_based_greeting
from app.helpers.rate_limiting import is_locked_out, record_failed_attempt, clear_failed_attempts
from app.helpers.sale_audit_logger import SaleAuditLogger
from app.helpers.register_lock_db import unlock_register

logger = logging.getLogger(__name__)

@caja_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login del POS - usa autenticación local"""
    if request.method == 'POST':
        pin = request.form.get('pin', '').strip()
        employee_id = request.form.get('employee_id')
        
        if not pin or not employee_id:
            flash("Debes ingresar tu PIN.", "error")
            employees = obtener_empleados_habilitados_para_puesto("caja")
            return render_template('pos/login.html', employees=employees)
        
        employee = authenticate_employee(None, pin=pin, employee_id=employee_id)
        
        if employee:
            employee_id_str = str(employee["id"]) if employee.get("id") else None
            puede_acceder, mensaje_validacion, jornada_id = puede_abrir_puesto(employee_id_str, "caja")
        
            if not puede_acceder:
                flash(mensaje_validacion, "error")
                employee_name = employee.get("name", "Desconocido")
                logger.warning(f"⚠️  Intento de acceso denegado: {employee_name} - {mensaje_validacion}")
                employees = obtener_empleados_habilitados_para_puesto("caja")
                return render_template("pos/login.html", employees=employees)
            
            employee_id_str = str(employee['id']) if employee.get('id') else None
            session['pos_employee_id'] = employee_id_str
            session["jornada_id"] = jornada_id
            session['pos_employee_name'] = employee['name']
            session['pos_logged_in'] = True
            session['show_fortune_cookie'] = True  # Flag en sesión para mostrar galleta
            employee_name = employee.get("name", "Empleado")
            logger.info(f"✅ Login exitoso: {employee_name}")
            init_session()
            welcome_msg = f"{get_time_based_greeting()} {get_welcome_message(employee_name)}"
            flash(welcome_msg, "success")
            # Redirigir con parámetro para mostrar galleta de la fortuna
            return redirect(url_for('caja.register', show_fortune='true'))
        else:
            flash("PIN incorrecto. Intenta nuevamente.", "error")
    
    employees = obtener_empleados_habilitados_para_puesto("caja")
    if not employees:
        logger.warning("⚠️ No hay empleados habilitados para Caja")
        flash("No hay cajeros asignados en el turno actual. Por favor, contacta al administrador.", "warning")
    return render_template('pos/login.html', employees=employees)


@caja_bp.route('/api/verify-pin', methods=['POST'])
def api_verify_pin():
    """API: Verificar PIN del empleado actual para operaciones como cerrar caja"""
    if not session.get('pos_logged_in'):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        pin = data.get('pin', '').strip()
        
        if not pin:
            return jsonify({'success': False, 'error': 'PIN requerido'}), 400
        
        # Obtener employee_id de la sesión
        employee_id = session.get('pos_employee_id')
        if not employee_id:
            logger.warning("⚠️ No hay employee_id en la sesión")
            return jsonify({'success': False, 'error': 'No hay empleado en la sesión'}), 400
        
        # Verificar PIN usando la función de autenticación local
        from app.helpers.employee_local import authenticate_employee_local
        
        employee = authenticate_employee_local(str(employee_id), pin)
        
        if employee:
            logger.info(f"✅ PIN verificado correctamente para empleado {employee_id}")
            return jsonify({
                'success': True,
                'message': 'PIN verificado correctamente',
                'employee': {
                    'id': employee.get('id'),
                    'name': employee.get('name')
                }
            })
        else:
            logger.warning(f"❌ PIN incorrecto para empleado {employee_id}")
            return jsonify({'success': False, 'error': 'PIN incorrecto'}), 401
            
    except Exception as e:
        logger.error(f"Error al verificar PIN: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al verificar PIN: {str(e)}'}), 500

