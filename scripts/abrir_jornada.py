#!/usr/bin/env python3
"""
Script para abrir una jornada existente
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.jornada_models import Jornada
from app.models import db
from app import CHILE_TZ

def abrir_jornada(jornada_id=None):
    """Abre una jornada existente"""
    app = create_app()
    
    with app.app_context():
        if jornada_id:
            jornada = Jornada.query.get(jornada_id)
        else:
            # Buscar la jornada más reciente en estado "preparando"
            jornada = Jornada.query.filter_by(estado_apertura='preparando').order_by(
                Jornada.fecha_jornada.desc()
            ).first()
        
        if not jornada:
            print("❌ No se encontró ninguna jornada para abrir")
            return False
        
        print(f"📋 Jornada encontrada:")
        print(f"   ID: {jornada.id}")
        print(f"   Fecha: {jornada.fecha_jornada}")
        print(f"   Estado actual: {jornada.estado_apertura}")
        print(f"   Nombre: {jornada.nombre_fiesta}")
        
        # Cambiar estado a "abierto"
        jornada.estado_apertura = 'abierto'
        jornada.abierto_en = datetime.now(CHILE_TZ)
        jornada.abierto_por = jornada.abierto_por or 'admin'
        
        db.session.commit()
        
        print(f"\n✅ Jornada abierta correctamente:")
        print(f"   Estado: {jornada.estado_apertura}")
        print(f"   Abierto en: {jornada.abierto_en}")
        print(f"   Abierto por: {jornada.abierto_por}")
        
        return True

if __name__ == '__main__':
    import sys
    jornada_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    abrir_jornada(jornada_id)

