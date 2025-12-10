"""
Rutas para la gestión de Guardarropía
"""
from flask import render_template, request, redirect, session, url_for, flash, jsonify
from flask import current_app
from datetime import datetime
from app.application.services.service_factory import get_guardarropia_service
from app.application.dto.guardarropia_dto import (
    DepositItemRequest,
    RetrieveItemRequest,
    MarkLostRequest
)
from app.helpers.logger import get_logger
from app.helpers.pos_api import authenticate_employee
from app.helpers.puesto_validator import puede_abrir_puesto, obtener_empleados_habilitados_para_puesto
from app.helpers.session_manager import init_session
from app.helpers.motivational_messages import get_welcome_message, get_time_based_greeting

# El blueprint se importa desde __init__.py
from . import guardarropia_bp

logger = get_logger(__name__)


def require_admin():
    """Verifica que el usuario esté autenticado como administrador"""
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('routes.login_admin'))
    return None


def require_guardarropia_employee():
    """Verifica que el usuario esté autenticado como empleado de guardarropía"""
    if not session.get('guardarropia_logged_in'):
        flash("Debes iniciar sesión como empleado de guardarropía.", "error")
        return redirect(url_for('guardarropia.login'))
    return None


@guardarropia_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login de guardarropía - igual que las otras cajas"""
    # Limpiar sesión de caja regular si existe (para evitar conflictos)
    if session.get('pos_logged_in'):
        session.pop('pos_logged_in', None)
        session.pop('pos_employee_id', None)
        session.pop('pos_employee_name', None)
        session.pop('register_id', None)
        session.pop('register_name', None)
    
    if request.method == 'POST':
        pin = request.form.get('pin', '').strip()
        employee_id = request.form.get('employee_id')
        
        if not pin or not employee_id:
            flash("Debes ingresar tu PIN.", "error")
            employees = obtener_empleados_habilitados_para_puesto("guardarropia")
            return render_template('pos/login.html', employees=employees)
        
        employee = authenticate_employee(None, pin=pin, employee_id=employee_id)
        
        if employee:
            employee_id_str = str(employee["id"]) if employee.get("id") else None
            puede_acceder, mensaje_validacion, jornada_id = puede_abrir_puesto(employee_id_str, "guardarropia")
        
            if not puede_acceder:
                flash(mensaje_validacion, "error")
                employee_name = employee.get("name", "Desconocido")
                logger.warning(f"⚠️  Intento de acceso denegado a guardarropía: {employee_name} - {mensaje_validacion}")
                employees = obtener_empleados_habilitados_para_puesto("guardarropia")
                return render_template("pos/login.html", employees=employees)
            
            employee_id_str = str(employee['id']) if employee.get('id') else None
            session['guardarropia_employee_id'] = employee_id_str
            session['guardarropia_jornada_id'] = jornada_id
            session['guardarropia_employee_name'] = employee['name']
            session['guardarropia_logged_in'] = True
            employee_name = employee.get("name", "Empleado")
            logger.info(f"✅ Login exitoso en guardarropía: {employee_name}")
            init_session()
            welcome_msg = f"{get_time_based_greeting()} {get_welcome_message(employee_name)}"
            flash(welcome_msg, "success")
            # Redirigir a POS de guardarropía
            return redirect(url_for('guardarropia.pos'))
        else:
            flash("PIN incorrecto. Intenta nuevamente.", "error")
    
    employees = obtener_empleados_habilitados_para_puesto("guardarropia")
    if not employees:
        logger.warning("⚠️ No hay empleados habilitados para Guardarropía")
        flash("No hay trabajadores asignados a Guardarropía en el turno actual. Por favor, contacta al administrador.", "warning")
    return render_template('pos/login.html', employees=employees)


@guardarropia_bp.route('/')
def index():
    """Página principal de guardarropía - Redirige automáticamente a POS si hay turno abierto y empleado autenticado"""
    # Si el empleado está autenticado y hay turno abierto, redirigir a POS
    if session.get('guardarropia_logged_in'):
        from app.application.services.service_factory import get_shift_service
        shift_service = get_shift_service()
        shift_status = shift_service.get_current_shift_status()
        
        if shift_status.is_open:
            return redirect(url_for('guardarropia.pos'))
    
    # Si no está autenticado, redirigir a login
    if not session.get('guardarropia_logged_in'):
        return redirect(url_for('guardarropia.login'))
    
    try:
        service = get_guardarropia_service()
        
        # Obtener estadísticas
        stats = service.get_stats()
        
        # Obtener items depositados (no retirados)
        deposited_items = service.get_deposited_items()
        
        # Verificar estado del turno
        from app.application.services.service_factory import get_shift_service
        shift_service = get_shift_service()
        shift_status = shift_service.get_current_shift_status()
        
        return render_template(
            'guardarropia/index.html',
            stats=stats,
            deposited_items=deposited_items,
            shift_status=shift_status
        )
    except Exception as e:
        current_app.logger.error(f"Error en index de guardarropía: {e}", exc_info=True)
        flash(f"Error al cargar guardarropía: {str(e)}", "error")
        return redirect(url_for('guardarropia.login'))


@guardarropia_bp.route('/abrir-turno', methods=['GET', 'POST'])
def abrir_turno():
    """Abre un turno de guardarropía y redirige automáticamente a POS - Solo admin"""
    if require_admin():
        return require_admin()
    
    try:
        from app.application.services.service_factory import get_shift_service
        from app.application.dto.shift_dto import OpenShiftRequest
        from app.domain.exceptions import ShiftAlreadyOpenError
        
        shift_service = get_shift_service()
        shift_status = shift_service.get_current_shift_status()
        
        # Si ya hay turno abierto, redirigir directamente
        if shift_status.is_open:
            flash("Turno ya está abierto. Redirigiendo a guardarropía...", "info")
            return redirect(url_for('guardarropia.pos'))
        
        # Si es POST, abrir el turno
        if request.method == 'POST':
            opened_by = session.get('admin_user', 'admin')
            
            request_dto = OpenShiftRequest(
                fiesta_nombre=request.form.get('fiesta_nombre', 'Guardarropía'),
                opened_by=opened_by,
                djs='',
                barras_disponibles=[],
                bartenders=[],
                cashiers=[]
            )
            
            success, message = shift_service.open_shift(request_dto)
            
            if success:
                flash(f"✅ {message}", "success")
                return redirect(url_for('guardarropia.pos'))
            else:
                flash(f"❌ {message}", "error")
                return render_template('guardarropia/abrir_turno.html')
        
        # Si es GET, mostrar formulario para abrir turno
        return render_template('guardarropia/abrir_turno.html')
        
    except ShiftAlreadyOpenError:
        flash("Ya hay un turno abierto. Redirigiendo a guardarropía...", "info")
        return redirect(url_for('guardarropia.pos'))
    except Exception as e:
        current_app.logger.error(f"Error al abrir turno de guardarropía: {e}", exc_info=True)
        flash(f"Error inesperado: {str(e)}", "error")
        return redirect(url_for('guardarropia.index'))


@guardarropia_bp.route('/pos', methods=['GET'])
def pos():
    """Interfaz POS para venta de espacios de guardarropía"""
    # Verificar que el empleado esté autenticado
    if require_guardarropia_employee():
        return require_guardarropia_employee()
    
    # Verificar que hay turno abierto
    from app.application.services.service_factory import get_shift_service
    shift_service = get_shift_service()
    shift_status = shift_service.get_current_shift_status()
    
    if not shift_status.is_open:
        flash("No hay un turno abierto actualmente.", "warning")
        return redirect(url_for('guardarropia.login'))
    
    return render_template('guardarropia/pos.html')


@guardarropia_bp.route('/depositar', methods=['GET', 'POST'])
def depositar():
    """Depositar una prenda en guardarropía"""
    if require_guardarropia_employee():
        return require_guardarropia_employee()
    
    if request.method == 'POST':
        try:
            service = get_guardarropia_service()
            deposited_by = session.get('guardarropia_employee_name', 'Empleado')
            
            # Obtener turno actual para asociar
            from app.application.services.service_factory import get_shift_service
            shift_service = get_shift_service()
            shift_status = shift_service.get_current_shift_status()
            shift_date = shift_status.shift_date if shift_status.is_open else None
            
            # Precio fijo de $500
            price = 500.0
            
            # Tipo de pago (por defecto efectivo)
            payment_type = request.form.get('payment_type', 'cash').strip() or 'cash'
            
            # Nombre y teléfono son obligatorios
            customer_name = request.form.get('customer_name', '').strip()
            customer_phone = request.form.get('customer_phone', '').strip()
            
            if not customer_name:
                flash("El nombre del cliente es requerido", "error")
                return render_template('guardarropia/pos.html')
            
            if not customer_phone:
                flash("El teléfono del cliente es requerido", "error")
                return render_template('guardarropia/pos.html')
            
            request_dto = DepositItemRequest(
                ticket_code=None,  # Se genera automáticamente
                description=request.form.get('description', '').strip() or None,
                customer_name=customer_name,
                customer_phone=customer_phone,
                notes=request.form.get('notes', '').strip() or None,
                shift_date=shift_date,
                price=price,
                payment_type=payment_type
            )
            
            success, message, item = service.deposit_item(request_dto, deposited_by)
            
            if success:
                # Generar e imprimir ticket con QR
                try:
                    from app.infrastructure.services.ticket_printer_service import TicketPrinterService
                    printer_service = TicketPrinterService()
                    
                    # Generar ticket específico para guardarropía
                    ticket_img = printer_service.generate_guardarropia_ticket(
                        ticket_code=item.ticket_code,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        description=item.description,
                        price=float(price),
                        payment_type=payment_type,
                        deposited_at=item.deposited_at.isoformat() if item.deposited_at else None
                    )
                    
                    # Guardar y imprimir
                    import tempfile
                    import os
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    ticket_img.save(temp_file.name, 'PNG')
                    temp_file.close()
                    
                    # Imprimir
                    printer_service._print_macos(temp_file.name)
                    
                    # Limpiar
                    try:
                        os.remove(temp_file.name)
                    except:
                        pass
                        
                except Exception as e:
                    current_app.logger.error(f"Error al imprimir ticket: {e}", exc_info=True)
                    # Continuar aunque falle la impresión
                
                # Redirigir a página de éxito con ticket
                return redirect(url_for('guardarropia.ticket_success', ticket_code=item.ticket_code))
            else:
                flash(message, "error")
                return render_template('guardarropia/depositar.html')
                
        except Exception as e:
            current_app.logger.error(f"Error al depositar item: {e}", exc_info=True)
            flash(f"Error inesperado: {str(e)}", "error")
            return render_template('guardarropia/depositar.html')
    
    return render_template('guardarropia/depositar.html')


@guardarropia_bp.route('/retirar', methods=['GET', 'POST'])
def retirar():
    """Retirar una prenda de guardarropía"""
    if require_guardarropia_employee():
        return require_guardarropia_employee()
    
    if request.method == 'POST':
        try:
            service = get_guardarropia_service()
            retrieved_by = session.get('guardarropia_employee_name', 'Empleado')
            
            request_dto = RetrieveItemRequest(
                ticket_code=request.form.get('ticket_code', '').strip().upper(),
                retrieved_by=retrieved_by
            )
            
            success, message, item = service.retrieve_item(request_dto)
            
            if success:
                flash(message, "success")
                return redirect(url_for('guardarropia.index'))
            else:
                flash(message, "error")
                return render_template('guardarropia/retirar.html')
                
        except Exception as e:
            current_app.logger.error(f"Error al retirar item: {e}", exc_info=True)
            flash(f"Error inesperado: {str(e)}", "error")
            return render_template('guardarropia/retirar.html')
    
    return render_template('guardarropia/retirar.html')


@guardarropia_bp.route('/buscar', methods=['GET', 'POST'])
def buscar():
    """Buscar un item por código de ticket"""
    if require_guardarropia_employee():
        return require_guardarropia_employee()
    
    item = None
    if request.method == 'POST':
        try:
            service = get_guardarropia_service()
            ticket_code = request.form.get('ticket_code', '').strip().upper()
            
            if ticket_code:
                item = service.get_item_by_ticket(ticket_code)
                if not item:
                    flash(f"No se encontró un item con el código {ticket_code}", "error")
            else:
                flash("Por favor ingresa un código de ticket", "error")
                
        except Exception as e:
            current_app.logger.error(f"Error al buscar item: {e}", exc_info=True)
            flash(f"Error inesperado: {str(e)}", "error")
    
    return render_template('guardarropia/buscar.html', item=item)


@guardarropia_bp.route('/listar')
def listar():
    """Listar todos los items de guardarropía"""
    if require_guardarropia_employee():
        return require_guardarropia_employee()
    
    try:
        service = get_guardarropia_service()
        
        # Obtener parámetros de filtro
        status = request.args.get('status', '')
        shift_date = request.args.get('shift_date', '')
        
        # Obtener items
        items = service.get_all_items(
            status=status if status else None,
            shift_date=shift_date if shift_date else None
        )
        
        # Obtener estadísticas
        stats = service.get_stats(shift_date=shift_date if shift_date else None)
        
        return render_template(
            'guardarropia/listar.html',
            items=items,
            stats=stats,
            current_status=status,
            current_shift_date=shift_date
        )
    except Exception as e:
        current_app.logger.error(f"Error al listar items: {e}", exc_info=True)
        flash(f"Error al cargar items: {str(e)}", "error")
        return redirect(url_for('guardarropia.index'))


@guardarropia_bp.route('/marcar_perdido', methods=['POST'])
def marcar_perdido():
    """Marcar un item como perdido (API endpoint)"""
    if require_guardarropia_employee():
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    
    try:
        service = get_guardarropia_service()
        data = request.get_json()
        
        request_dto = MarkLostRequest(
            ticket_code=data.get('ticket_code', '').strip().upper(),
            notes=data.get('notes', '').strip() or None
        )
        
        success, message, item = service.mark_as_lost(request_dto)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'item': item.to_dict() if item else None
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error al marcar item como perdido: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Error inesperado: {str(e)}"
        }), 500


@guardarropia_bp.route('/ticket/<ticket_code>')
def ticket_success(ticket_code):
    """Muestra el ticket generado con QR"""
    if require_guardarropia_employee():
        return require_guardarropia_employee()
    
    try:
        service = get_guardarropia_service()
        item = service.get_item_by_ticket(ticket_code)
        
        if not item:
            flash(f"No se encontró el ticket {ticket_code}", "error")
            return redirect(url_for('guardarropia.index'))
        
        # Generar QR code para mostrar en pantalla
        import qrcode
        import base64
        import io
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4
        )
        qr.add_data(ticket_code)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convertir a base64 para mostrar en HTML
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        qr_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        return render_template(
            'guardarropia/ticket_success.html',
            item=item,
            qr_code=qr_base64
        )
    except Exception as e:
        current_app.logger.error(f"Error al mostrar ticket: {e}", exc_info=True)
        flash(f"Error al mostrar ticket: {str(e)}", "error")
        return redirect(url_for('guardarropia.index'))


@guardarropia_bp.route('/api/stats')
def api_stats():
    """API endpoint para obtener estadísticas"""
    if require_guardarropia_employee():
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        service = get_guardarropia_service()
        shift_date = request.args.get('shift_date', '')
        
        stats = service.get_stats(shift_date=shift_date if shift_date else None)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_deposited': stats.total_deposited,
                'total_retrieved': stats.total_retrieved,
                'total_lost': stats.total_lost,
                'currently_stored': stats.currently_stored,
                'shift_date': stats.shift_date
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error al obtener estadísticas: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Error inesperado: {str(e)}"
        }), 500

