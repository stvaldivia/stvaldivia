"""
Modelos de base de datos para el POS propio
Sistema de gestión propio - ventas locales + sincronización con PHP POS
"""
from datetime import datetime
from . import db
from sqlalchemy import Numeric, Text, Index
import json


class PosSession(db.Model):
    """Sesión activa del POS (carrito temporal)"""
    __tablename__ = 'pos_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), nullable=False, index=True)
    employee_name = db.Column(db.String(200), nullable=False)
    register_id = db.Column(db.String(50), nullable=True, index=True)
    register_name = db.Column(db.String(200), nullable=True)
    
    # Carrito temporal (JSON)
    cart_items = db.Column(Text, nullable=True)  # JSON string
    
    # Estado
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Índice compuesto para búsquedas activas
    __table_args__ = (
        Index('idx_pos_sessions_active_register', 'is_active', 'register_id'),
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee_name,
            'register_id': self.register_id,
            'register_name': self.register_name,
            'cart_items': json.loads(self.cart_items) if self.cart_items else [],
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PosSaleBackup(db.Model):
    """Respaldo de ventas eliminadas/respaldadas del POS"""
    __tablename__ = 'pos_sales_backup'
    
    id = db.Column(db.Integer, primary_key=True)
    original_sale_id = db.Column(db.Integer, nullable=False, index=True)  # ID original de la venta
    sale_id_phppos = db.Column(db.String(50), nullable=True, index=True)
    total_amount = db.Column(Numeric(10, 2), nullable=False)
    payment_type = db.Column(db.String(50), nullable=False)
    payment_cash = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    payment_debit = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    payment_credit = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    employee_id = db.Column(db.String(50), nullable=False, index=True)
    employee_name = db.Column(db.String(200), nullable=False)
    register_id = db.Column(db.String(50), nullable=False, index=True)
    register_name = db.Column(db.String(200), nullable=False)
    shift_date = db.Column(db.String(50), nullable=True, index=True)
    synced_to_phppos = db.Column(db.Boolean, default=False, nullable=False)
    
    # Información del respaldo
    backed_up_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    backed_up_by = db.Column(db.String(200), nullable=True)  # Usuario que hizo el respaldo
    backup_reason = db.Column(db.String(500), nullable=True)  # Razón del respaldo (ej: "Limpieza de cajas")
    
    # Timestamp original de la venta
    original_created_at = db.Column(db.DateTime, nullable=False)
    
    # Relación con items de respaldo
    items = db.relationship('PosSaleItemBackup', backref='sale_backup', lazy=True, cascade='all, delete-orphan')
    
    # Índices
    __table_args__ = (
        Index('idx_pos_sales_backup_shift_date', 'shift_date'),
        Index('idx_pos_sales_backup_backed_up_at', 'backed_up_at'),
        Index('idx_pos_sales_backup_register_date', 'register_id', 'shift_date'),
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'original_sale_id': self.original_sale_id,
            'sale_id_phppos': self.sale_id_phppos,
            'total_amount': float(self.total_amount) if self.total_amount else 0.0,
            'payment_type': self.payment_type,
            'payment_cash': float(self.payment_cash) if self.payment_cash else 0.0,
            'payment_debit': float(self.payment_debit) if self.payment_debit else 0.0,
            'payment_credit': float(self.payment_credit) if self.payment_credit else 0.0,
            'employee_id': self.employee_id,
            'employee_name': self.employee_name,
            'register_id': self.register_id,
            'register_name': self.register_name,
            'shift_date': self.shift_date,
            'synced_to_phppos': self.synced_to_phppos,
            'backed_up_at': self.backed_up_at.isoformat() if self.backed_up_at else None,
            'backed_up_by': self.backed_up_by,
            'backup_reason': self.backup_reason,
            'original_created_at': self.original_created_at.isoformat() if self.original_created_at else None,
            'items': [item.to_dict() for item in self.items] if self.items else []
        }


class PosSaleItemBackup(db.Model):
    """Item de una venta respaldada"""
    __tablename__ = 'pos_sale_items_backup'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_backup_id = db.Column(db.Integer, db.ForeignKey('pos_sales_backup.id'), nullable=False, index=True)
    original_item_id = db.Column(db.Integer, nullable=False)  # ID original del item
    product_id = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(Numeric(10, 2), nullable=False)
    subtotal = db.Column(Numeric(10, 2), nullable=False)
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'sale_backup_id': self.sale_backup_id,
            'original_item_id': self.original_item_id,
            'product_id': self.product_id,
            'product_name': self.product_name,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price) if self.unit_price else 0.0,
            'subtotal': float(self.subtotal) if self.subtotal else 0.0
        }


class PosSale(db.Model):
    """Venta realizada en el POS (guardada localmente)"""
    __tablename__ = 'pos_sales'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id_phppos = db.Column(db.String(50), unique=True, nullable=True, index=True)  # ID de PHP POS si se sincronizó
    total_amount = db.Column(Numeric(10, 2), nullable=False)
    payment_type = db.Column(db.String(50), nullable=False, index=True)  # Efectivo, Débito, Crédito
    payment_cash = db.Column(Numeric(10, 2), default=0.0, nullable=False)  # Monto en efectivo
    payment_debit = db.Column(Numeric(10, 2), default=0.0, nullable=False)  # Monto en débito
    payment_credit = db.Column(Numeric(10, 2), default=0.0, nullable=False)  # Monto en crédito
    employee_id = db.Column(db.String(50), nullable=False, index=True)
    employee_name = db.Column(db.String(200), nullable=False)
    register_id = db.Column(db.String(50), nullable=False, index=True)
    register_name = db.Column(db.String(200), nullable=False)
    
    # Datos adicionales
    shift_date = db.Column(db.String(50), nullable=True, index=True)
    synced_to_phppos = db.Column(db.Boolean, default=False, nullable=False, index=True)  # Si se sincronizó a PHP POS
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relación con items - eager loading por defecto para evitar N+1 queries
    items = db.relationship('PosSaleItem', backref='sale', lazy='joined', cascade='all, delete-orphan')
    
    # Índices compuestos para consultas comunes
    __table_args__ = (
        Index('idx_pos_sales_register_date', 'register_id', 'shift_date'),
        Index('idx_pos_sales_employee_date', 'employee_id', 'shift_date'),
        Index('idx_pos_sales_created_at', 'created_at'),
        Index('idx_pos_sales_shift_date', 'shift_date'),  # Para consultas por turno
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'sale_id_phppos': self.sale_id_phppos,
            'total_amount': float(self.total_amount) if self.total_amount else 0.0,
            'payment_type': self.payment_type,
            'payment_cash': float(self.payment_cash) if self.payment_cash else 0.0,
            'payment_debit': float(self.payment_debit) if self.payment_debit else 0.0,
            'payment_credit': float(self.payment_credit) if self.payment_credit else 0.0,
            'employee_id': self.employee_id,
            'employee_name': self.employee_name,
            'register_id': self.register_id,
            'register_name': self.register_name,
            'shift_date': self.shift_date,
            'synced_to_phppos': self.synced_to_phppos,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'items': [item.to_dict() for item in self.items] if self.items else []
        }


class PosSaleItem(db.Model):
    """Item de una venta"""
    __tablename__ = 'pos_sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('pos_sales.id'), nullable=False, index=True)
    product_id = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(Numeric(10, 2), nullable=False)
    subtotal = db.Column(Numeric(10, 2), nullable=False)
    
    # Índice compuesto para búsquedas por producto
    __table_args__ = (
        Index('idx_pos_sale_items_product', 'product_id', 'sale_id'),
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product_name,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price) if self.unit_price else 0.0,
            'subtotal': float(self.subtotal) if self.subtotal else 0.0
        }


class RegisterLock(db.Model):
    """Bloqueo de caja por usuario"""
    __tablename__ = 'register_locks'
    
    register_id = db.Column(db.String(50), primary_key=True)
    employee_id = db.Column(db.String(50), nullable=False)
    employee_name = db.Column(db.String(200), nullable=False)
    session_id = db.Column(db.String(200), nullable=True)
    locked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # Timeout automático
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'register_id': self.register_id,
            'employee_id': self.employee_id,
            'employee_name': self.employee_name,
            'session_id': self.session_id,
            'locked_at': self.locked_at.isoformat() if self.locked_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }


class RegisterClose(db.Model):
    """Cierre de caja (guardado en base de datos)"""
    __tablename__ = 'register_closes'
    
    id = db.Column(db.Integer, primary_key=True)
    register_id = db.Column(db.String(50), nullable=False)
    register_name = db.Column(db.String(200), nullable=False)
    employee_id = db.Column(db.String(50), nullable=False)
    employee_name = db.Column(db.String(200), nullable=False)
    
    # Fechas
    shift_date = db.Column(db.String(50), nullable=True)
    opened_at = db.Column(db.String(200), nullable=True)
    closed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Totales esperados
    expected_cash = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    expected_debit = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    expected_credit = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    
    # Totales reales
    actual_cash = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    actual_debit = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    actual_credit = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    
    # Diferencias
    diff_cash = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    diff_debit = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    diff_credit = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    difference_total = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    
    # Estadísticas
    total_sales = db.Column(db.Integer, default=0, nullable=False)
    total_amount = db.Column(Numeric(10, 2), default=0.0, nullable=False)
    
    # Notas y resolución
    notes = db.Column(Text, nullable=True)
    status = db.Column(db.String(50), default='pending', nullable=False)  # pending, balanced, resolved
    resolved_by = db.Column(db.String(200), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Índices para mejor rendimiento
    __table_args__ = (
        Index('idx_register_closes_status', 'status'),
        Index('idx_register_closes_register_id', 'register_id'),
        Index('idx_register_closes_closed_at', 'closed_at'),
        Index('idx_register_closes_employee_id', 'employee_id'),
        Index('idx_register_closes_shift_date', 'shift_date'),  # Para consultas por turno
        Index('idx_register_closes_date_status', 'shift_date', 'status'),  # Índice compuesto para consultas frecuentes
    )
    
    def calculate_total_amount(self):
        """Calcula el total_amount como suma de montos reales si es 0"""
        if self.total_amount == 0:
            actual_cash = float(self.actual_cash or 0)
            actual_debit = float(self.actual_debit or 0)
            actual_credit = float(self.actual_credit or 0)
            total_recaudado = actual_cash + actual_debit + actual_credit
            if total_recaudado > 0:
                self.total_amount = total_recaudado
                return total_recaudado
        return float(self.total_amount or 0)
    
    def calculate_difference_total(self):
        """Calcula difference_total como suma de diferencias individuales si es 0"""
        if self.difference_total == 0:
            diff_cash = float(self.diff_cash or 0)
            diff_debit = float(self.diff_debit or 0)
            diff_credit = float(self.diff_credit or 0)
            total_diff = diff_cash + diff_debit + diff_credit
            if total_diff != 0:
                self.difference_total = total_diff
                return total_diff
        return float(self.difference_total or 0)
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        # Asegurar que los totales estén calculados
        self.calculate_total_amount()
        self.calculate_difference_total()
        
        return {
            'id': self.id,
            'register_id': self.register_id,
            'register_name': self.register_name,
            'employee_id': self.employee_id,
            'employee_name': self.employee_name,
            'shift_date': self.shift_date,
            'opened_at': self.opened_at,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'expected_cash': float(self.expected_cash) if self.expected_cash else 0.0,
            'expected_debit': float(self.expected_debit) if self.expected_debit else 0.0,
            'expected_credit': float(self.expected_credit) if self.expected_credit else 0.0,
            'actual_cash': float(self.actual_cash) if self.actual_cash else 0.0,
            'actual_debit': float(self.actual_debit) if self.actual_debit else 0.0,
            'actual_credit': float(self.actual_credit) if self.actual_credit else 0.0,
            'diff_cash': float(self.diff_cash) if self.diff_cash else 0.0,
            'diff_debit': float(self.diff_debit) if self.diff_debit else 0.0,
            'diff_credit': float(self.diff_credit) if self.diff_credit else 0.0,
            'difference_total': float(self.difference_total) if self.difference_total else 0.0,
            'total_sales': self.total_sales,
            'total_amount': float(self.total_amount) if self.total_amount else 0.0,
            'notes': self.notes,
            'status': self.status,
            'resolved_by': self.resolved_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_notes': self.resolution_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Employee(db.Model):
    """
    Empleado almacenado localmente.
    
    IMPORTANTE: El campo 'id' es único e INMUTABLE.
    - Se genera automáticamente como número secuencial simple (1, 2, 3, ...) para nuevos trabajadores
    - Los IDs antiguos pueden ser UUIDs (compatibilidad hacia atrás)
    - Nunca se puede cambiar, incluso si el trabajador vuelve a trabajar en el futuro
    - Permite mantener un historial completo del trabajador a través del tiempo
    - Si un trabajador vuelve después de un tiempo, se puede buscar por su ID único
    """
    __tablename__ = 'employees'
    
    id = db.Column(db.String(50), primary_key=True)  # ID único e inmutable - número simple (1, 2, 3...) o UUID (legacy)
    person_id = db.Column(db.String(50), nullable=True, index=True)
    employee_id = db.Column(db.String(50), nullable=True, index=True)
    
    # Información básica
    first_name = db.Column(db.String(200), nullable=True)
    last_name = db.Column(db.String(200), nullable=True)
    name = db.Column(db.String(400), nullable=False)  # Nombre completo
    
    # Información de autenticación
    pin = db.Column(db.String(50), nullable=True)  # PIN desde custom_fields.Pin
    
    # Campos personalizados (JSON)
    custom_fields = db.Column(Text, nullable=True)  # JSON string con custom_fields de PHP POS
    
    # Información bancaria para transferencias
    rut = db.Column(db.String(20), nullable=True)  # RUT del trabajador
    banco = db.Column(db.String(100), nullable=True)  # Nombre del banco
    tipo_cuenta = db.Column(db.String(20), nullable=True)  # 'Corriente', 'Ahorro', 'Vista'
    numero_cuenta = db.Column(db.String(50), nullable=True)  # Número de cuenta bancaria
    email = db.Column(db.String(200), nullable=True)  # Email para notificaciones
    
    # Filtros
    cargo = db.Column(db.String(100), nullable=True, index=True)  # 'Cajero', 'Bartender', etc.
    is_bartender = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_cashier = db.Column(db.Boolean, default=False, nullable=False, index=True)
    
    # Estado
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    deleted = db.Column(db.String(10), default='0', nullable=False)  # '0' o '1' desde PHP POS
    
    # Sincronización
    last_synced_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    synced_from_phppos = db.Column(db.Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Índices compuestos para búsquedas comunes
    __table_args__ = (
        Index('idx_employees_cargo_active', 'cargo', 'is_active'),
        Index('idx_employees_bartender', 'is_bartender', 'is_active'),
        Index('idx_employees_cashier', 'is_cashier', 'is_active'),
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        custom_fields_dict = {}
        if self.custom_fields:
            try:
                custom_fields_dict = json.loads(self.custom_fields)
            except:
                pass
        
        return {
            'id': self.id,
            'person_id': self.person_id,
            'employee_id': self.employee_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'name': self.name,
            'pin': self.pin,
            'custom_fields': custom_fields_dict,
            'cargo': self.cargo,
            'is_bartender': self.is_bartender,
            'is_cashier': self.is_cashier,
            'is_active': self.is_active,
            'deleted': self.deleted,
            'last_synced_at': self.last_synced_at.isoformat() if self.last_synced_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
