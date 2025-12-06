#!/usr/bin/env python3
"""
Script para verificar y corregir el PIN de un empleado en la base de datos
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from app.models.pos_models import Employee

def verificar_y_corregir_pin(nombre_empleado, pin_esperado='1234'):
    """Verifica y corrige el PIN de un empleado"""
    app = create_app()
    
    with app.app_context():
        # Buscar empleado por nombre (parcial)
        empleados = Employee.query.filter(
            Employee.name.ilike(f'%{nombre_empleado}%')
        ).all()
        
        if not empleados:
            print(f"❌ No se encontró ningún empleado con nombre que contenga '{nombre_empleado}'")
            return False
        
        if len(empleados) > 1:
            print(f"⚠️ Se encontraron {len(empleados)} empleados con nombre similar:")
            for emp in empleados:
                print(f"  - ID: {emp.id}, Nombre: {emp.name}, PIN: {emp.pin}, Activo: {emp.is_active}, Eliminado: {emp.deleted}")
            print("\nUsando el primero encontrado...")
        
        empleado = empleados[0]
        
        print(f"\n📋 Información del empleado:")
        print(f"  ID: {empleado.id}")
        print(f"  Nombre: {empleado.name}")
        print(f"  PIN actual: '{empleado.pin}' (tipo: {type(empleado.pin).__name__})")
        print(f"  Activo: {empleado.is_active}")
        print(f"  Eliminado: {empleado.deleted}")
        print(f"  Es cajero: {empleado.is_cashier}")
        
        # Verificar si el PIN es correcto
        pin_actual_str = str(empleado.pin).strip() if empleado.pin else ''
        pin_esperado_str = str(pin_esperado).strip()
        
        if pin_actual_str == pin_esperado_str:
            print(f"\n✅ El PIN ya es correcto: '{pin_actual_str}'")
        else:
            print(f"\n⚠️ El PIN no coincide:")
            print(f"  Almacenado: '{pin_actual_str}'")
            print(f"  Esperado: '{pin_esperado_str}'")
            
            # Actualizar el PIN
            empleado.pin = pin_esperado_str
            db.session.commit()
            print(f"✅ PIN actualizado a '{pin_esperado_str}'")
        
        # Verificar que esté activo
        if not empleado.is_active:
            print(f"\n⚠️ El empleado está INACTIVO. Activándolo...")
            empleado.is_active = True
            db.session.commit()
            print(f"✅ Empleado activado")
        
        # Verificar que no esté eliminado
        if empleado.deleted == '1':
            print(f"\n⚠️ El empleado está marcado como ELIMINADO. Corrigiendo...")
            empleado.deleted = None
            db.session.commit()
            print(f"✅ Empleado restaurado (deleted = None)")
        
        # Verificar que sea cajero
        if not empleado.is_cashier:
            print(f"\n⚠️ El empleado NO está marcado como CAJERO. Marcándolo como cajero...")
            empleado.is_cashier = True
            db.session.commit()
            print(f"✅ Empleado marcado como cajero")
        
        print(f"\n✅ Verificación completada. El empleado debería poder hacer login ahora.")
        return True

if __name__ == '__main__':
    nombre = 'Sebastian Canizarez' if len(sys.argv) < 2 else sys.argv[1]
    pin = '1234' if len(sys.argv) < 3 else sys.argv[2]
    
    print(f"🔍 Verificando empleado: {nombre}")
    print(f"🔐 PIN esperado: {pin}\n")
    
    verificar_y_corregir_pin(nombre, pin)

