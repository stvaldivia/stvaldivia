# Mejoras de Seguridad - Headers HTTP y Configuración
# Aplicar en app/__init__.py después de crear la app

from flask import Flask

def setup_security_headers(app: Flask):
    """
    Configura headers de seguridad HTTP
    
    Args:
        app: Instancia de Flask
    """
    
    @app.after_request
    def set_security_headers(response):
        """Agrega headers de seguridad a todas las respuestas"""
        # Prevenir clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Prevenir MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # XSS Protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy (ajustar según necesidades)
        # Permite recursos desde el mismo origen y CDNs comunes
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.socket.io; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com data:; "
            "connect-src 'self' ws://localhost:* wss://localhost:* ws://stvaldivia.cl:* wss://stvaldivia.cl:* https://stvaldivia.cl:*; "
            "frame-ancestors 'self';"
        )
        response.headers['Content-Security-Policy'] = csp
        
        # Permissions Policy (antes Feature-Policy)
        response.headers['Permissions-Policy'] = (
            'geolocation=(), '
            'microphone=(), '
            'camera=()'
        )
        
        # HSTS (solo en HTTPS, configurar en nginx para producción)
        # response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response
    
    return app


# Uso en app/__init__.py:
"""
def create_app():
    app = Flask(__name__)
    
    # ... otras configuraciones ...
    
    # Configurar headers de seguridad
    from app.helpers.security_headers import setup_security_headers
    setup_security_headers(app)
    
    return app
"""

