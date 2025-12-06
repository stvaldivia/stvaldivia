"""
Modelos de base de datos para el sistema de Jornadas
Gestión completa de apertura de jornada en la discoteca
"""
from datetime import datetime
from . import db
from sqlalchemy import Numeric, Text, Index
import json


class Jornada(db.Model):
    """Jornada completa de trabajo"""
    __tablename__ = 'jornadas'
    
    id = db.Column(db.Integer, primary_key=True)
    fecha_jornada = db.Column(db.String(50), nullable=False, index=True)
    tipo_turno = db.Column(db.String(50), nullable=False)  # "Noche", "Día", "Especial"
    nombre_fiesta = db.Column(db.String(200), nullable=False)
    horario_apertura_programado = db.Column(db.String(10), nullable=False)  # "20:00"
    horario_cierre_programado = db.Column(db.String(10), nullable=False)  # "04:00"
    horario_apertura_real = db.Column(db.DateTime, nullable=True)
    
    # Responsables
    responsable_cajas = db.Column(db.String(200), nullable=True)
    responsable_puerta = db.Column(db.String(200), nullable=True)
    responsable_seguridad = db.Column(db.String(200), nullable=True)
    responsable_admin = db.Column(db.String(200), nullable=True)
    
    # Estado
    estado_apertura = db.Column(db.String(50), default='preparando', nullable=False)  # preparando, revisando, listo, abierto
    checklist_tecnico = db.Column(Text, nullable=True)  # JSON
    checklist_apertura = db.Column(Text, nullable=True)  # JSON
    
    # Información adicional
    djs = db.Column(db.String(200), nullable=True)
    barras_disponibles = db.Column(Text, nullable=True)  # JSON lista
    
    # Timestamps
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    abierto_en = db.Column(db.DateTime, nullable=True)
    abierto_por = db.Column(db.String(200), nullable=True)
    
    # Índices para mejor rendimiento
    __table_args__ = (
        Index('idx_jornadas_fecha', 'fecha_jornada'),
        Index('idx_jornadas_estado', 'estado_apertura'),
    )
    
    # Relaciones
    planilla_trabajadores = db.relationship('PlanillaTrabajador', backref='jornada', lazy=True, cascade='all, delete-orphan')
    aperturas_cajas = db.relationship('AperturaCaja', backref='jornada', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'fecha_jornada': self.fecha_jornada,
            'tipo_turno': self.tipo_turno,
            'nombre_fiesta': self.nombre_fiesta,
            'horario_apertura_programado': self.horario_apertura_programado,
            'horario_cierre_programado': self.horario_cierre_programado,
            'horario_apertura_real': self.horario_apertura_real.isoformat() if self.horario_apertura_real else None,
            'responsable_cajas': self.responsable_cajas,
            'responsable_puerta': self.responsable_puerta,
            'responsable_seguridad': self.responsable_seguridad,
            'responsable_admin': self.responsable_admin,
            'estado_apertura': self.estado_apertura,
            'checklist_tecnico': json.loads(self.checklist_tecnico) if self.checklist_tecnico else {},
            'checklist_apertura': json.loads(self.checklist_apertura) if self.checklist_apertura else {},
            'djs': self.djs,
            'barras_disponibles': json.loads(self.barras_disponibles) if self.barras_disponibles else [],
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
            'abierto_en': self.abierto_en.isoformat() if self.abierto_en else None,
            'abierto_por': self.abierto_por
        }
    
    def get_checklist_tecnico_dict(self):
        """Obtiene el checklist técnico como diccionario"""
        if self.checklist_tecnico:
            try:
                return json.loads(self.checklist_tecnico)
            except:
                return {}
        return {}
    
    def set_checklist_tecnico(self, checklist_dict):
        """Establece el checklist técnico desde un diccionario"""
        self.checklist_tecnico = json.dumps(checklist_dict)
    
    def get_checklist_apertura_dict(self):
        """Obtiene el checklist de apertura como diccionario"""
        if self.checklist_apertura:
            try:
                return json.loads(self.checklist_apertura)
            except:
                return {}
        return {}
    
    def set_checklist_apertura(self, checklist_dict):
        """Establece el checklist de apertura desde un diccionario"""
        self.checklist_apertura = json.dumps(checklist_dict)


class PlanillaTrabajador(db.Model):
    """Planilla de trabajadores de una jornada"""
    __tablename__ = 'planilla_trabajadores'
    
    id = db.Column(db.Integer, primary_key=True)
    jornada_id = db.Column(db.Integer, db.ForeignKey('jornadas.id'), nullable=False, index=True)
    id_empleado = db.Column(db.String(50), nullable=False)
    nombre_empleado = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(50), nullable=False)  # "cajero", "bartender", "seguridad", "admin", "puerta"
    hora_inicio = db.Column(db.String(10), nullable=False)  # "20:00"
    hora_fin = db.Column(db.String(10), nullable=False)  # "04:00"
    costo_hora = db.Column(Numeric(10, 2), nullable=False)
    costo_total = db.Column(Numeric(10, 2), nullable=False)
    area = db.Column(db.String(100), nullable=True)  # "caja 1", "barra principal", etc.
    
    # Timestamps
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Índices
    __table_args__ = (
        Index('idx_planilla_jornada', 'jornada_id'),
        Index('idx_planilla_empleado', 'id_empleado'),
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'jornada_id': self.jornada_id,
            'id_empleado': self.id_empleado,
            'nombre_empleado': self.nombre_empleado,
            'rol': self.rol,
            'hora_inicio': self.hora_inicio,
            'hora_fin': self.hora_fin,
            'costo_hora': float(self.costo_hora) if self.costo_hora else 0.0,
            'costo_total': float(self.costo_total) if self.costo_total else 0.0,
            'area': self.area,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None
        }
    
    def calcular_costo_total(self):
        """Calcula el costo total basado en horas trabajadas"""
        try:
            # Parsear horas
            inicio = datetime.strptime(self.hora_inicio, '%H:%M')
            fin = datetime.strptime(self.hora_fin, '%H:%M')
            
            # Si la hora fin es menor que inicio, asumimos que pasa la medianoche
            if fin < inicio:
                fin = fin.replace(day=fin.day + 1)
            
            diferencia = fin - inicio
            horas_trabajadas = diferencia.total_seconds() / 3600.0
            
            self.costo_total = self.costo_hora * horas_trabajadas
            return self.costo_total
        except:
            return 0.0


class AperturaCaja(db.Model):
    """Apertura de una caja en una jornada"""
    __tablename__ = 'aperturas_cajas'
    
    id = db.Column(db.Integer, primary_key=True)
    jornada_id = db.Column(db.Integer, db.ForeignKey('jornadas.id'), nullable=False, index=True)
    id_caja = db.Column(db.String(50), nullable=False, index=True)
    nombre_caja = db.Column(db.String(200), nullable=False)
    id_empleado = db.Column(db.String(50), nullable=False)
    nombre_empleado = db.Column(db.String(200), nullable=False)
    fondo_inicial = db.Column(Numeric(10, 2), nullable=False)
    fecha_apertura = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    abierto_por = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(50), default='abierta', nullable=False)  # pendiente, abierta, cerrada
    
    # Índices
    __table_args__ = (
        Index('idx_apertura_caja_jornada', 'jornada_id'),
        Index('idx_apertura_caja_id', 'id_caja'),
        Index('idx_apertura_caja_estado', 'estado'),
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        return {
            'id': self.id,
            'jornada_id': self.jornada_id,
            'id_caja': self.id_caja,
            'nombre_caja': self.nombre_caja,
            'id_empleado': self.id_empleado,
            'nombre_empleado': self.nombre_empleado,
            'fondo_inicial': float(self.fondo_inicial) if self.fondo_inicial else 0.0,
            'fecha_apertura': self.fecha_apertura.isoformat() if self.fecha_apertura else None,
            'abierto_por': self.abierto_por,
            'estado': self.estado
        }


class SnapshotEmpleados(db.Model):
    """Snapshot de empleados al abrir el turno (para evitar consultas constantes a la API)"""
    __tablename__ = 'snapshot_empleados'
    
    id = db.Column(db.Integer, primary_key=True)
    jornada_id = db.Column(db.Integer, db.ForeignKey('jornadas.id'), nullable=False, index=True)
    empleado_id = db.Column(db.String(50), nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False)
    cargo = db.Column(db.String(100), nullable=True)  # "Bartender", "Cajero", etc.
    datos_completos = db.Column(Text, nullable=True)  # JSON con todos los datos del empleado
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Índices
    __table_args__ = (
        Index('idx_snapshot_jornada', 'jornada_id'),
        Index('idx_snapshot_empleado', 'empleado_id'),
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        datos = {}
        if self.datos_completos:
            try:
                datos = json.loads(self.datos_completos)
            except:
                pass
        return {
            'id': self.id,
            'jornada_id': self.jornada_id,
            'empleado_id': self.empleado_id,
            'nombre': self.nombre,
            'cargo': self.cargo,
            'datos_completos': datos,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None
        }


class SnapshotCajas(db.Model):
    """Snapshot de cajas al abrir el turno (para evitar consultas constantes a la API)"""
    __tablename__ = 'snapshot_cajas'
    
    id = db.Column(db.Integer, primary_key=True)
    jornada_id = db.Column(db.Integer, db.ForeignKey('jornadas.id'), nullable=False, index=True)
    caja_id = db.Column(db.String(50), nullable=False, index=True)
    nombre_caja = db.Column(db.String(200), nullable=False)
    datos_completos = db.Column(Text, nullable=True)  # JSON con todos los datos de la caja
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Índices
    __table_args__ = (
        Index('idx_snapshot_cajas_jornada', 'jornada_id'),
        Index('idx_snapshot_cajas_id', 'caja_id'),
    )
    
    def to_dict(self):
        """Convierte el modelo a diccionario"""
        datos = {}
        if self.datos_completos:
            try:
                datos = json.loads(self.datos_completos)
            except:
                pass
        return {
            'id': self.id,
            'jornada_id': self.jornada_id,
            'caja_id': self.caja_id,
            'nombre_caja': self.nombre_caja,
            'datos_completos': datos,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None
        }


