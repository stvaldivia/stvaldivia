"""
Script para agregar empleados a la base de datos local
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.models.pos_models import Employee
from datetime import datetime

def add_employees():
    """Agrega los empleados a la base de datos local"""
    app = create_app()
    
    with app.app_context():
        try:
            # Empleados que están en producción
            employees_data = [
                {
                    'id': '1',
                    'name': 'Franco Vasquez',
                    'cargo': 'BARRA',
                    'pin': '1234',  # PIN por defecto, se puede cambiar después
                    'is_active': True,
                    'is_bartender': True,
                    'is_cashier': False
                },
                {
                    'id': '2',
                    'name': 'Haydee Manquilepe',
                    'cargo': 'ASEO',
                    'pin': '1234',
                    'is_active': True,
                    'is_bartender': False,
                    'is_cashier': False
                },
                {
                    'id': '3',
                    'name': 'Java Corona',
                    'cargo': 'COPERX',
                    'pin': '1234',
                    'is_active': True,
                    'is_bartender': True,  # COPERX es tipo barra
                    'is_cashier': False
                },
                {
                    'id': '4',
                    'name': 'Sebastian Canizarez',
                    'cargo': 'CAJA',
                    'pin': '1234',
                    'is_active': True,
                    'is_bartender': False,
                    'is_cashier': True
                }
            ]
            
            print("👥 Agregando empleados a la base de datos local...")
            print("")
            
            added = 0
            updated = 0
            
            for emp_data in employees_data:
                # Verificar si ya existe
                existing = Employee.query.filter_by(id=emp_data['id']).first()
                
                if existing:
                    # Actualizar
                    existing.name = emp_data['name']
                    existing.cargo = emp_data['cargo']
                    existing.pin = emp_data['pin']
                    existing.is_active = emp_data['is_active']
                    existing.is_bartender = emp_data['is_bartender']
                    existing.is_cashier = emp_data['is_cashier']
                    existing.updated_at = datetime.utcnow()
                    updated += 1
                    print(f"   ✏️  Actualizado: {emp_data['name']} ({emp_data['cargo']})")
                else:
                    # Crear nuevo
                    employee = Employee(
                        id=emp_data['id'],
                        name=emp_data['name'],
                        cargo=emp_data['cargo'],
                        pin=emp_data['pin'],
                        is_active=emp_data['is_active'],
                        is_bartender=emp_data['is_bartender'],
                        is_cashier=emp_data['is_cashier'],
                        synced_from_phppos=False,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.session.add(employee)
                    added += 1
                    print(f"   ✅ Agregado: {emp_data['name']} ({emp_data['cargo']})")
            
            db.session.commit()
            
            print("")
            print(f"✅ Proceso completado:")
            print(f"   - Agregados: {added}")
            print(f"   - Actualizados: {updated}")
            print(f"   - Total: {added + updated} empleados")
            print("")
            print("⚠️  Nota: Todos los empleados tienen PIN '1234' por defecto")
            print("   Puedes cambiarlos desde la interfaz web en /admin/equipo/listar")
            
            return True
            
        except Exception as e:
            print(f"❌ Error al agregar empleados: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False

if __name__ == '__main__':
    print("🚀 Iniciando agregado de empleados...")
    print("")
    success = add_employees()
    
    if success:
        print("\n✅ Empleados agregados exitosamente")
        print("   Ahora puedes verlos en: http://localhost:5001/admin/equipo/listar")
    else:
        print("\n❌ Error al agregar empleados")
        sys.exit(1)




