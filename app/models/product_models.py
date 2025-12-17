"""
Modelos de productos para inventario propio.
Reemplaza la dependencia de la API externa.
"""
from datetime import datetime
from . import db

class Product(db.Model):
    """Modelo de Producto"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True, index=True)
    category = db.Column(db.String(100))
    price = db.Column(db.Integer, default=0)
    cost_price = db.Column(db.Integer, default=0)
    stock_quantity = db.Column(db.Integer, default=0)
    stock_minimum = db.Column(db.Integer, default=0)  # Stock mínimo antes de alertar
    is_active = db.Column(db.Boolean, default=True)
    is_kit = db.Column(db.Boolean, default=False) # Si es True, usa receta (ProductRecipe)
    
    # Identificadores externos (para migración)
    external_id = db.Column(db.String(100), index=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'price': self.price,
            'cost_price': self.cost_price,
            'stock_quantity': self.stock_quantity,
            'stock_minimum': self.stock_minimum,
            'is_active': self.is_active,
            'is_kit': self.is_kit,
            'profit': self.price - self.cost_price if self.cost_price else None,
            'profit_percent': ((self.price - self.cost_price) / self.cost_price * 100) if self.cost_price and self.cost_price > 0 else None
        }
    
    @property
    def profit(self):
        """Calcula la ganancia (precio - costo)"""
        if self.cost_price:
            return self.price - self.cost_price
        return None
    
    @property
    def profit_percent(self):
        """Calcula el porcentaje de ganancia"""
        if self.cost_price and self.cost_price > 0:
            return round((self.price - self.cost_price) / self.cost_price * 100, 2)
        return None
    
    @property
    def stock_status(self):
        """Retorna el estado del stock: 'ok', 'low', 'out'"""
        if self.stock_quantity <= 0:
            return 'out'
        elif self.stock_minimum > 0 and self.stock_quantity <= self.stock_minimum:
            return 'low'
        return 'ok'
    
    def __repr__(self):
        return f'<Product {self.name}>'
