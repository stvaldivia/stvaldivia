#!/usr/bin/env python3
"""
Script para listar todos los empleados en la base de datos
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from app.models.pos_models import Employee

def listar_empleados():
    """Lista todos los empleados en la base de datos"""
    app = create_app()
    
    with app.app_context():
        empleados = Employee.query.order_by(Employee.name).all()
        
        print(f"\n📋 Total de empleados en BD: {len(empleados)}\n")
        
        for emp in empleados:
            emp_id = str(emp.id)
            emp_name = emp.name or 'N/A'
            emp_pin = str(emp.pin) if emp.pin else 'N/A'
            emp_active = emp.is_active
            emp_deleted = emp.deleted
            emp_cashier = emp.is_cashier
            print(f"ID: {emp_id:4s} | Nombre: {emp_name:30s} | PIN: {emp_pin:10s} | Activo: {emp_active} | Eliminado: {emp_deleted} | Cajero: {emp_cashier}")
        
        # Buscar específicamente por "sebastian" o "canizarez"
        print("\n🔍 Buscando empleados con 'sebastian' o 'canizarez' en el nombre:")
        empleados_filtrados = Employee.query.filter(
            db.or_(
                Employee.name.ilike('%sebastian%'),
                Employee.name.ilike('%canizarez%')
            )
        ).all()
        
        if empleados_filtrados:
            for emp in empleados_filtrados:
                print(f"  ✅ ID: {emp.id}, Nombre: '{emp.name}', PIN: '{emp.pin}', Activo: {emp.is_active}, Eliminado: {emp.deleted}")
        else:
            print("  ❌ No se encontraron empleados con esos nombres")

if __name__ == '__main__':
    listar_empleados()

