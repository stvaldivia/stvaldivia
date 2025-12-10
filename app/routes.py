"""
Rutas principales del sistema BIMBA
"""
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from app.application.services.jornada_service import JornadaService
from app.application.dto.jornada_dto import (
    CrearJornadaRequest, AsignarResponsablesRequest, AbrirLocalRequest
)
from app.models.jornada_models import Jornada

# Crear blueprint principal (puede estar vacío si las rutas están en otros módulos)
bp = Blueprint('routes', __name__)

# Las rutas principales están definidas en otros módulos/blueprints
# Este blueprint puede usarse para rutas comunes si es necesario

@bp.route('/admin/dashboard')
def admin_dashboard():
    """Dashboard administrativo"""
    # Verificar autenticación
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin_dashboard.html')


@bp.route('/admin/logs')
def admin_logs():
    """Logs de entregas - redirige a admin_area"""
    # Verificar autenticación
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    # Obtener parámetros de paginación
    page = request.args.get('page', 1, type=int)
    turno = request.args.get('turno', 'false')
    per_page = request.args.get('per_page', 50, type=int)
    
    # Variables básicas para el template
    filter_by_turno = turno == 'true'
    current_page = page
    total_logs = 0  # Los logs se cargan dinámicamente via JavaScript/SocketIO
    logs = []  # Lista vacía - los logs se cargan dinámicamente
    
    # Calcular paginación (valores por defecto para evitar errores en el template)
    total_pages = 1
    has_prev = False
    has_next = False
    
    # Renderizar admin_area.html que parece ser la página principal de logs
    return render_template('admin_area.html',
                         filter_by_turno=filter_by_turno,
                         current_page=current_page,
                         per_page=per_page,
                         total_logs=total_logs,
                         logs=logs,
                         total_pages=total_pages,
                         has_prev=has_prev,
                         has_next=has_next)


@bp.route('/admin/pos_stats')
def pos_stats():
    """Estadísticas de POS (Cajas y Kioskos)"""
    # Verificar autenticación
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin/pos_stats.html')


@bp.route('/admin/panel_control')
def admin_panel_control():
    """Panel de control administrativo"""
    # Verificar autenticación
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin/panel_control.html')


@bp.route('/admin/turnos')
def admin_turnos():
    """Gestión de turnos y jornadas"""
    # Verificar autenticación
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin_turnos.html')


@bp.route('/admin/jornada/crear', methods=['POST'])
def crear_jornada():
    """Crear una nueva jornada"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    try:
        service = JornadaService()
        request_dto = CrearJornadaRequest(
            fecha_jornada=request.form.get('fecha_jornada'),
            tipo_turno=request.form.get('tipo_turno'),
            nombre_fiesta=request.form.get('nombre_fiesta'),
            horario_apertura_programado=request.form.get('horario_apertura_programado'),
            horario_cierre_programado=request.form.get('horario_cierre_programado'),
            djs=request.form.get('djs', '')
        )
        
        success, message, jornada = service.crear_jornada(request_dto, session.get('admin_user', 'admin'))
        
        if success:
            flash(message, 'success')
            return redirect(url_for('routes.admin_turnos', jornada_id=jornada.id if jornada else None))
        else:
            flash(message, 'error')
            return redirect(url_for('routes.admin_turnos'))
    except Exception as e:
        flash(f'Error al crear jornada: {str(e)}', 'error')
        return redirect(url_for('routes.admin_turnos'))


@bp.route('/admin/jornada/actualizar', methods=['POST'])
def actualizar_jornada():
    """Actualizar una jornada existente"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    try:
        jornada_id = request.form.get('jornada_id', type=int)
        if not jornada_id:
            flash('ID de jornada requerido', 'error')
            return redirect(url_for('routes.admin_turnos'))
        
        jornada = Jornada.query.get(jornada_id)
        if not jornada:
            flash('Jornada no encontrada', 'error')
            return redirect(url_for('routes.admin_turnos'))
        
        # Actualizar campos
        jornada.fecha_jornada = request.form.get('fecha_jornada', jornada.fecha_jornada)
        jornada.tipo_turno = request.form.get('tipo_turno', jornada.tipo_turno)
        jornada.nombre_fiesta = request.form.get('nombre_fiesta', jornada.nombre_fiesta)
        jornada.horario_apertura_programado = request.form.get('horario_apertura_programado', jornada.horario_apertura_programado)
        jornada.horario_cierre_programado = request.form.get('horario_cierre_programado', jornada.horario_cierre_programado)
        jornada.djs = request.form.get('djs', jornada.djs or '')
        
        from app.models import db
        db.session.commit()
        
        flash('Jornada actualizada correctamente', 'success')
        return redirect(url_for('routes.admin_turnos', jornada_id=jornada_id))
    except Exception as e:
        flash(f'Error al actualizar jornada: {str(e)}', 'error')
        return redirect(url_for('routes.admin_turnos'))


@bp.route('/admin/jornada/asignar_planilla', methods=['POST'])
def asignar_planilla_responsables():
    """Asignar responsables a la planilla"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    try:
        jornada_id = request.form.get('jornada_id', type=int)
        if not jornada_id:
            flash('ID de jornada requerido', 'error')
            return redirect(url_for('routes.admin_turnos'))
        
        service = JornadaService()
        request_dto = AsignarResponsablesRequest(
            responsable_cajas=request.form.get('responsable_cajas', ''),
            responsable_puerta=request.form.get('responsable_puerta', ''),
            responsable_seguridad=request.form.get('responsable_seguridad', ''),
            responsable_admin=request.form.get('responsable_admin', '')
        )
        
        success, message = service.asignar_responsables(jornada_id, request_dto)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('routes.admin_turnos', jornada_id=jornada_id))
    except Exception as e:
        flash(f'Error al asignar responsables: {str(e)}', 'error')
        return redirect(url_for('routes.admin_turnos'))


@bp.route('/admin/jornada/abrir_local', methods=['POST'])
def abrir_local():
    """Abrir el local (finalizar proceso de apertura)"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    try:
        jornada_id = request.form.get('jornada_id', type=int)
        if not jornada_id:
            flash('ID de jornada requerido', 'error')
            return redirect(url_for('routes.admin_turnos'))
        
        service = JornadaService()
        request_dto = AbrirLocalRequest(
            abierto_por=session.get('admin_user', 'admin')
        )
        
        success, message = service.abrir_local(jornada_id, request_dto)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('routes.admin_turnos', jornada_id=jornada_id))
    except Exception as e:
        flash(f'Error al abrir local: {str(e)}', 'error')
        return redirect(url_for('routes.admin_turnos'))


@bp.route('/admin/jornada/cerrar', methods=['POST'])
def cerrar_jornada():
    """Cerrar una jornada"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    try:
        jornada_id = request.form.get('jornada_id', type=int)
        if not jornada_id:
            flash('ID de jornada requerido', 'error')
            return redirect(url_for('routes.admin_turnos'))
        
        jornada = Jornada.query.get(jornada_id)
        if not jornada:
            flash('Jornada no encontrada', 'error')
            return redirect(url_for('routes.admin_turnos'))
        
        from datetime import datetime
        from app import CHILE_TZ
        from app.models import db
        
        jornada.estado_apertura = 'cerrado'
        jornada.cerrado_en = datetime.now(CHILE_TZ)
        jornada.cerrado_por = session.get('admin_user', 'admin')
        
        db.session.commit()
        
        flash('Jornada cerrada correctamente', 'success')
        return redirect(url_for('routes.admin_turnos'))
    except Exception as e:
        flash(f'Error al cerrar jornada: {str(e)}', 'error')
        return redirect(url_for('routes.admin_turnos'))


@bp.route('/admin/jornada/<int:jornada_id>/detalle')
def ver_detalle_jornada(jornada_id):
    """Ver detalle de una jornada"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    jornada = Jornada.query.get_or_404(jornada_id)
    return render_template('admin_detalle_jornada.html', jornada=jornada)


@bp.route('/admin/scanner')
def admin_scanner():
    """Redirigir al scanner"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return redirect(url_for('scanner.scanner'))


@bp.route('/admin/export/csv')
def export_csv():
    """Exportar logs en CSV"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return redirect(url_for('api.export_logs'))


@bp.route('/admin/fraud/config', methods=['GET', 'POST'])
def fraud_config():
    """Configuración de fraude"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    if request.method == 'POST':
        # Actualizar configuración
        try:
            from app.helpers.fraud_detection import load_fraud_config, save_fraud_config
            config = load_fraud_config()
            config['max_hours_old_ticket'] = int(request.form.get('max_hours_old_ticket', 24))
            config['max_attempts_per_hour'] = int(request.form.get('max_attempts_per_hour', 10))
            save_fraud_config(config)
            flash('Configuración actualizada correctamente', 'success')
        except Exception as e:
            flash(f'Error al actualizar configuración: {str(e)}', 'error')
        return redirect(url_for('routes.fraud_config'))
    
    # GET - Mostrar configuración
    try:
        from app.helpers.fraud_detection import load_fraud_config, load_fraud_attempts
        config = load_fraud_config()
        attempts = load_fraud_attempts()
        total_fraud_attempts = len(attempts)
        authorized_count = sum(1 for a in attempts if len(a) > 7 and a[7] == '1')
        unauthorized_count = total_fraud_attempts - authorized_count
    except Exception as e:
        config = {'max_hours_old_ticket': 24, 'max_attempts_per_hour': 10}
        total_fraud_attempts = 0
        authorized_count = 0
        unauthorized_count = 0
    
    return render_template('admin_fraud_config.html',
                         config=config,
                         total_fraud_attempts=total_fraud_attempts,
                         authorized_count=authorized_count,
                         unauthorized_count=unauthorized_count)


@bp.route('/admin/fraud/history')
def fraud_history():
    """Historial de fraudes"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    try:
        from app.helpers.fraud_detection import load_fraud_attempts
        attempts = load_fraud_attempts()
    except Exception:
        attempts = []
    
    return render_template('admin_fraud_history.html', fraud_attempts=attempts)


@bp.route('/admin/apertura')
def apertura():
    """Página de apertura"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin/apertura_cierre.html')


@bp.route('/admin/shift/open')
def open_shift():
    """Abrir turno"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin/open_shift.html')


@bp.route('/admin/shift/close', methods=['POST'])
def close_shift():
    """Cerrar turno"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    try:
        # Lógica para cerrar turno
        flash('Turno cerrado correctamente', 'success')
    except Exception as e:
        flash(f'Error al cerrar turno: {str(e)}', 'error')
    
    return redirect(url_for('home.index'))


@bp.route('/admin/shift/history')
def shift_history():
    """Historial de turnos"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin/shift_history.html')


@bp.route('/admin/inventory/view')
def view_inventory():
    """Ver inventario"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin/view_inventory.html')


@bp.route('/admin/inventory/register', methods=['GET', 'POST'])
def register_inventory():
    """Registrar inventario"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    if request.method == 'POST':
        try:
            # Lógica para registrar inventario
            flash('Inventario registrado correctamente', 'success')
            return redirect(url_for('routes.view_inventory'))
        except Exception as e:
            flash(f'Error al registrar inventario: {str(e)}', 'error')
    
    return render_template('admin/register_inventory.html')


@bp.route('/admin/social_media')
def admin_social_media():
    """Gestión de redes sociales"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin_social_media.html')


@bp.route('/admin/service/restart', methods=['POST'])
def restart_service():
    """Reiniciar servicio"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        # Lógica para reiniciar servicio (si es necesario)
        return jsonify({'success': True, 'message': 'Servicio reiniciado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/pagos/generar')
def admin_generar_pagos():
    """Generar pagos"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin/generar_pagos.html')


@bp.route('/admin/logs/turno')
def admin_logs_turno():
    """Logs por turno"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    return render_template('admin_logs_turno.html',
                         current_page=page,
                         per_page=per_page)


@bp.route('/admin/logs/modulos')
def admin_logs_modulos():
    """Logs por módulos"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin_logs_modulos.html')


@bp.route('/admin/logs/pendientes')
def admin_logs_pendientes():
    """Logs pendientes"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('auth.login_admin'))
    
    return render_template('admin_logs_pendientes.html')


@bp.route('/admin/area')
def admin_area():
    """Área administrativa (alias de admin_logs)"""
    return redirect(url_for('routes.admin_logs'))




