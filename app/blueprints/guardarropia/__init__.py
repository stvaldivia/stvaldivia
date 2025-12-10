"""
Blueprint para la gestión de Guardarropía
Módulo para gestionar el guardado y retiro de prendas/abrigos de clientes
"""
from flask import Blueprint

guardarropia_bp = Blueprint('guardarropia', __name__, url_prefix='/admin/guardarropia', template_folder='templates')

from . import routes




