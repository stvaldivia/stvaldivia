"""
Modelos de base de datos para Ecommerce - Venta de Entradas Express
"""
from datetime import datetime
from . import db
from sqlalchemy import Numeric, Text, Index, String, Boolean
import json
import uuid


class Entrada(db.Model):
    """Modelo para entradas/tickets de eventos"""
    __tablename__ = 'entradas'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_code = db.Column(String(50), unique=True, nullable=False, index=True)
    
    # Información del evento
    evento_nombre = db.Column(String(200), nullable=False)
    evento_fecha = db.Column(db.DateTime, nullable=False, index=True)
    evento_lugar = db.Column(String(200), nullable=True)
    
    # Información del comprador
    comprador_nombre = db.Column(String(200), nullable=False)
    comprador_email = db.Column(String(200), nullable=False, index=True)
    comprador_rut = db.Column(String(20), nullable=True)
    comprador_telefono = db.Column(String(20), nullable=True)
    
    # Información de la compra
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(Numeric(10, 2), nullable=False)
    precio_total = db.Column(Numeric(10, 2), nullable=False)
    
    # Estado del pago
    estado_pago = db.Column(String(50), nullable=False, default='pendiente', index=True)  # pendiente, pagado, cancelado, reembolsado
    metodo_pago = db.Column(String(50), nullable=True)  # getnet_web, getnet_link, etc.
    
    # Referencias de GetNet
    getnet_payment_id = db.Column(String(100), nullable=True, index=True)
    getnet_transaction_id = db.Column(String(100), nullable=True)
    getnet_auth_code = db.Column(String(50), nullable=True)
    
    # Información adicional
    metadata_json = db.Column(Text, nullable=True)  # JSON con información adicional
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    # Índices
    __table_args__ = (
        Index('idx_entradas_estado_fecha', 'estado_pago', 'evento_fecha'),
        Index('idx_entradas_email_estado', 'comprador_email', 'estado_pago'),
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'ticket_code': self.ticket_code,
            'evento_nombre': self.evento_nombre,
            'evento_fecha': self.evento_fecha.isoformat() if self.evento_fecha else None,
            'evento_lugar': self.evento_lugar,
            'comprador_nombre': self.comprador_nombre,
            'comprador_email': self.comprador_email,
            'comprador_rut': self.comprador_rut,
            'comprador_telefono': self.comprador_telefono,
            'cantidad': self.cantidad,
            'precio_unitario': float(self.precio_unitario) if self.precio_unitario else 0.0,
            'precio_total': float(self.precio_total) if self.precio_total else 0.0,
            'estado_pago': self.estado_pago,
            'metodo_pago': self.metodo_pago,
            'getnet_payment_id': self.getnet_payment_id,
            'getnet_transaction_id': self.getnet_transaction_id,
            'getnet_auth_code': self.getnet_auth_code,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
        }
    
    @staticmethod
    def generate_ticket_code():
        """Genera un código único para el ticket"""
        return f"ENT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


class CheckoutSession(db.Model):
    """Sesión temporal de checkout (carrito de compra)"""
    __tablename__ = 'checkout_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(String(100), unique=True, nullable=False, index=True)
    
    # Información del evento
    evento_nombre = db.Column(String(200), nullable=False)
    evento_fecha = db.Column(db.DateTime, nullable=False)
    evento_lugar = db.Column(String(200), nullable=True)
    
    # Información del comprador (temporal, se guarda en Entrada al confirmar)
    comprador_nombre = db.Column(String(200), nullable=True)
    comprador_email = db.Column(String(200), nullable=True)
    comprador_rut = db.Column(String(20), nullable=True)
    comprador_telefono = db.Column(String(20), nullable=True)
    
    # Carrito
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(Numeric(10, 2), nullable=False)
    precio_total = db.Column(Numeric(10, 2), nullable=False)
    
    # Estado
    estado = db.Column(String(50), nullable=False, default='iniciado', index=True)  # iniciado, completado, expirado
    payment_intent_id = db.Column(String(100), nullable=True, index=True)  # ID del payment intent de GetNet
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relación con entrada creada
    entrada_id = db.Column(db.Integer, db.ForeignKey('entradas.id'), nullable=True)
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'evento_nombre': self.evento_nombre,
            'evento_fecha': self.evento_fecha.isoformat() if self.evento_fecha else None,
            'evento_lugar': self.evento_lugar,
            'comprador_nombre': self.comprador_nombre,
            'comprador_email': self.comprador_email,
            'cantidad': self.cantidad,
            'precio_unitario': float(self.precio_unitario) if self.precio_unitario else 0.0,
            'precio_total': float(self.precio_total) if self.precio_total else 0.0,
            'estado': self.estado,
            'payment_intent_id': self.payment_intent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }
    
    def is_expired(self):
        """Verifica si la sesión expiró"""
        return datetime.utcnow() > self.expires_at
    
    @staticmethod
    def generate_session_id():
        """Genera un ID único para la sesión"""
        return f"CHK-{uuid.uuid4().hex}"

