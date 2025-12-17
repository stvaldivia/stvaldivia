"""
Rutas del Bot de IA (BimbaBot) para el Panel de Control
"""
import uuid
from flask import render_template, request, redirect, url_for, session, flash, current_app
from app.models import db
from app.models.bot_log_models import BotLog
from app.application.services.bot_log_service import BotLogService

# Importar el blueprint desde __init__.py
from . import admin_bp


@admin_bp.route('/bot/logs', methods=['GET'])
def bot_logs():
    """
    Vista de logs del bot de IA.
    Renderiza admin/bot_logs.html con los logs filtrados.
    """
    # Verificar autenticación
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('auth.login_admin'))
    
    try:
        service = BotLogService()
        
        # Leer filtros desde request.args con valores por defecto
        canal = request.args.get('canal', 'todos')
        direccion = request.args.get('direccion', 'todas')
        estado = request.args.get('estado', 'todos')
        limite = request.args.get('limite', type=int) or 100
        
        # Validar límite
        if limite < 1 or limite > 500:
            limite = 100
        
        # Traducir "todos"/"todas" -> None para pasar al servicio
        canal_filter = None if canal == 'todos' else canal
        direction_filter = None if direccion == 'todas' else direccion
        status_filter = None if estado == 'todos' else estado
        
        # Obtener logs usando el servicio
        logs = service.get_recent_logs(
            limit=limite,
            canal=canal_filter,
            direction=direction_filter,
            status=status_filter
        )
        
        # Obtener canales únicos para el selector de filtro
        canales_unicos = db.session.query(BotLog.canal).distinct().all()
        canales = [c[0] for c in canales_unicos if c[0]]
        
        # Pasar logs y valores de filtro actuales al template
        return render_template(
            'admin/bot_logs.html',
            logs=logs,
            canales=canales,
            filtro_canal=canal,
            filtro_direction=direccion,
            filtro_status=estado,
            limit=limite
        )
        
    except Exception as e:
        current_app.logger.error(f"Error al cargar logs del bot: {e}", exc_info=True)
        flash(f'Error al cargar logs: {str(e)}', 'error')
        return render_template('admin/bot_logs.html', logs=[], canales=[], 
                             filtro_canal='todos', filtro_direction='todas', 
                             filtro_status='todos', limit=100)


@admin_bp.route('/bot/test', methods=['POST'])
def bot_test():
    """
    Endpoint para probar el bot y registrar logs.
    Se activa cuando el usuario presiona "Probar Respuesta" en la consola de prueba.
    """
    # Verificar autenticación
    if not session.get('admin_logged_in'):
        flash("Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('auth.login_admin'))
    
    try:
        service = BotLogService()
        
        # Leer desde request.form
        canal = request.form.get('canal', 'interno').strip()
        mensaje_usuario = request.form.get('mensaje_usuario', '').strip()
        
        # Si mensaje_usuario viene vacío → redirigir a /admin/bot/logs
        if not mensaje_usuario:
            flash('El mensaje no puede estar vacío.', 'error')
            return redirect(url_for('admin.bot_logs'))
        
        # Generar un conversation_id usando uuid4()
        conversation_id = str(uuid.uuid4())
        
        # Registrar el mensaje del usuario
        service.log_user_message(
            canal=canal,
            conversation_id=conversation_id,
            message=mensaje_usuario,
            meta={"origin": "admin_test_console"}
        )
        
        # Generar la respuesta REAL del bot usando BimbaBotEngine
        from app.application.services.bimba_bot_engine import BimbaBotEngine
        respuesta = BimbaBotEngine.generar_respuesta_simple(
            mensaje_usuario=mensaje_usuario,
            canal=canal
        )
        
        # Registrar la respuesta del bot
        service.log_bot_response(
            canal=canal,
            conversation_id=conversation_id,
            message=respuesta,
            model="simple-programacion",
            status="success",
            meta={"origin": "admin_test_console"}
        )
        
        # Redirigir nuevamente a /admin/bot/logs para que los logs aparezcan en pantalla
        flash('Mensaje de prueba registrado correctamente.', 'success')
        return redirect(url_for('admin.bot_logs'))
        
    except Exception as e:
        current_app.logger.error(f"Error en test del bot: {e}", exc_info=True)
        flash(f'Error al procesar mensaje: {str(e)}', 'error')
        return redirect(url_for('admin.bot_logs'))


