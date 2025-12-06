"""
Ejemplo de integración del sistema de notificaciones
Este archivo muestra cómo integrar las notificaciones en diferentes partes del sistema
"""

# ============================================================================
# EJEMPLO 1: Notificar cuando se registra un cierre de caja
# ============================================================================

# En app/routes.py o donde se registren los cierres de caja:

def registrar_cierre_caja(barra, cajero, monto_declarado, monto_sistema):
    """Ejemplo de función que registra un cierre de caja"""
    from app.helpers.notification_service import NotificationService
    
    # ... código para registrar el cierre ...
    cierre_id = 123  # ID del cierre registrado
    
    # Calcular diferencia
    diferencia = monto_declarado - monto_sistema
    
    # Notificar cierre pendiente
    NotificationService.notify_cierre_pendiente(
        cierre_id=cierre_id,
        barra=barra,
        cajero=cajero
    )
    
    # Si la diferencia es grande (más de $20,000), notificar con prioridad crítica
    if abs(diferencia) > 20000:
        NotificationService.notify_diferencia_grande(
            cierre_id=cierre_id,
            barra=barra,
            diferencia=diferencia
        )


# ============================================================================
# EJEMPLO 2: Notificar cuando se detecta un fraude
# ============================================================================

# En app/helpers/fraud_detection.py o donde se detecten fraudes:

def detect_fraud_with_notification(sale_id, bartender, sale_time):
    """Ejemplo de función que detecta fraudes y notifica"""
    from app.helpers.notification_service import NotificationService
    from app.helpers.fraud_detection import detect_fraud
    
    # Detectar fraude usando la función existente
    fraud_check = detect_fraud(sale_id, sale_time)
    
    if fraud_check['is_fraud']:
        # Notificar el fraude detectado
        NotificationService.notify_fraude_detectado(
            sale_id=sale_id,
            bartender=bartender,
            fraud_type=fraud_check['fraud_type']
        )
        
        return fraud_check
    
    return {'is_fraud': False}


# ============================================================================
# EJEMPLO 3: Notificar al abrir/cerrar turnos
# ============================================================================

# En app/application/services/shift_service.py:

def abrir_turno_con_notificacion(jornada_nombre, admin_user):
    """Ejemplo de función que abre un turno y notifica"""
    from app.helpers.notification_service import NotificationService
    
    # ... código para abrir el turno ...
    
    # Notificar apertura de turno
    NotificationService.notify_turno_abierto(
        jornada_nombre=jornada_nombre,
        admin=admin_user
    )


def cerrar_turno_con_notificacion(jornada_nombre, admin_user, total_ventas):
    """Ejemplo de función que cierra un turno y notifica"""
    from app.helpers.notification_service import NotificationService
    
    # ... código para cerrar el turno ...
    
    # Notificar cierre de turno
    NotificationService.notify_turno_cerrado(
        jornada_nombre=jornada_nombre,
        admin=admin_user,
        total_ventas=total_ventas
    )


# ============================================================================
# EJEMPLO 4: Notificaciones personalizadas
# ============================================================================

def enviar_notificacion_personalizada():
    """Ejemplo de notificaciones personalizadas"""
    from app.helpers.notification_service import NotificationService
    
    # Notificación informativa
    NotificationService.notify_info(
        title='Sistema Actualizado',
        message='El sistema ha sido actualizado a la versión 2.0',
        action_url='/admin/dashboard'
    )
    
    # Notificación de éxito
    NotificationService.notify_success(
        title='Backup Completado',
        message='El backup de la base de datos se completó exitosamente'
    )
    
    # Notificación de advertencia
    NotificationService.notify_warning(
        title='Espacio en Disco Bajo',
        message='El espacio en disco está por debajo del 10%'
    )
    
    # Notificación de error
    NotificationService.notify_error(
        title='Error de Conexión',
        message='No se pudo conectar con el servidor de pagos'
    )
    
    # Notificación completamente personalizada
    NotificationService.create_notification(
        type='info',
        title='Título Personalizado',
        message='Mensaje personalizado con todos los detalles',
        priority=3,  # 1=baja, 2=normal, 3=alta, 4=crítica
        data={'custom_field': 'custom_value'},  # Datos adicionales
        action_url='/admin/custom-page',
        target_user='admin'  # Usuario específico (None = todos)
    )


# ============================================================================
# EJEMPLO 5: Integración en rutas Flask
# ============================================================================

from flask import Blueprint, request, jsonify, session
from app.helpers.notification_service import NotificationService

bp = Blueprint('example', __name__)

@bp.route('/admin/aprobar-cierre/<int:cierre_id>', methods=['POST'])
def aprobar_cierre(cierre_id):
    """Ejemplo de ruta que aprueba un cierre y notifica"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 401
    
    # ... código para aprobar el cierre ...
    
    # Notificar que el cierre fue aprobado
    NotificationService.notify_success(
        title='Cierre Aprobado',
        message=f'El cierre #{cierre_id} ha sido aprobado',
        action_url=f'/admin/cajas'
    )
    
    return jsonify({'success': True})


@bp.route('/admin/rechazar-cierre/<int:cierre_id>', methods=['POST'])
def rechazar_cierre(cierre_id):
    """Ejemplo de ruta que rechaza un cierre y notifica"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'No autorizado'}), 401
    
    motivo = request.json.get('motivo', 'Sin motivo especificado')
    
    # ... código para rechazar el cierre ...
    
    # Notificar que el cierre fue rechazado
    NotificationService.notify_warning(
        title='Cierre Rechazado',
        message=f'El cierre #{cierre_id} fue rechazado: {motivo}',
        action_url=f'/admin/cajas'
    )
    
    return jsonify({'success': True})


# ============================================================================
# EJEMPLO 6: Notificaciones programadas (con scheduler)
# ============================================================================

def notificaciones_programadas():
    """Ejemplo de notificaciones programadas (requiere scheduler como APScheduler)"""
    from app.helpers.notification_service import NotificationService
    from datetime import datetime
    
    # Verificar si es hora de cerrar (ejemplo: 6 AM)
    now = datetime.now()
    if now.hour == 6 and now.minute == 0:
        NotificationService.notify_warning(
            title='Recordatorio de Cierre',
            message='Es hora de cerrar el turno de la noche',
            action_url='/admin/turnos'
        )
    
    # Verificar cierres pendientes hace más de 2 horas
    # ... código para verificar cierres pendientes ...
    cierres_pendientes = []  # Obtener de la BD
    
    for cierre in cierres_pendientes:
        NotificationService.notify_warning(
            title='Cierre Pendiente Hace Tiempo',
            message=f'El cierre de {cierre["barra"]} lleva más de 2 horas pendiente',
            action_url='/admin/cajas'
        )


# ============================================================================
# EJEMPLO 7: Notificaciones basadas en eventos del sistema
# ============================================================================

def on_database_backup_complete(success, file_path):
    """Callback cuando se completa un backup de la base de datos"""
    from app.helpers.notification_service import NotificationService
    
    if success:
        NotificationService.notify_success(
            title='Backup Completado',
            message=f'Backup guardado en: {file_path}'
        )
    else:
        NotificationService.notify_error(
            title='Error en Backup',
            message='No se pudo completar el backup de la base de datos'
        )


def on_low_stock(producto, cantidad_actual, cantidad_minima):
    """Callback cuando un producto tiene stock bajo"""
    from app.helpers.notification_service import NotificationService
    
    NotificationService.notify_warning(
        title='Stock Bajo',
        message=f'{producto}: {cantidad_actual} unidades (mínimo: {cantidad_minima})',
        action_url='/admin/inventario'
    )


def on_employee_login(employee_name):
    """Callback cuando un empleado inicia sesión"""
    from app.helpers.notification_service import NotificationService
    
    # Solo notificar en horarios inusuales (ejemplo: antes de las 10 AM)
    from datetime import datetime
    if datetime.now().hour < 10:
        NotificationService.notify_info(
            title='Empleado Conectado',
            message=f'{employee_name} inició sesión fuera del horario habitual'
        )


# ============================================================================
# EJEMPLO 8: Testing - Crear notificaciones de prueba
# ============================================================================

def crear_notificaciones_de_prueba():
    """Función para crear notificaciones de prueba"""
    from app.helpers.notification_service import NotificationService
    import time
    
    # Crear una de cada tipo
    NotificationService.notify_cierre_pendiente(
        cierre_id=999,
        barra='Barra de Prueba',
        cajero='Cajero de Prueba'
    )
    
    time.sleep(1)
    
    NotificationService.notify_diferencia_grande(
        cierre_id=999,
        barra='Barra de Prueba',
        diferencia=-50000
    )
    
    time.sleep(1)
    
    NotificationService.notify_fraude_detectado(
        sale_id='BMB 99999',
        bartender='Bartender de Prueba',
        fraud_type='ticket_antiguo'
    )
    
    time.sleep(1)
    
    NotificationService.notify_turno_abierto(
        jornada_nombre='Fiesta de Prueba',
        admin='Admin de Prueba'
    )
    
    time.sleep(1)
    
    NotificationService.notify_info(
        title='Notificación de Información',
        message='Esta es una notificación informativa de prueba'
    )
    
    time.sleep(1)
    
    NotificationService.notify_success(
        title='Notificación de Éxito',
        message='Esta es una notificación de éxito de prueba'
    )
    
    time.sleep(1)
    
    NotificationService.notify_warning(
        title='Notificación de Advertencia',
        message='Esta es una notificación de advertencia de prueba'
    )
    
    time.sleep(1)
    
    NotificationService.notify_error(
        title='Notificación de Error',
        message='Esta es una notificación de error de prueba'
    )


# ============================================================================
# NOTAS DE IMPLEMENTACIÓN
# ============================================================================

"""
IMPORTANTE:

1. Todas las notificaciones se guardan en la base de datos automáticamente
2. Las notificaciones se emiten por Socket.IO a la sala 'admins' por defecto
3. Se puede especificar un usuario específico con target_user
4. Las notificaciones tienen prioridades (1-4) que afectan el estilo visual y el sonido
5. Cada notificación puede tener una action_url para redirigir al hacer click

INTEGRACIÓN RECOMENDADA:

1. Cierres de Caja:
   - Notificar cuando se registra un cierre
   - Notificar si hay diferencia grande
   - Notificar cuando se aprueba/rechaza

2. Detección de Fraudes:
   - Notificar cada intento de fraude detectado
   - Incluir detalles del tipo de fraude

3. Turnos/Jornadas:
   - Notificar al abrir turno
   - Notificar al cerrar turno
   - Notificar si un turno lleva mucho tiempo abierto

4. Inventario:
   - Notificar cuando hay stock bajo
   - Notificar cuando se completa un inventario

5. Sistema:
   - Notificar errores críticos
   - Notificar actualizaciones
   - Notificar backups completados

TESTING:

Para probar el sistema, puedes usar la ruta de API:

POST /admin/api/notifications/test
{
    "type": "warning",
    "title": "Prueba",
    "message": "Mensaje de prueba",
    "priority": 3
}

O ejecutar la función crear_notificaciones_de_prueba() desde la consola de Python.
"""
