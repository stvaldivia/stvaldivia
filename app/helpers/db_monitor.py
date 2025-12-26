"""
Helper para monitoreo de base de datos PostgreSQL
Proporciona estadísticas detalladas de la base de datos
"""
from typing import Dict, Any, List
from flask import current_app
from app.models import db
from sqlalchemy import text


def get_database_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas completas de la base de datos PostgreSQL
    
    Returns:
        Dict con estadísticas de tamaño, conexiones, tablas, etc.
    """
    try:
        stats = {
            'database_size': get_database_size(),
            'connection_stats': get_connection_stats(),
            'table_sizes': get_table_sizes(),
            'database_info': get_database_info(),
            'index_stats': get_index_stats(),
            'connection_pool_stats': get_connection_pool_stats()
        }
        return stats
    except Exception as e:
        current_app.logger.error(f"Error al obtener estadísticas de DB: {e}", exc_info=True)
        return {
            'error': str(e),
            'message': 'Error al obtener estadísticas de base de datos'
        }


def get_database_size() -> Dict[str, Any]:
    """Obtiene el tamaño total de la base de datos"""
    try:
        query = text("""
            SELECT 
                pg_size_pretty(pg_database_size(current_database())) as size_pretty,
                pg_database_size(current_database()) as size_bytes
        """)
        result = db.session.execute(query).fetchone()
        
        return {
            'size_pretty': result[0] if result else 'N/A',
            'size_bytes': result[1] if result else 0
        }
    except Exception as e:
        current_app.logger.warning(f"Error al obtener tamaño de DB: {e}")
        return {'size_pretty': 'N/A', 'size_bytes': 0}


def get_connection_stats() -> Dict[str, Any]:
    """Obtiene estadísticas de conexiones activas"""
    try:
        # Estadísticas generales de conexiones
        query = text("""
            SELECT 
                count(*) as total_connections,
                count(*) FILTER (WHERE state = 'active') as active_connections,
                count(*) FILTER (WHERE state = 'idle') as idle_connections,
                count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                max_conn as max_connections
            FROM pg_stat_activity, 
                 (SELECT setting::int as max_conn FROM pg_settings WHERE name = 'max_connections') mc
            WHERE datname = current_database()
            GROUP BY max_conn
        """)
        result = db.session.execute(query).fetchone()
        
        if result:
            return {
                'total': result[0],
                'active': result[1],
                'idle': result[2],
                'idle_in_transaction': result[3],
                'max_connections': result[4],
                'usage_percent': round((result[0] / result[4] * 100), 2) if result[4] > 0 else 0
            }
        else:
            return {
                'total': 0,
                'active': 0,
                'idle': 0,
                'idle_in_transaction': 0,
                'max_connections': 0,
                'usage_percent': 0
            }
    except Exception as e:
        current_app.logger.warning(f"Error al obtener estadísticas de conexiones: {e}")
        return {'error': str(e)}


def get_table_sizes(limit: int = 20) -> List[Dict[str, Any]]:
    """Obtiene las tablas más grandes ordenadas por tamaño"""
    try:
        query = text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size_pretty,
                pg_total_relation_size(schemaname||'.'||tablename) as size_bytes,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size_pretty,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as indexes_size_pretty,
                (SELECT n_live_tup FROM pg_stat_user_tables WHERE schemaname = t.schemaname AND relname = t.tablename) as row_count
            FROM pg_tables t
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT :limit
        """)
        result = db.session.execute(query, {'limit': limit}).fetchall()
        
        tables = []
        for row in result:
            tables.append({
                'schema': row[0],
                'table_name': row[1],
                'total_size_pretty': row[2],
                'total_size_bytes': row[3],
                'table_size_pretty': row[4],
                'indexes_size_pretty': row[5] if row[5] else '0 bytes',
                'row_count': row[6] if row[6] is not None else 0
            })
        
        return tables
    except Exception as e:
        current_app.logger.warning(f"Error al obtener tamaños de tablas: {e}")
        return []


def get_database_info() -> Dict[str, Any]:
    """Obtiene información general de la base de datos (compatible MySQL y PostgreSQL)"""
    try:
        from flask import current_app
        db_type = current_app.config.get('DB_TYPE', 'unknown')
        
        # Versión de la base de datos (compatible MySQL y PostgreSQL)
        version_query = text("SELECT VERSION()")
        version_result = db.session.execute(version_query).fetchone()
        version = version_result[0] if version_result else 'N/A'
        
        # Extraer número de versión según tipo de BD
        import re
        if db_type == 'mysql':
            version_match = re.search(r'(\d+\.\d+\.\d+)', version)
            version_number = version_match.group(1) if version_match else 'N/A'
        else:
            # PostgreSQL o desconocido
            version_match = re.search(r'PostgreSQL (\d+\.\d+)', version)
            version_number = version_match.group(1) if version_match else 'N/A'
        
        # Nombre de la base de datos
        if db_type == 'mysql':
            db_name_query = text("SELECT DATABASE()")
        else:
            db_name_query = text("SELECT current_database()")
        db_name_result = db.session.execute(db_name_query).fetchone()
        db_name = db_name_result[0] if db_name_result else 'N/A'
        
        # Fecha de creación (solo PostgreSQL tiene pg_stat_file)
        created_date = None
        if db_type == 'postgresql':
            try:
                created_query = text("""
                    SELECT pg_stat_file('base/' || oid || '/PG_VERSION').modification
                    FROM pg_database
                    WHERE datname = current_database()
                """)
                created_result = db.session.execute(created_query).fetchone()
                created_date = created_result[0] if created_result else None
            except:
                created_date = None
        # MySQL no tiene equivalente directo, usar información del schema
        
        # Número de tablas
        if db_type == 'mysql':
            tables_count_query = text("""
                SELECT count(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
            """)
        else:
            tables_count_query = text("""
                SELECT count(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
        tables_count_result = db.session.execute(tables_count_query).fetchone()
        tables_count = tables_count_result[0] if tables_count_result else 0
        
        return {
            'version': version,
            'version_number': version_number,
            'database_name': db_name,
            'database_type': db_type,
            'created_date': created_date.isoformat() if created_date else None,
            'tables_count': tables_count
        }
    except Exception as e:
        current_app.logger.warning(f"Error al obtener info de DB: {e}")
        return {'error': str(e)}


def get_index_stats() -> Dict[str, Any]:
    """Obtiene estadísticas de índices"""
    try:
        query = text("""
            SELECT 
                count(*) as total_indexes,
                pg_size_pretty(sum(pg_relation_size(indexrelid))) as total_size_pretty,
                sum(pg_relation_size(indexrelid)) as total_size_bytes
            FROM pg_stat_user_indexes
        """)
        result = db.session.execute(query).fetchone()
        
        if result:
            return {
                'total_indexes': result[0],
                'total_size_pretty': result[1] if result[1] else '0 bytes',
                'total_size_bytes': result[2] if result[2] else 0
            }
        else:
            return {
                'total_indexes': 0,
                'total_size_pretty': '0 bytes',
                'total_size_bytes': 0
            }
    except Exception as e:
        current_app.logger.warning(f"Error al obtener estadísticas de índices: {e}")
        return {'error': str(e)}


def get_connection_pool_stats() -> Dict[str, Any]:
    """Obtiene estadísticas del pool de conexiones de SQLAlchemy"""
    try:
        engine = db.engine
        pool = engine.pool
        
        return {
            'size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'invalid': pool.invalid()
        }
    except Exception as e:
        current_app.logger.warning(f"Error al obtener estadísticas del pool: {e}")
        return {'error': str(e)}









