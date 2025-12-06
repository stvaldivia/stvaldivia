#!/usr/bin/env python3
"""
Script para listar todos los trabajadores y sus PINs
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.pos_models import Employee

app = create_app()

with app.app_context():
    print("=" * 80)
    print("📋 LISTA DE TRABAJADORES Y SUS PINs")
    print("=" * 80)
    print()
    
    # Obtener todos los trabajadores
    employees = Employee.query.order_by(Employee.name).all()
    
    if len(employees) == 0:
        print("⚠️  No se encontraron trabajadores en la base de datos")
    else:
        print(f"Total de trabajadores: {len(employees)}")
        print()
        print("-" * 80)
        print(f"{'ID':<10} {'Nombre':<40} {'PIN':<10} {'Cargo':<15} {'Activo':<8}")
        print("-" * 80)
        
        for emp in employees:
            pin_display = emp.pin if emp.pin else "❌ Sin PIN"
            cargo_display = emp.cargo if emp.cargo else "N/A"
            activo_display = "✅ Sí" if emp.is_active else "❌ No"
            
            print(f"{str(emp.id):<10} {emp.name[:38]:<40} {pin_display:<10} {cargo_display[:13]:<15} {activo_display:<8}")
        
        print("-" * 80)
        print()
        
        # Resumen
        con_pin = sum(1 for emp in employees if emp.pin)
        sin_pin = len(employees) - con_pin
        activos = sum(1 for emp in employees if emp.is_active)
        
        print("📊 Resumen:")
        print(f"   • Total trabajadores: {len(employees)}")
        print(f"   • Con PIN configurado: {con_pin}")
        print(f"   • Sin PIN: {sin_pin}")
        print(f"   • Activos: {activos}")
        print(f"   • Inactivos: {len(employees) - activos}")
    
    print()
    print("=" * 80)

