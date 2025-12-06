
import os
from flask import Flask
from flask_socketio import SocketIO
from dotenv import load_dotenv
from datetime import datetime
import pytz

# Configurar zona horaria de Chile
CHILE_TZ = pytz.timezone('America/Santiago')

# Caché en memoria para context processor (optimización)
_cache = {}
_cache_ttl = 60  # 60 segundos
_last_cache_update = None

def get_cached_shift_info():
    global _cache, _last_cache_update
    from datetime import datetime
    now = datetime.now()
    if _last_cache_update and (now - _last_cache_update).seconds < _cache_ttl:
        return _cache.get('shift_info')
    return None

def set_cached_shift_info(shift_info):
    global _cache, _last_cache_update
    from datetime import datetime
    _cache['shift_info'] = shift_info
    _last_cache_update = datetime.now()

def invalidate_shift_cache():
    global _cache, _last_cache_update
    _cache.pop('shift_info', None)
    _last_cache_update = None


socketio = SocketIO(cors_allowed_origins="*")

def create_app():
    # Cargar variables de entorno
    # Intentar cargar desde diferentes ubicaciones posibles
    env_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),  # Raíz del proyecto
        '/var/www/flask_app/.env',  # Servidor producción común
        os.path.expanduser('~/.env'),  # Home del usuario
        '.env'  # Directorio actual
    ]
    
    env_loaded = False
    for env_path in env_paths:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            env_loaded = True
            app_logger = None
            try:
                from flask import current_app
                if current_app:
                    app_logger = current_app.logger
            except:
                import logging
                app_logger = logging.getLogger(__name__)
            if app_logger:
                app_logger.info(f"✅ Variables de entorno cargadas desde: {env_path}")
            break
    
    # Si no se encontró ningún .env, intentar cargar desde el directorio actual
    if not env_loaded:
        load_dotenv()  # Buscar en directorio actual y padres

    app = Flask(__name__)

    # Configuración
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_key')
    # MODO SOLO LOCAL: No conectarse a servicios externos
    app.config['LOCAL_ONLY'] = os.environ.get('LOCAL_ONLY', 'true').lower() == 'true'
    if app.config['LOCAL_ONLY']:
        app.config['API_KEY'] = None  # No usar API externa
        app.config['BASE_API_URL'] = None  # No conectar a API externa
    else:
        app.config['API_KEY'] = os.environ.get('API_KEY')
        app.config['BASE_API_URL'] = os.environ.get('BASE_API_URL', "https://clubbb.phppointofsale.com/index.php/api/v1")
    app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD')
    
    # Configuración Flask
    app.config['FLASK_ENV'] = os.environ.get('FLASK_ENV', 'development')
    app.config['FLASK_DEBUG'] = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Configuración de zona horaria
    app.config['TIMEZONE'] = 'America/Santiago'
    app.config['CHILE_TZ'] = CHILE_TZ
    
    # Configuración GetNet POS Integrado
    # Puede configurarse independientemente del modo local
    app.config['GETNET_ENABLED'] = os.environ.get('GETNET_ENABLED', 'false').lower() == 'true'
    
    if app.config['GETNET_ENABLED']:
        # Si no está configurado, usar el mismo host del servidor Flask
        getnet_host = os.environ.get('GETNET_SERVER_HOST', 'localhost')
        if getnet_host == 'localhost':
            # Si es localhost, intentar usar el host del request (será reemplazado por el navegador)
            getnet_host = 'localhost'
        app.config['GETNET_SERVER_HOST'] = getnet_host
        app.config['GETNET_SERVER_PORT'] = int(os.environ.get('GETNET_SERVER_PORT', 8020))
    else:
        app.config['GETNET_SERVER_HOST'] = None
        app.config['GETNET_SERVER_PORT'] = None
    
    # Configuración de OpenAI para Agente de Redes Sociales
    # Puede configurarse independientemente del modo local
    app.config['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY')
    app.config['OPENAI_ORGANIZATION_ID'] = os.environ.get('OPENAI_ORGANIZATION_ID')
    app.config['OPENAI_PROJECT_ID'] = os.environ.get('OPENAI_PROJECT_ID')
    app.config['OPENAI_DEFAULT_MODEL'] = os.environ.get('OPENAI_DEFAULT_MODEL')
    app.config['OPENAI_DEFAULT_TEMPERATURE'] = float(os.environ.get('OPENAI_DEFAULT_TEMPERATURE', '0.7'))

    # Configuración de logs - ahora se guarda en base de datos
    instance_path = os.path.abspath(app.instance_path)  # Asegurar ruta absoluta
    os.makedirs(instance_path, exist_ok=True)
    # Mantener LOG_FILE para compatibilidad, pero ya no se usa (todo va a BD)
    app.config['LOG_FILE'] = os.path.join(instance_path, 'logs.csv')
    app.config['INSTANCE_PATH'] = instance_path

    # Configuración de base de datos para BIMBA System
    # Nota: "kiosko" es solo un módulo de la aplicación, no el nombre principal
    # Usar SQLite por defecto, pero se puede cambiar a PostgreSQL/MySQL
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        # SQLite en la carpeta instance - usar ruta absoluta siempre
        # En Cloud Run, usar /tmp para evitar problemas de permisos con sistema de archivos efímero
        is_cloud_run = bool(os.environ.get('K_SERVICE') or os.environ.get('GAE_ENV') or os.environ.get('CLOUD_RUN_SERVICE'))
        
        if is_cloud_run:
            # Estamos en Cloud Run - usar /tmp que siempre es escribible
            db_dir = '/tmp'
            db_path = os.path.join(db_dir, "bimba.db")
        else:
            # Ambiente local o VM tradicional
            db_dir = instance_path
            db_path = os.path.join(db_dir, "bimba.db")
        
        # Asegurar que el directorio existe y tiene permisos correctos
        try:
            # /tmp siempre existe en Linux, solo verificar permisos si no es /tmp
            if db_dir != '/tmp':
                os.makedirs(db_dir, mode=0o755, exist_ok=True)
                # Intentar escribir en el directorio (pero no fallar si no podemos - puede que el archivo ya exista)
                try:
                    test_file = os.path.join(db_dir, '.test_write_bimba')
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                except (IOError, OSError):
                    # Si no podemos escribir, pero el archivo de BD ya existe, continuar
                    if not os.path.exists(db_path):
                        raise
        except Exception as e:
            app.logger.warning(f"⚠️ Error al preparar directorio de BD {db_dir}: {e}")
            # Solo usar /tmp como fallback si no es Cloud Run y no podemos usar instance
            if not is_cloud_run:
                app.logger.error(f"❌ No se pudo usar directorio {db_dir}, intentando con /tmp")
                db_dir = '/tmp'
                db_path = os.path.join(db_dir, "bimba.db")
        
        db_abs_path = os.path.abspath(db_path)  # Asegurar que sea absoluta
        
        # SQLite requiere 3 barras para rutas absolutas en macOS/Linux
        database_url = f'sqlite:///{db_abs_path}'
        
        app.logger.info(f"📁 Base de datos configurada en: {db_abs_path} (Cloud Run: {is_cloud_run})")
        app.logger.info(f"📁 URI de base de datos: {database_url}")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicializar SQLAlchemy
    from .models import db
    db.init_app(app)

    # Logging de configuración cargada (después de crear la app)
    env_path_used = None
    for env_path in env_paths:
        if os.path.exists(env_path):
            env_path_used = env_path
            break
    
    if env_path_used:
        app.logger.info(f"✅ Variables de entorno cargadas desde: {env_path_used}")
        app.logger.info(f"   API_KEY configurada: {'Sí' if os.environ.get('API_KEY') else 'No'}")
        app.logger.info(f"   BASE_API_URL configurada: {'Sí' if os.environ.get('BASE_API_URL') else 'No'}")
    else:
        app.logger.warning("⚠️  No se encontró archivo .env en ubicaciones estándar")
        app.logger.info(f"   API_KEY en env: {'Sí' if os.environ.get('API_KEY') else 'No'}")
        app.logger.info(f"   BASE_API_URL en env: {'Sí' if os.environ.get('BASE_API_URL') else 'No'}")

    # Inicializar SocketIO con configuración para sesiones
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        manage_session=True,  # Permitir que SocketIO gestione sesiones
        logger=True,
        engineio_logger=False
    )

    # Obtener prefijo de URL de variables de entorno
    url_prefix = os.environ.get('APPLICATION_ROOT', '')
    
    # Registrar rutas
    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp, url_prefix=url_prefix)
    
    # Registrar blueprint de encuestas
    # El blueprint ya tiene url_prefix='/encuesta' definido
    # Si APPLICATION_ROOT está configurado, combinarlo con el prefijo del blueprint
    from .survey import survey_bp
    if url_prefix:
        # Combinar APPLICATION_ROOT con el prefijo del blueprint
        combined_prefix = f"{url_prefix}/encuesta" if not url_prefix.endswith('/') else f"{url_prefix}encuesta"
        app.register_blueprint(survey_bp, url_prefix=combined_prefix)
    else:
        # Usar solo el url_prefix del blueprint (/encuesta)
        app.register_blueprint(survey_bp)
    
    # Registrar blueprint de equipo
    from .blueprints.equipo import equipo_bp
    if url_prefix:
        combined_prefix = f"{url_prefix}/admin/equipo" if not url_prefix.endswith('/') else f"{url_prefix}admin/equipo"
        app.register_blueprint(equipo_bp, url_prefix=combined_prefix)
    else:
        app.register_blueprint(equipo_bp)
    
    # Registrar blueprint de Instagram webhooks
    try:
        from .routes_instagram import instagram_bp
        app.register_blueprint(instagram_bp, url_prefix=url_prefix)
    except ImportError:
        # Si no existe el módulo, continuar sin errores (opcional)
        pass
    
    # Configuración Kiosko
    # DESACTIVADO TEMPORALMENTE - Para reactivar, cambiar KIOSK_ENABLED a True
    app.config['KIOSK_ENABLED'] = os.environ.get('KIOSK_ENABLED', 'false').lower() == 'true'
    
    # Registrar blueprint de Kiosko
    # Crear tablas de la base de datos si no existen (siempre, no solo para kiosko)
    with app.app_context():
        try:
            # Intentar crear tablas con manejo mejorado de errores
            db.create_all()
            app.logger.info("✅ Base de datos inicializada (todas las tablas)")
        except Exception as e:
            app.logger.error(f"❌ Error al inicializar base de datos: {e}", exc_info=True)
            # No fallar completamente si hay error en la BD - la app puede funcionar sin BD inicialmente
            app.logger.warning("⚠️ Continuando sin inicializar base de datos (puede causar errores en funcionalidades que la requieren)")
    
    if app.config['KIOSK_ENABLED']:
        try:
            from .blueprints.kiosk import kiosk_bp
            app.register_blueprint(kiosk_bp, url_prefix=url_prefix)
        except ImportError as e:
            app.logger.warning(f"⚠️  No se pudo registrar el blueprint del kiosko: {e}")
        except Exception as e:
            app.logger.error(f"❌ Error al registrar blueprint del kiosko: {e}")
    else:
        app.logger.info("⚠️  Kiosko desactivado")
    
    # Registrar blueprint de Caja (POS)
    try:
        from .blueprints.pos import caja_bp
        # El blueprint ya tiene url_prefix='/caja' definido
        # Si APPLICATION_ROOT está configurado, combinarlo con el prefijo del blueprint
        if url_prefix:
            # Combinar APPLICATION_ROOT con el prefijo del blueprint
            combined_prefix = f"{url_prefix}/caja" if not url_prefix.endswith('/') else f"{url_prefix}caja"
            app.register_blueprint(caja_bp, url_prefix=combined_prefix)
        else:
            # Usar solo el url_prefix del blueprint (/caja)
            app.register_blueprint(caja_bp)
        app.logger.info("✅ Blueprint de Caja registrado")
    except ImportError as e:
        app.logger.warning(f"⚠️  No se pudo registrar el blueprint de caja: {e}")
    except Exception as e:
        app.logger.error(f"❌ Error al registrar blueprint de caja: {e}")
    
    # Context processor para hacer shift_status y shift_metrics disponibles en todos los templates
    @app.context_processor
    def inject_shift_info():
        """Inyecta información del turno en todos los templates para el footer general (sistema único - Jornada)"""
        # Inyectar información de versión
        from .helpers.version import get_version_string, get_full_version_string, get_build_info
        version_info = {
            'app_version': get_version_string(),
            'app_version_full': get_full_version_string(),
            'app_build_info': get_build_info()
        }
        
        # Intentar obtener desde caché primero
        cached_info = get_cached_shift_info()
        if cached_info:
            return {
                **cached_info,
                **version_info
            }
        
        
        try:
            from .application.services.service_factory import get_stats_service
            from datetime import datetime
            from .models.jornada_models import Jornada
            
            # Usar solo sistema de Jornadas (sistema único)
            from flask import current_app
            CHILE_TZ = current_app.config.get('CHILE_TZ')
            fecha_hoy = datetime.now(CHILE_TZ).strftime('%Y-%m-%d')
            jornada_abierta = Jornada.query.filter_by(
                fecha_jornada=fecha_hoy,
                estado_apertura='abierto'
            ).first()
            
            # Si hay jornada abierta, usar esa información
            if jornada_abierta:
                shift_status_dict = {
                    'is_open': True,
                    'shift_date': jornada_abierta.fecha_jornada,
                    'opened_at': jornada_abierta.abierto_en.isoformat() if jornada_abierta.abierto_en else jornada_abierta.horario_apertura_programado,
                    'closed_at': None,
                    'fiesta_nombre': jornada_abierta.nombre_fiesta,
                    'djs': jornada_abierta.djs
                }
            else:
                shift_status_dict = {
                    'is_open': False,
                    'shift_date': fecha_hoy,
                    'opened_at': None,
                    'closed_at': None,
                    'fiesta_nombre': None,
                    'djs': None
                }
            
            shift_metrics = {}
            if shift_status_dict.get('is_open', False):
                try:
                    stats_service = get_stats_service()
                    
                    # Calcular tiempo transcurrido
                    opened_at_str = shift_status_dict.get('opened_at')
                    if opened_at_str:
                        try:
                            opened_dt = datetime.fromisoformat(opened_at_str.replace('Z', '+00:00') if 'Z' in opened_at_str else opened_at_str)
                            now = datetime.utcnow()
                            diff = now - opened_dt
                            hours = int(diff.total_seconds() // 3600)
                            minutes = int((diff.total_seconds() % 3600) // 60)
                            shift_metrics['tiempo_transcurrido'] = f"{hours}h {minutes}m"
                        except:
                            shift_metrics['tiempo_transcurrido'] = 'N/A'
                    else:
                        shift_metrics['tiempo_transcurrido'] = 'N/A'
                    
                    # Obtener estadísticas del turno
                    shift_date = shift_status_dict.get('shift_date', fecha_hoy)
                    delivery_stats = stats_service.get_delivery_stats(
                        start_date=shift_date,
                        end_date=shift_date
                    )
                    shift_metrics['total_entregas'] = delivery_stats.get('total_deliveries', 0)
                    
                    # Obtener entradas - OPTIMIZADO: No llamar a API externa en cada request
                    # Esto causaba lentitud extrema en login y navegación
                    # Se debe cargar asíncronamente o usar un valor en caché
                    shift_metrics['total_entradas'] = 0 # Placeholder para evitar bloqueo
                    
                    # TODO: Implementar carga asíncrona de entradas si es necesario
                    # from .helpers.pos_api import get_entradas_sales
                    # try:
                    #     entradas_sales = get_entradas_sales(limit=100)
                    #     shift_metrics['total_entradas'] = len([s for s in entradas_sales if s.get('sale_time', '').startswith(shift_date)])
                    # except:
                    #     shift_metrics['total_entradas'] = 0
                except Exception as e:
                    app.logger.warning(f"Error al calcular métricas del turno en context processor: {e}")
                    shift_metrics = {
                        'tiempo_transcurrido': 'N/A',
                        'total_entregas': 0,
                        'total_entradas': 0
                    }
            
            # Guardar en caché
            result = {
                'global_shift_status': shift_status_dict,
                'global_shift_metrics': shift_metrics,
                'shift_status': shift_status_dict,  # Compatibilidad
                'shift_metrics': shift_metrics,  # Compatibilidad
                **version_info
            }
            set_cached_shift_info(result)
            return result
        except Exception as e:
            app.logger.warning(f"Error en context processor de shift_info: {e}")
            return {
                'global_shift_status': {'is_open': False},
                'global_shift_metrics': {},
                'shift_status': {'is_open': False},  # Compatibilidad
                'shift_metrics': {},  # Compatibilidad
                **version_info  # Agregar información de versión incluso si hay error
            }

    # Registrar eventos de socket
    from .socketio_events import register_socketio_events
    register_socketio_events(socketio)
    
    # Configuración de Instagram/Meta Webhooks
    app.config['INSTAGRAM_VERIFY_TOKEN'] = os.environ.get('INSTAGRAM_VERIFY_TOKEN')
    app.config['INSTAGRAM_PAGE_ACCESS_TOKEN'] = os.environ.get('INSTAGRAM_PAGE_ACCESS_TOKEN')
    app.config['INSTAGRAM_BUSINESS_ACCOUNT_ID'] = os.environ.get('INSTAGRAM_BUSINESS_ACCOUNT_ID')
    app.config['META_APP_ID'] = os.environ.get('META_APP_ID')
    app.config['META_APP_SECRET'] = os.environ.get('META_APP_SECRET')

    # Registrar filtros personalizados de Jinja2
    @app.template_filter('to_datetime')
    def to_datetime_filter(value):
        """Convierte un string de fecha a objeto datetime"""
        if not value or not isinstance(value, str):
            return None
        try:
            # Intentar diferentes formatos comunes
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%fZ',
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            return None
        except Exception:
            return None
    
    @app.template_filter('currency')
    def currency_filter(value):
        """Formatea un número como moneda chilena: puntos como separador de miles, sin decimales"""
        if value is None:
            return '0'
        try:
            # Convertir a float y redondear a entero
            num = int(round(float(value)))
            # Formatear con puntos como separador de miles (formato chileno)
            return f'{num:,}'.replace(',', '.')
        except (ValueError, TypeError):
            return '0'
    
    @app.template_filter('fecha')
    def fecha_filter(value):
        """Formatea una fecha en formato día/mes/año hora:minuto (24 horas)"""
        if value is None:
            return 'N/A'
        
        try:
            # Si ya es un string con formato conocido, intentar parsearlo
            if isinstance(value, str):
                # Intentar diferentes formatos comunes
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%SZ',
                    '%Y-%m-%dT%H:%M:%S.%fZ',
                    '%Y-%m-%d',
                    '%d-%m-%Y, %I:%M %p',  # Formato que ya tenemos en algunos lugares
                    '%d/%m/%Y %H:%M:%S',
                    '%d/%m/%Y %H:%M',
                ]
                
                for fmt in formats:
                    try:
                        dt = datetime.strptime(value, fmt)
                        # Formato: DD/MM/YYYY HH:MM
                        return dt.strftime('%d/%m/%Y %H:%M')
                    except ValueError:
                        continue
                
                # Si no coincide con ningún formato, retornar el valor original
                return value
            
            # Si es un objeto datetime
            elif isinstance(value, datetime):
                return value.strftime('%d/%m/%Y %H:%M')
            
            return str(value)
            
        except Exception as e:
            # Si hay algún error, retornar el valor original o 'N/A'
            return str(value) if value else 'N/A'
    
    @app.template_filter('fecha_solo')
    def fecha_solo_filter(value):
        """Formatea una fecha en formato día/mes/año (sin hora)"""
        if value is None:
            return 'N/A'
        
        try:
            if isinstance(value, str):
                # Intentar diferentes formatos
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d',
                    '%Y-%m-%dT%H:%M:%S',
                    '%d/%m/%Y',
                    '%d-%m-%Y',
                ]
                
                for fmt in formats:
                    try:
                        dt = datetime.strptime(value.split()[0] if ' ' in value else value, fmt.split()[0] if ' ' in fmt else fmt)
                        return dt.strftime('%d/%m/%Y')
                    except (ValueError, IndexError):
                        continue
                
                return value.split()[0] if ' ' in value else value
            
            elif isinstance(value, datetime):
                return value.strftime('%d/%m/%Y')
            
            return str(value)
            
        except Exception:
            return str(value) if value else 'N/A'
    
    @app.template_filter('hora')
    def hora_filter(value):
        """Formatea solo la hora en formato 24 horas (HH:MM)"""
        if value is None:
            return 'N/A'
        
        try:
            if isinstance(value, str):
                # Intentar extraer hora de diferentes formatos
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S',
                    '%H:%M:%S',
                    '%H:%M',
                    '%d/%m/%Y %H:%M',
                ]
                
                for fmt in formats:
                    try:
                        dt = datetime.strptime(value, fmt)
                        return dt.strftime('%H:%M')
                    except ValueError:
                        continue
                
                # Intentar extraer hora manualmente si tiene formato conocido
                if ':' in value:
                    parts = value.split()
                    for part in parts:
                        if ':' in part and len(part) >= 5:
                            hora_part = part.split(':')[:2]
                            return f"{hora_part[0]}:{hora_part[1]}"
            
            elif isinstance(value, datetime):
                return value.strftime('%H:%M')
            
            return str(value)
            
        except Exception:
            return str(value) if value else 'N/A'

    # Configurar headers de seguridad
    from app.helpers.security_headers import setup_security_headers

    # Configurar headers de seguridad

    return app