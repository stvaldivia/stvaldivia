"""
Rutas de la Página Principal
"""
from flask import Blueprint, render_template

home_bp = Blueprint('home', __name__)


@home_bp.route('/', methods=['GET', 'POST'])
def index():
    """Página principal - siempre muestra página de inicio"""
    # Siempre mostrar la página de inicio, sin redirecciones automáticas
    return render_template('home.html')














