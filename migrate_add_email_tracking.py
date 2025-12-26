#!/usr/bin/env python3
"""
Migración: Agregar campos de seguimiento de email a la tabla entradas
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Verificar si las columnas ya existen
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('entradas')]
        
        if 'email_resumen_enviado' not in columns:
            print("Agregando columna email_resumen_enviado...")
            db.session.execute(text("""
                ALTER TABLE entradas 
                ADD COLUMN email_resumen_enviado BOOLEAN DEFAULT 0 NOT NULL
            """))
            db.session.commit()
            print("✅ Columna email_resumen_enviado agregada")
        else:
            print("✅ Columna email_resumen_enviado ya existe")
        
        if 'email_resumen_enviado_at' not in columns:
            print("Agregando columna email_resumen_enviado_at...")
            db.session.execute(text("""
                ALTER TABLE entradas 
                ADD COLUMN email_resumen_enviado_at DATETIME
            """))
            db.session.commit()
            print("✅ Columna email_resumen_enviado_at agregada")
        else:
            print("✅ Columna email_resumen_enviado_at ya existe")
        
        # Crear índice para búsquedas rápidas
        try:
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_entradas_email_enviado 
                ON entradas(email_resumen_enviado)
            """))
            db.session.commit()
            print("✅ Índice creado")
        except Exception as idx_error:
            print(f"⚠️ Índice ya existe o error: {idx_error}")
        
        print("\n✅ Migración completada exitosamente")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error en migración: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

