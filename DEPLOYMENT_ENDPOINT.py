"""
Endpoint para deployment automático desde el panel de control
"""
from flask import Blueprint, jsonify, session
import subprocess
import os

# Este endpoint se agregará a routes.py

@bp.route('/admin/api/deploy', methods=['POST'])
def deploy_to_production():
    """Despliega la aplicación a Cloud Run"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    
    try:
        # Verificar que estamos en el directorio correcto
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Ejecutar deployment
        result = subprocess.run(
            ['gcloud', 'run', 'deploy', 'bimba-pos', 
             '--source', '.', 
             '--region', 'us-central1',
             '--quiet'],  # No pedir confirmación
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutos máximo
        )
        
        if result.returncode == 0:
            # Extraer información de la salida
            output = result.stdout
            revision = 'N/A'
            
            # Intentar extraer el nombre de la revisión
            for line in output.split('\n'):
                if 'revision' in line.lower() and 'has been deployed' in line.lower():
                    parts = line.split('[')
                    if len(parts) > 1:
                        revision = parts[1].split(']')[0]
                    break
            
            return jsonify({
                'success': True,
                'message': 'Deployment iniciado correctamente. El sitio se actualizará en 2-3 minutos.',
                'revision': revision
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Error en deployment: {result.stderr[:200]}'
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Timeout: El deployment tomó más de 5 minutos'
        }), 500
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': 'gcloud CLI no está instalado o no está en el PATH'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error inesperado: {str(e)}'
        }), 500
