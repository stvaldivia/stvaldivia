"""
Rutas de debugging - Solo disponibles en desarrollo o con DEBUG_ERRORS=1
"""
import os
from flask import Blueprint, jsonify, request, session, current_app

debug_bp = Blueprint('debug', __name__, url_prefix='/admin/debug')

def is_debug_enabled():
    """Verificar si el modo debug está habilitado"""
    is_production = os.environ.get('FLASK_ENV', '').lower() == 'production'
    debug_errors = os.environ.get('DEBUG_ERRORS', '0') == '1'
    is_localhost = request.host.startswith('localhost') or request.host.startswith('127.0.0.1')
    
    # Permitir si:
    # 1. No es producción Y es localhost, O
    # 2. DEBUG_ERRORS=1 está configurado, O
    # 3. Usuario admin está logueado (para producción con flag)
    return (not is_production and is_localhost) or debug_errors or session.get('admin_logged_in')


@debug_bp.route('/errors/export')
def export_errors():
    """Exportar reporte de errores capturados en el cliente"""
    if not is_debug_enabled():
        return jsonify({'error': 'Debug mode not enabled'}), 403
    
    # El reporte debe venir del cliente vía POST body
    # Por ahora retornamos instrucciones
    return jsonify({
        'message': 'Use window.getErrorReport() in browser console to get error report',
        'instructions': {
            'get_report': 'window.getErrorReport()',
            'clear_report': 'window.clearErrorReport()',
            'export_json': 'JSON.stringify(window.getErrorReport(), null, 2)'
        }
    })


@debug_bp.route('/errors', methods=['POST'])
def receive_errors():
    """Recibir reporte de errores del cliente"""
    if not is_debug_enabled():
        return jsonify({'error': 'Debug mode not enabled'}), 403
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Loggear errores críticos
        if data.get('network_errors'):
            for error in data['network_errors']:
                if error.get('status', 0) >= 500:
                    current_app.logger.error(
                        f"🔴 Network Error 5xx: {error.get('method')} {error.get('url')} → {error.get('status')}"
                    )
        
        if data.get('js_errors'):
            for error in data['js_errors']:
                current_app.logger.error(
                    f"🔴 JS Error: {error.get('message')} at {error.get('filename')}:{error.get('lineno')}"
                )
        
        # Retornar resumen
        return jsonify({
            'received': True,
            'summary': {
                'js_errors': len(data.get('js_errors', [])),
                'network_errors': len(data.get('network_errors', [])),
                'csp_violations': len(data.get('csp_violations', [])),
                'unhandled_rejections': len(data.get('unhandled_rejections', []))
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error receiving error report: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/errors')
def errors_panel():
    """Panel simple para ver resumen de errores"""
    if not is_debug_enabled():
        return jsonify({'error': 'Debug mode not enabled'}), 403
    
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Admin login required'}), 403
    
    return render_template('admin/debug_errors.html')

