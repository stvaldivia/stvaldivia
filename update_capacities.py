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
                        ingredient.volume_ml = capacity_ml
                        count += 1
                        print(f"Updated {name}: {capacity_ml} ml")
                        
                except Exception as e:
                    pass
            
            db.session.commit()
            print(f"Updated capacity for {count} ingredients")
            
        except Exception as e:
            print(f"Error reading excel: {e}")

if __name__ == '__main__':
    update_ingredient_capacities()
