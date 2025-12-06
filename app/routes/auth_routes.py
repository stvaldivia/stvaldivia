"""
Rutas de Autenticación
Login y logout de administradores
"""
from flask import Blueprint, render_template, request, redirect, session, url_for, flash
import time
from app.helpers.rate_limiting import record_failed_attempt, clear_failed_attempts, is_locked_out, get_client_identifier
from app.helpers.security import verify_admin_password
from app.helpers.admin_users import verify_admin_user
from app.helpers.motivational_messages import get_welcome_message, get_time_based_greeting

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login_admin', methods=['GET', 'POST'])
def login_admin():
    """Login de administrador"""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))
    
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
            welcome_msg = f"{get_time_based_greeting()} {get_welcome_message(username)}"
            flash(welcome_msg, "success")
            return redirect(url_for('admin.dashboard'))
        
        # Fallback a autenticación con contraseña única
        elif pwd and verify_admin_password(pwd):
            clear_failed_attempts(client_id)
            session['admin_logged_in'] = True
            session['admin_username'] = 'Admin'
            session['last_activity'] = time.time()
            flash("Bienvenido, Administrador!", "success")
            return redirect(url_for('admin.dashboard'))
        else:
            # Registrar intento fallido
            record_failed_attempt(client_id)
            flash("Credenciales incorrectas. Intenta nuevamente.", "error")
    
    return render_template('login_admin.html')


@auth_bp.route('/logout_admin')
def logout_admin():
    """Logout de administrador"""
    session.clear()
    flash("Sesión cerrada exitosamente.", "info")
    return redirect(url_for('home.index'))














