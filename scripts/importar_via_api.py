#!/usr/bin/env python3
"""
Script para importar datos en producción vía API HTTP
Requiere autenticación de administrador
"""
import requests
import json
import sys
import os

# URL base
BASE_URL = 'https://stvaldivia.cl'

# Leer credenciales desde variables de entorno o pedirlas
username = os.environ.get('ADMIN_USERNAME', 'admin')
password = os.environ.get('ADMIN_PASSWORD', '')

if not password:
    print("⚠️  ADMIN_PASSWORD no configurado en variables de entorno")
    print("   Usando credenciales por defecto o pide al usuario")
    password = input("Contraseña de administrador: ").strip()

# Crear sesión
session = requests.Session()

print("🔐 Iniciando sesión...")
# Iniciar sesión
login_response = session.post(
    f'{BASE_URL}/login_admin',
    data={
        'username': username,
        'password': password
    },
    allow_redirects=False
)

if login_response.status_code != 302:
    print(f"❌ Error al iniciar sesión: {login_response.status_code}")
    print(f"   Respuesta: {login_response.text[:200]}")
    sys.exit(1)

print("✅ Sesión iniciada")

# Leer archivo JSON
json_file = sys.argv[1] if len(sys.argv) > 1 else 'datos_exportados.json'
if not os.path.exists(json_file):
    print(f"❌ Error: No se encontró el archivo {json_file}")
    sys.exit(1)

print(f"📦 Leyendo archivo: {json_file}")
with open(json_file, 'r', encoding='utf-8') as f:
    datos = json.load(f)

print(f"   - {len(datos.get('empleados', []))} empleados")
print(f"   - {len(datos.get('jornadas', []))} jornadas")
print(f"   - {len(datos.get('planilla', []))} registros de planilla")

# Preparar archivo para upload
files = {
    'archivo': (json_file, json.dumps(datos, ensure_ascii=False), 'application/json')
}

print("📤 Enviando datos a producción...")
import_response = session.post(
    f'{BASE_URL}/admin/importar-datos',
    files=files
)

if import_response.status_code == 200:
    print("✅ Datos importados exitosamente")
    print(f"   Respuesta: {import_response.text[:500]}")
elif import_response.status_code == 302:
    # Redirect significa éxito
    print("✅ Importación completada (redirección)")
    location = import_response.headers.get('Location', '')
    print(f"   Redirigido a: {location}")
else:
    print(f"❌ Error al importar: {import_response.status_code}")
    print(f"   Respuesta: {import_response.text[:500]}")
    sys.exit(1)

print()
print("✅ Proceso completado")
print("   Verifica en:")
print(f"   - {BASE_URL}/admin/equipo/listar (empleados)")
print(f"   - {BASE_URL}/admin/turnos (jornadas)")

