"""
Helper para crear/actualizar caja de prueba idempotente
"""
import json
import logging
from app.models import db
from app.models.pos_models import PosRegister

logger = logging.getLogger(__name__)


def seed_test_register():
    """
    Crea o actualiza la caja de prueba TEST001 de forma idempotente
    
    Returns:
        Tuple[bool, str, PosRegister]: (success, message, register)
    """
    try:
        # Buscar caja existente por code o name
        test_register = PosRegister.query.filter(
            (PosRegister.code == 'TEST001') | (PosRegister.name == 'CAJA TEST')
        ).first()
        
        # Configuración de la caja de prueba
        test_config = {
            'name': 'CAJA TEST BIMBA',
            'code': 'TEST001',
            'location': 'TEST',
            'register_type': 'HUMANA',
            'tpv_type': 'humana',  # Legacy
            'is_active': True,
            'operational_status': 'active',
            'is_test': True,
            'payment_methods': json.dumps(['cash', 'debit', 'credit']),
            'payment_provider_primary': 'GETNET',
            'payment_provider_backup': 'KLAP',
            'fallback_policy': json.dumps({
                'enabled': True,
                'max_switch_time_seconds': 60,
                'backup_devices_required': 1,
                'trigger_events': ['pos_error', 'pos_offline']
            }),
            'provider_config': json.dumps({
                'note': 'TEST REGISTER - no usar en operación real',
                'GETNET': {
                    'mode': 'manual',
                    'note': 'Pago manual confirmado'
                },
                'KLAP': {
                    'merchant_id': 'TEST-KLAP',
                    'note': 'Backup para pruebas'
                }
            })
        }
        
        if test_register:
            # Actualizar caja existente
            logger.info(f"✅ Actualizando caja de prueba existente: {test_register.id}")
            
            test_register.name = test_config['name']
            test_register.code = test_config['code']
            test_register.location = test_config['location']
            test_register.register_type = test_config['register_type']
            test_register.tpv_type = test_config['tpv_type']
            test_register.is_active = test_config['is_active']
            test_register.operational_status = test_config['operational_status']
            test_register.is_test = test_config['is_test']
            test_register.payment_methods = test_config['payment_methods']
            test_register.payment_provider_primary = test_config['payment_provider_primary']
            test_register.payment_provider_backup = test_config['payment_provider_backup']
            test_register.fallback_policy = test_config['fallback_policy']
            test_register.provider_config = test_config['provider_config']
            test_register.updated_at = db.func.now()
            
            db.session.commit()
            
            return True, f"Caja de prueba actualizada: {test_register.name} (ID: {test_register.id})", test_register
        
        else:
            # Crear nueva caja de prueba
            logger.info("✅ Creando nueva caja de prueba")
            
            new_register = PosRegister(
                name=test_config['name'],
                code=test_config['code'],
                location=test_config['location'],
                register_type=test_config['register_type'],
                tpv_type=test_config['tpv_type'],
                is_active=test_config['is_active'],
                operational_status=test_config['operational_status'],
                is_test=test_config['is_test'],
                payment_methods=test_config['payment_methods'],
                payment_provider_primary=test_config['payment_provider_primary'],
                payment_provider_backup=test_config['payment_provider_backup'],
                fallback_policy=test_config['fallback_policy'],
                provider_config=test_config['provider_config'],
                superadmin_only=False,  # Permitir acceso normal para pruebas
                max_concurrent_sessions=1,
                requires_cash_count=True
            )
            
            db.session.add(new_register)
            db.session.commit()
            
            logger.info(f"✅ Caja de prueba creada: {new_register.id}")
            
            return True, f"Caja de prueba creada: {new_register.name} (ID: {new_register.id})", new_register
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al crear/actualizar caja de prueba: {e}", exc_info=True)
        return False, f"Error: {str(e)}", None

