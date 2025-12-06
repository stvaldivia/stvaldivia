from flask import session, request, current_app
from flask_socketio import emit


def register_socketio_events(socketio):

    @socketio.on('connect', namespace='/admin_logs')
    def admin_logs_connect(auth):
        # Verificar si el usuario está autenticado
        # Usar app_context para asegurar acceso correcto a la sesión
        try:
            with current_app.app_context():
                admin_logged_in = session.get('admin_logged_in', False)
                
                if admin_logged_in:
                    current_app.logger.info('✅ Admin WebSocket conectado')
                    emit('status', {'msg': 'Conectado al stream de logs.'})
                else:
                    current_app.logger.warning('❌ Intento NO autorizado de conexión WS')
                    # Permitir conexión pero informar que no está autorizado
                    emit('status', {'msg': 'No autorizado. Por favor, inicia sesión.'})
        except Exception as e:
            current_app.logger.error(f'Error en admin_logs_connect: {e}')
            # Permitir conexión incluso si hay error
            emit('status', {'msg': 'Conectado (modo limitado)'})

    @socketio.on('disconnect', namespace='/admin_logs')
    def admin_logs_disconnect():
        with current_app.app_context():
            current_app.logger.info('Admin WebSocket desconectado')

    @socketio.on('connect', namespace='/admin_stats')
    def admin_stats_connect():
        with current_app.app_context():
            if session.get('admin_logged_in'):
                current_app.logger.info('Admin Stats WebSocket conectado')
                emit('status', {'msg': 'Conectado al stream de estadísticas.'})
            else:
                current_app.logger.warning('Intento NO autorizado de conexión WS stats → desconectando.')
                return False

    @socketio.on('disconnect', namespace='/admin_stats')
    def admin_stats_disconnect():
        with current_app.app_context():
            current_app.logger.info('Admin Stats WebSocket desconectado')

    @socketio.on('connect', namespace='/encuesta')
    def survey_connect():
        with current_app.app_context():
            current_app.logger.info('Survey WebSocket conectado')
            emit('status', {'msg': 'Conectado al stream de encuestas.'})

    @socketio.on('disconnect', namespace='/encuesta')
    def survey_disconnect():
        with current_app.app_context():
            current_app.logger.info('Survey WebSocket desconectado')