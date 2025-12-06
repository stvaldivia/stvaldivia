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
            'stock_quantity': self.stock_quantity,
            'is_active': self.is_active
        }
    
    def __repr__(self):
        return f'<Product {self.name}>'
