"""
Rutas administrativas para Ecommerce - Gestión de compras y compradores
"""
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash, Response
from app.models.ecommerce_models import Entrada, CheckoutSession
from app.models.programacion_models import ProgramacionEvento
from app.models import db
from app.helpers.export_utils import DataExporter
from sqlalchemy import func, desc
from datetime import datetime

admin_ecommerce_bp = Blueprint('admin_ecommerce', __name__, url_prefix='/admin/ecommerce')


def require_admin():
    """Verifica que el usuario esté autenticado como admin"""
    if not session.get('admin_logged_in'):
        flash('Debes iniciar sesión como administrador', 'error')
        return redirect(url_for('auth.login_admin'))
    return None


def _build_compras_query():
    """Construye la query de compras aplicando los filtros de la request"""
    # Obtener parámetros de filtrado
    evento_nombre = request.args.get('evento', '')
    estado_pago = request.args.get('estado', 'pagado')
    search = request.args.get('search', '')
    
    # Construir query base
    query = Entrada.query
    
    # Filtrar por estado de pago
    if estado_pago:
        query = query.filter_by(estado_pago=estado_pago)
    else:
        query = query.filter_by(estado_pago='pagado')
    
    # Filtrar por evento
    if evento_nombre:
        query = query.filter(Entrada.evento_nombre.ilike(f'%{evento_nombre}%'))
    
    # Buscar por nombre, email o ticket_code
    if search:
        search_filter = db.or_(
            Entrada.comprador_nombre.ilike(f'%{search}%'),
            Entrada.comprador_email.ilike(f'%{search}%'),
            Entrada.ticket_code.ilike(f'%{search}%')
        )
        query = query.filter(search_filter)
    
    # Ordenar por fecha de pago descendente
    query = query.order_by(desc(Entrada.paid_at))
    
    return query


@admin_ecommerce_bp.route('/compras')
def list_compras():
    """Lista de compradores y compras del ecommerce"""
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    # Obtener parámetros de filtrado
    evento_nombre = request.args.get('evento', '')
    estado_pago = request.args.get('estado', 'pagado')
    search = request.args.get('search', '')
    
    # Construir query usando la función auxiliar
    query = _build_compras_query()
    compras = query.all()
    
    # Obtener estadísticas de cupos por evento
    eventos_stats = {}
    eventos = ProgramacionEvento.query.filter(
        ProgramacionEvento.aforo_objetivo.isnot(None)
    ).all()
    
    for evento in eventos:
        entradas_vendidas = db.session.query(
            func.sum(Entrada.cantidad)
        ).filter(
            Entrada.evento_nombre == evento.nombre_evento,
            Entrada.estado_pago == 'pagado'
        ).scalar() or 0
        
        cupos_disponibles = max(0, evento.aforo_objetivo - entradas_vendidas)
        
        eventos_stats[evento.nombre_evento] = {
            'total': evento.aforo_objetivo,
            'vendidos': int(entradas_vendidas),
            'disponibles': int(cupos_disponibles),
            'porcentaje': round((entradas_vendidas / evento.aforo_objetivo * 100), 1) if evento.aforo_objetivo > 0 else 0
        }
    
    # Estadísticas generales
    total_compras = Entrada.query.filter_by(estado_pago='pagado').count()
    total_recaudado = db.session.query(
        func.sum(Entrada.precio_total)
    ).filter_by(estado_pago='pagado').scalar() or 0
    
    # Obtener lista de eventos únicos para el filtro
    eventos_disponibles = db.session.query(
        Entrada.evento_nombre
    ).distinct().order_by(Entrada.evento_nombre).all()
    eventos_list = [e[0] for e in eventos_disponibles]
    
    return render_template('admin/ecommerce_compras.html',
                         compras=compras,
                         eventos_stats=eventos_stats,
                         total_compras=total_compras,
                         total_recaudado=float(total_recaudado),
                         eventos_list=eventos_list,
                         filtro_evento=evento_nombre,
                         filtro_estado=estado_pago,
                         filtro_search=search)


@admin_ecommerce_bp.route('/api/stats')
def api_stats():
    """API: Estadísticas de compras del ecommerce"""
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    # Estadísticas generales
    total_compras = Entrada.query.filter_by(estado_pago='pagado').count()
    total_recaudado = db.session.query(
        func.sum(Entrada.precio_total)
    ).filter_by(estado_pago='pagado').scalar() or 0
    
    # Estadísticas por evento
    eventos_stats = {}
    eventos = ProgramacionEvento.query.filter(
        ProgramacionEvento.aforo_objetivo.isnot(None)
    ).all()
    
    for evento in eventos:
        entradas_vendidas = db.session.query(
            func.sum(Entrada.cantidad)
        ).filter(
            Entrada.evento_nombre == evento.nombre_evento,
            Entrada.estado_pago == 'pagado'
        ).scalar() or 0
        
        cupos_disponibles = max(0, evento.aforo_objetivo - entradas_vendidas)
        
        eventos_stats[evento.nombre_evento] = {
            'total': evento.aforo_objetivo,
            'vendidos': int(entradas_vendidas),
            'disponibles': int(cupos_disponibles),
            'porcentaje': round((entradas_vendidas / evento.aforo_objetivo * 100), 1) if evento.aforo_objetivo > 0 else 0
        }
    
    return jsonify({
        'total_compras': total_compras,
        'total_recaudado': float(total_recaudado),
        'eventos_stats': eventos_stats
    })


@admin_ecommerce_bp.route('/compras/export')
def export_compras():
    """Exporta las compras del ecommerce a CSV"""
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    try:
        # Construir query usando la función auxiliar
        query = _build_compras_query()
        compras = query.all()
        
        if not compras:
            flash('No hay compras para exportar con los filtros seleccionados', 'warning')
            return redirect(url_for('admin_ecommerce.list_compras'))
        
        # Preparar datos para exportación
        export_data = []
        for compra in compras:
            export_data.append({
                'Ticket Code': compra.ticket_code,
                'Comprador': compra.comprador_nombre,
                'Email': compra.comprador_email,
                'RUT': compra.comprador_rut or '',
                'Teléfono': compra.comprador_telefono or '',
                'Evento': compra.evento_nombre,
                'Fecha Evento': compra.evento_fecha.strftime('%d/%m/%Y %H:%M') if compra.evento_fecha else '',
                'Lugar': compra.evento_lugar or '',
                'Cantidad': compra.cantidad,
                'Precio Unitario': float(compra.precio_unitario) if compra.precio_unitario else 0.0,
                'Precio Total': float(compra.precio_total) if compra.precio_total else 0.0,
                'Estado Pago': compra.estado_pago,
                'Método Pago': compra.metodo_pago or '',
                'GetNet Payment ID': compra.getnet_payment_id or '',
                'GetNet Transaction ID': compra.getnet_transaction_id or '',
                'GetNet Auth Code': compra.getnet_auth_code or '',
                'Fecha Creación': compra.created_at.strftime('%d/%m/%Y %H:%M:%S') if compra.created_at else '',
                'Fecha Pago': compra.paid_at.strftime('%d/%m/%Y %H:%M:%S') if compra.paid_at else '',
                'Fecha Cancelación': compra.cancelled_at.strftime('%d/%m/%Y %H:%M:%S') if compra.cancelled_at else ''
            })
        
        # Exportar usando DataExporter
        return DataExporter.export_to_csv(export_data, "compras_ecommerce")
        
    except Exception as e:
        flash(f'Error al exportar compras: {str(e)}', 'error')
        return redirect(url_for('admin_ecommerce.list_compras'))



