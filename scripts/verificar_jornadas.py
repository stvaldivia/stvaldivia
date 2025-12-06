#!/usr/bin/env python3
"""
Script para verificar jornadas en la base de datos
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.jornada_models import Jornada
from app.models import db

def verificar_jornadas():
    """Verifica todas las jornadas en la BD"""
    app = create_app()
    
    with app.app_context():
        # Obtener todas las jornadas ordenadas por fecha
        jornadas = Jornada.query.order_by(Jornada.fecha_jornada.desc(), Jornada.creado_en.desc()).limit(10).all()
        
        print(f"\n📋 Total de jornadas encontradas: {len(jornadas)}\n")
        
        for jornada in jornadas:
            print(f"ID: {jornada.id}")
            print(f"  Fecha: {jornada.fecha_jornada}")
            print(f"  Estado: {jornada.estado_apertura}")
            print(f"  Nombre Fiesta: {jornada.nombre_fiesta}")
            print(f"  Abierto por: {jornada.abierto_por}")
            print(f"  Abierto en: {jornada.abierto_en}")
            print(f"  Creado en: {jornada.creado_en}")
            print()
        
        # Buscar jornadas abiertas específicamente
        jornadas_abiertas = Jornada.query.filter_by(estado_apertura='abierto').all()
        print(f"\n🔓 Jornadas ABIERTAS: {len(jornadas_abiertas)}\n")
        
        if jornadas_abiertas:
            for jornada in jornadas_abiertas:
                print(f"✅ Jornada ABIERTA:")
                print(f"   ID: {jornada.id}")
                print(f"   Fecha: {jornada.fecha_jornada}")
                print(f"   Nombre: {jornada.nombre_fiesta}")
                print(f"   Abierto por: {jornada.abierto_por}")
                print(f"   Abierto en: {jornada.abierto_en}")
        else:
            print("⚠️  No hay jornadas abiertas en la base de datos")
            print("\n💡 Posibles razones:")
            print("   - El turno se cerró")
            print("   - El estado cambió a 'cerrado' o 'preparando'")
            print("   - Hubo un problema al guardar")

if __name__ == '__main__':
    verificar_jornadas()

