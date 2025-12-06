"""
Script para actualizar la capacidad de los ingredientes desde el Excel.
"""
import pandas as pd
from app import create_app
from app.models import db
from app.models.recipe_models import Ingredient

def update_ingredient_capacities():
    app = create_app()
    with app.app_context():
        print("Updating ingredient capacities...")
        
        try:
            df = pd.read_excel('i/Ingredientes.xlsx', header=None)
            
            # Columna 2: Nombre
            # Columna 32: Capacidad (700, 750, 1000, etc)
            # Columna 33: Unidad (ml, lt, etc)
            
            count = 0
            for index, row in df.iterrows():
                name = str(row[2]).strip()
                if not name or name == 'nan':
                    continue
                    
                try:
                    capacity = float(row[32])
                    unit = str(row[33]).strip().lower()
                    
                    if pd.isna(capacity):
                        continue
                        
                    # Normalizar a ml
                    if unit in ['lt', 'l', 'litro', 'litros']:
                        capacity_ml = capacity * 1000
                    else:
                        capacity_ml = capacity
                        
                    # Buscar ingrediente
                    ingredient = Ingredient.query.filter_by(name=name).first()
                    if ingredient:
                        # Guardamos la capacidad en stock_quantity? No, eso es el stock actual.
                        # Deberíamos agregar un campo 'volume_ml' al modelo Ingredient.
                        # Por ahora, vamos a imprimir lo que encontramos para verificar.
                        print(f"Found {name}: {capacity_ml} ml")
                        count += 1
                        
                except Exception as e:
                    # print(f"Error parsing row {index}: {e}")
                    pass
            
            print(f"Found capacity info for {count} ingredients")
            
        except Exception as e:
            print(f"Error reading excel: {e}")

if __name__ == '__main__':
    update_ingredient_capacities()
