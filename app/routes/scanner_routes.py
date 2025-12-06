"""
Rutas del Sistema de Escaneo y Entregas
"""
from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from collections import defaultdict
from app.application.services.service_factory import get_delivery_service
from app.application.validators import SaleIdValidator
from app.application.validators.sale_id_validator import SaleIdValidationError
from app.application.dto.delivery_dto import ScanSaleRequest, DeliveryRequest
from app.helpers.logger import get_logger, log_error
from app.helpers.fraud_detection import save_fraud_attempt
from app.helpers.pos_api import get_entity_details, get_employees, authenticate_employee
from app.infrastructure.rate_limiter.decorators import rate_limit

scanner_bp = Blueprint('scanner', __name__)
logger = get_logger(__name__)


@scanner_bp.route('/scanner', methods=['GET', 'POST'])
@rate_limit(max_requests=30, per_seconds=60)
def scanner():
    """Página del escáner - sistema de entregas independiente de turnos"""
    # Verificar sesión antes de mostrar el escáner
    if 'barra' not in session:
        flash("Por favor, selecciona una barra primero.", "info")
        return redirect(url_for('scanner.seleccionar_barra'))
    if 'bartender' not in session:
        flash("Por favor, selecciona un bartender.", "info")
        return redirect(url_for('scanner.seleccionar_bartender'))

    delivery_service = get_delivery_service()
    fraud_service = delivery_service.fraud_service
    
    items = []
    error = None
    venta_info = None
    fraud_detected = None

    # Validar entrada del usuario usando validador estricto
    user_input_id = (request.form.get('code', '') or request.args.get('sale_id', '')).strip()
    sale_id_canonical = None
    id_for_api_query = None

    if user_input_id:
        try:
            # Sanitizar primero
            sanitized_input = SaleIdValidator.sanitize_input(user_input_id)
            
            # Validar y normalizar usando el validador estricto
            sale_id_canonical, id_for_api_query = SaleIdValidator.validate_and_normalize(sanitized_input)
            
        except SaleIdValidationError as e:
            # Error de validación - mostrar mensaje amigable
            error = f"Error: {str(e)}"
            sale_id_canonical = None
            id_for_api_query = None
        except Exception as e:
            # Error inesperado
            log_error(
                logger,
                "Error validando sale_id",
                error=e,
                context={'user_input': user_input_id[:50]}
            )
            error = f"Error inesperado al validar código: {str(e)}"
            sale_id_canonical = None
            id_for_api_query = None

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
            if sale_id_canonical and sale_id_canonical.startswith("B "):
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
                    from app.helpers.ticket_scans import save_ticket_scan
                    # Preparar items para guardar
                    items_to_save = [{'name': item.get('name', ''), 'quantity': item.get('quantity', 0)} for item in items]
                    # Guardar toda la información de la venta para uso futuro
                    save_ticket_scan(sale_id_canonical, items_to_save, venta_info)
                
                # Verificar fraudes antes de mostrar el ticket
                sale_time = venta_info.get('fecha_venta', '')
                fraud_check = fraud_service.detect_fraud(sale_id_canonical, sale_time)
                
                if fraud_check['is_fraud']:
                    fraud_detected = fraud_check
                    # Guardar el intento de fraude
                    save_fraud_attempt(
                        sale_id=sale_id_canonical,
                        bartender=session.get('bartender', 'Desconocido'),
                        barra=session.get('barra', 'Desconocida'),
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
            return_url=url_for('scanner.scanner')
        )

    return render_template(
        'index.html',
        items=items,
        error=error,
        sale_id=sale_id_canonical,
        entregados_qty=entregados_qty,
        entregados_info=entregados_info,
        entregados_todos=entregados_todos,
        session_bartender=session.get('bartender'),
        session_barra=session.get('barra'),
        venta_info_adicional=venta_info
    )


@scanner_bp.route('/entregar', methods=['POST'])
@rate_limit(max_requests=50, per_seconds=60)
def entregar():
    """Registrar una entrega - thin controller usando DeliveryService"""
    from flask import current_app
    from app.domain.exceptions import ShiftNotOpenError, FraudDetectedError, DeliveryValidationError
    from app.helpers.fraud_detection import load_fraud_attempts
    
    # Verificar sesión
    if 'barra' not in session or 'bartender' not in session:
        flash("Error: No se ha seleccionado barra o bartender.", "error")
        return redirect(url_for('scanner.seleccionar_barra'))

    # Validar datos del formulario usando validadores estrictos
    from app.application.validators import SaleIdValidator, InputValidator, QuantityValidator
    from app.application.validators.sale_id_validator import SaleIdValidationError
    from app.application.validators.input_validator import InputValidationError
    from app.application.validators.quantity_validator import QuantityValidationError
    
    sale_id_raw = request.form.get('sale_id', '').strip()
    item_name_raw = request.form.get('item_name', '').strip()
    qty_str = request.form.get('qty', '').strip()
    
    # Validar sale_id
    try:
        sale_id_canonical, numeric_sale_id = SaleIdValidator.validate_and_normalize(
            SaleIdValidator.sanitize_input(sale_id_raw)
        )
        sale_id = sale_id_canonical
    except SaleIdValidationError as e:
        flash(f"Error en código de venta: {str(e)}", "error")
        return redirect(url_for('scanner.scanner', sale_id=sale_id_raw))
    
    # Validar item_name
    try:
        item_name = InputValidator.validate_string(
            item_name_raw,
            field_name="Nombre del producto",
            min_length=1,
            max_length=200,
            required=True
        )
    except InputValidationError as e:
        flash(f"Error en nombre del producto: {str(e)}", "error")
        return redirect(url_for('scanner.scanner', sale_id=sale_id))
    
    # Validar cantidad
    try:
        qty = QuantityValidator.validate(qty_str, field_name="Cantidad")
    except QuantityValidationError as e:
        flash(f"Error en cantidad: {str(e)}", "error")
        return redirect(url_for('scanner.scanner', sale_id=sale_id))

    # Usar servicios
    delivery_service = get_delivery_service()
    
    # Obtener información de la venta para validar cantidad pendiente y fecha
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
                    return redirect(url_for('scanner.scanner', sale_id=sale_id))
                break
    
    # Verificar autorización de fraudes previos
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
            # Guardar el intento de fraude
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
                return_url=url_for('scanner.scanner', sale_id=sale_id)
            )

    # Registrar entrega usando servicio
    delivery_request = DeliveryRequest(
        sale_id=sale_id,
        item_name=item_name,
        qty=qty,
        bartender=session.get('bartender'),
        barra=session.get('barra')
    )
    
    try:
        success, message, fraud_info = delivery_service.register_delivery_with_fraud_check(
            delivery_request,
            sale_time_str=sale_time
        )
        
        if success:
            flash(f"{qty} × {item_name} entregado(s).", "success")
        else:
            if fraud_info:
                flash(f"⚠️ {message}", "warning")
            else:
                flash(f"⚠️ {message}", "warning")
            
    except ShiftNotOpenError as e:
        flash(f"⚠️ {str(e)}", "error")
        return redirect(url_for('scanner.seleccionar_barra'))
    except FraudDetectedError as e:
        flash(f"⚠️ {str(e)}", "error")
        return redirect(url_for('scanner.scanner', sale_id=sale_id))
    except DeliveryValidationError as e:
        flash(f"❌ {str(e)}", "error")
        return redirect(url_for('scanner.scanner', sale_id=sale_id))
    except Exception as e:
        current_app.logger.error(f"Error al registrar entrega: {e}")
        flash(f"❌ Error al registrar entrega: {str(e)}", "error")
        return redirect(url_for('scanner.scanner', sale_id=sale_id))
    
    return redirect(url_for('scanner.scanner', sale_id=sale_id))


@scanner_bp.route('/barra', methods=['GET', 'POST'])
def seleccionar_barra():
    """Seleccionar barra para la sesión"""
    # Verificar que el bartender esté logueado
    if 'bartender' not in session:
        flash("Por favor, inicia sesión primero.", "info")
        return redirect(url_for('scanner.seleccionar_bartender'))
    
    if request.method == 'POST':
        b = request.form.get('barra')
        if b:
            session['barra'] = b
            # Después de seleccionar barra, ir al scanner
            return redirect(url_for('scanner.scanner'))
        flash("Debes seleccionar una barra.", "error")

    barras = ['Barra Principal', 'Barra Terraza', 'Barra VIP', 'Barra Exterior']
    return render_template('seleccionar_barra.html', barras=barras, current_barra=session.get('barra'))


@scanner_bp.route('/bartender', methods=['GET', 'POST'])
def seleccionar_bartender():
    """Seleccionar y autenticar bartender"""
    from flask import current_app
    import time
    
    selected_employee_id = session.get('selected_employee_id')
    selected_employee_info = session.get('selected_employee_info')

    if request.method == 'POST':
        # Si se cancela la selección
        if request.form.get('cancel'):
            session.pop('selected_employee_id', None)
            session.pop('selected_employee_info', None)
            return redirect(url_for('scanner.seleccionar_bartender'))
        
        # Si se selecciona un empleado
        employee_id = request.form.get('employee_id')
        if employee_id and not selected_employee_id:
            # Obtener información del empleado
            employee = get_entity_details("employees", employee_id)
            if employee:
                emp_id = employee.get('person_id') or employee.get('employee_id') or employee.get('id')
                emp_name = f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip() or employee.get('name', 'Empleado')
                
                session['selected_employee_id'] = emp_id
                session['selected_employee_info'] = {
                    'id': emp_id,
                    'name': emp_name,
                    'first_name': employee.get('first_name', ''),
                    'last_name': employee.get('last_name', '')
                }
                return redirect(url_for('scanner.seleccionar_bartender'))
            else:
                flash("No se pudo obtener información del empleado.", "error")
        
        # Si se ingresa el PIN
        pin = request.form.get('pin', '').strip()
        if pin and selected_employee_id:
            if not pin:
                flash("Debes ingresar tu PIN.", "error")
            else:
                # Autenticar empleado con PIN de PHP Point of Sale
                from app.helpers.pos_api import authenticate_employee
                employee = authenticate_employee(None, pin=pin, employee_id=selected_employee_id)
                
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
                    flash(f"Bienvenido, {employee['name']}!", "success")
                    # Ahora redirigir a seleccionar barra (después del login)
                    return redirect(url_for('scanner.seleccionar_barra'))
                else:
                    flash("PIN incorrecto. Intenta nuevamente.", "error")

    # Obtener lista de empleados bartenders desde la API
    try:
        employees = get_employees(only_bartenders=True)
    except Exception as e:
        current_app.logger.error(f"Error al obtener empleados: {e}")
        employees = []
        flash("No se pudieron cargar los empleados desde la API. Contacta al administrador.", "error")
    
    return render_template(
        'seleccionar_bartender.html', 
        employees=employees, 
        current_bartender=session.get('bartender'),
        selected_employee_id=selected_employee_id,
        selected_employee_info=selected_employee_info
    )


@scanner_bp.route('/reset')
def reset():
    """Resetear sesión (barra y bartender)"""
    session.pop('barra', None)
    session.pop('bartender', None)
    session.pop('bartender_id', None)
    session.pop('bartender_first_name', None)
    session.pop('bartender_last_name', None)
    session.pop('selected_employee_id', None)
    session.pop('selected_employee_info', None)
    flash("Sesión reiniciada.", "info")
    return redirect(url_for('scanner.seleccionar_barra'))














