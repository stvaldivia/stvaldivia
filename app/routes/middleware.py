"""
Middleware compartido para todas las rutas
Funciones comunes antes/durante/después de las peticiones
"""
from flask import request, redirect, url_for, flash, session
from app.helpers.session_utils import update_session_activity, check_session_timeout


def register_before_request(bp):
    """
    Registra el middleware before_request en un blueprint.
    
    Args:
        bp: Blueprint al que registrar el middleware
    """
    @bp.before_request
    def before_request():
        """Middleware para verificar timeout de sesión y actualizar actividad"""
        # No aplicar a rutas estáticas
        if request.endpoint and request.endpoint.startswith('static'):
            return
        
        # Verificar timeout de sesión para usuarios autenticados
        if session.get('bartender') or session.get('admin_logged_in'):
            if check_session_timeout():
                flash("Tu sesión ha expirado. Por favor, inicia sesión nuevamente.", "info")
                session.clear()
                return redirect(url_for('routes.scanner'))
            else:
                update_session_activity()














