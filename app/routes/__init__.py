"""
Rutas modulares del sistema BIMBA

NOTA: Por ahora importamos desde el archivo routes.py del nivel superior.
Los módulos en este directorio están preparados para migración futura.
"""
# Re-exportar el blueprint desde el archivo routes.py del nivel superior
# Para evitar conflicto con este directorio, importamos desde el módulo específico
import sys
import importlib.util
import os

# Importar desde app/routes.py (archivo, no este directorio)
parent_dir = os.path.dirname(os.path.dirname(__file__))
routes_file = os.path.join(parent_dir, 'routes.py')

# Usar importlib para importar desde la ruta del archivo
spec = importlib.util.spec_from_file_location("app.routes_module", routes_file)
routes_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routes_module)

# Re-exportar el blueprint
bp = routes_module.bp

