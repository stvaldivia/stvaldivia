import pandas as pd
import os
from app import create_app
from app.models import db
from app.models.product_models import Product
from app.models.recipe_models import Ingredient, ProductRecipe

def migrate_recipes():
    app = create_app()
    with app.app_context():
        # 1. Migrar Ingredientes
        file_path_ing = 'i/Ingredientes.xlsx'
        if os.path.exists(file_path_ing):
            print(f"Reading {file_path_ing}...")
            try:
                # Leer sin header para ver estructura
                df = pd.read_excel(file_path_ing, header=None)
                
                # Asumimos que la columna 2 (índice 2) es el nombre del ingrediente
                # Basado en la inspección anterior: 
                # Row 3: NaN NaN Araucano Largo ...
                # Parece que el nombre está en la columna 2
                
                count_ing = 0
                for index, row in df.iterrows():
                    name = str(row[2]).strip()
                    if not name or name == 'nan' or name == 'Nombre del kit':
                        continue
                        
                    # Verificar si existe como ingrediente
                    ing = Ingredient.query.filter_by(name=name).first()
                    if not ing:
                        ing = Ingredient(name=name, unit='unidad') # Default unit
                        db.session.add(ing)
                        count_ing += 1
                        print(f"Created Ingredient: {name}")
                
                db.session.commit()
                print(f"Created {count_ing} ingredients")
                
            except Exception as e:
                print(f"Error reading ingredients: {e}")

        # 2. Crear Recetas (Relación Kit -> Ingrediente)
        print("\nLinking Products to Ingredients...")
        
        # Ejemplo específico de la imagen: "Calpel 35 con bebida"
        # Ingredientes: Calpel 35 (0.09), Garnish... (1), Bebida Servida (0.2)
        
        product_calpel = Product.query.filter(Product.name.ilike("%Calpel 35 con bebida%")).first()
        if product_calpel:
            print(f"Configuring recipe for {product_calpel.name}...")
            product_calpel.is_kit = True
            
            # Ingrediente 1: Calpel 35
            ing_calpel = Ingredient.query.filter(Ingredient.name.ilike("%Calpel 35%")).first()
            if ing_calpel:
                # Verificar si ya existe
                if not ProductRecipe.query.filter_by(product_id=product_calpel.id, ingredient_id=ing_calpel.id).first():
                    r = ProductRecipe(product_id=product_calpel.id, ingredient_id=ing_calpel.id, quantity=0.09)
                    db.session.add(r)
                    print(f"  + Added ingredient: {ing_calpel.name} (0.09)")
            
            # Ingrediente 2: Garnish
            ing_garnish = Ingredient.query.filter(Ingredient.name.ilike("%Garnish%")).first()
            if ing_garnish:
                if not ProductRecipe.query.filter_by(product_id=product_calpel.id, ingredient_id=ing_garnish.id).first():
                    r = ProductRecipe(product_id=product_calpel.id, ingredient_id=ing_garnish.id, quantity=1.0)
                    db.session.add(r)
                    print(f"  + Added ingredient: {ing_garnish.name} (1.0)")
            
            # Ingrediente 3: Bebida Servida
            ing_bebida = Ingredient.query.filter(Ingredient.name.ilike("%Bebida Servida%")).first()
            if ing_bebida:
                if not ProductRecipe.query.filter_by(product_id=product_calpel.id, ingredient_id=ing_bebida.id).first():
                    r = ProductRecipe(product_id=product_calpel.id, ingredient_id=ing_bebida.id, quantity=0.2)
                    db.session.add(r)
                    print(f"  + Added ingredient: {ing_bebida.name} (0.2)")

        # Lógica general 1:1 para otros productos
        products = Product.query.all()
        count_recipes = 0
        
        for product in products:
            if product.id == product_calpel.id if product_calpel else False:
                continue
                
            # Buscar si existe un ingrediente con nombre similar
            ingredient = Ingredient.query.filter_by(name=product.name).first()
            
            if ingredient:
                # Crear receta 1:1
                recipe = ProductRecipe.query.filter_by(product_id=product.id, ingredient_id=ingredient.id).first()
                if not recipe:
                    recipe = ProductRecipe(
                        product_id=product.id,
                        ingredient_id=ingredient.id,
                        quantity=1.0
                    )
                    db.session.add(recipe)
                    
                    # Marcar producto como Kit
                    product.is_kit = True
                    count_recipes += 1
                    print(f"Linked {product.name} -> {ingredient.name} (1.0)")
        
        db.session.commit()
        print(f"Created {count_recipes} basic recipes + Example Recipe")

if __name__ == '__main__':
    migrate_recipes()
