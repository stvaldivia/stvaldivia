from app import create_app
from app.models import db
from app.models.product_models import Product
from app.models.recipe_models import Ingredient, ProductRecipe

def configure_gin_recipes():
    app = create_app()
    with app.app_context():
        print("Configuring Gin Tonic recipes...")
        
        # Ingredientes comunes
        ing_garnish = Ingredient.query.filter(Ingredient.name.ilike("%Garnish%")).first()
        ing_tonica = Ingredient.query.filter(Ingredient.name.ilike("%Agua Tónica%")).first()
        
        if not ing_garnish:
            print("Error: Ingredient 'Garnish' not found")
            return
        if not ing_tonica:
            print("Error: Ingredient 'Agua Tónica' not found")
            return
            
        print(f"Using common ingredients: {ing_garnish.name}, {ing_tonica.name}")
        
        # Gins a configurar
        gins = ['Beefeater', 'Bombay', 'Tanqueray']
        
        for gin_name in gins:
            product = Product.query.filter(Product.name.ilike(f"%{gin_name}%")).first()
            if not product:
                print(f"Product '{gin_name}' not found, skipping.")
                continue
                
            ingredient = Ingredient.query.filter(Ingredient.name.ilike(f"%{gin_name}%")).first()
            if not ingredient:
                print(f"Ingredient '{gin_name}' not found, skipping.")
                continue
                
            print(f"\nConfiguring {product.name}...")
            product.is_kit = True
            
            # Limpiar recetas existentes (si era 1:1)
            ProductRecipe.query.filter_by(product_id=product.id).delete()
            
            # 1. Gin (90cc)
            # Ahora definimos en ML para que el sistema calcule la fracción exacta según la botella
            r1 = ProductRecipe(product_id=product.id, ingredient_id=ingredient.id, quantity=90.0)
            db.session.add(r1)
            print(f"  + Added {ingredient.name}: 90.0 ml")
            
            # 2. Tónica (200cc)
            # Si la tónica es de 1.5L, 200cc es 0.2 / 1.5 = 0.1333
            # Aquí seguimos usando fracción porque la tónica se cuenta en botellas de 1.5L
            # Y 200ml es claramente < 5.0, así que el sistema lo tomará como fracción.
            qty_tonica = 0.2 / 1.5
            if "1.5L" in ing_tonica.name:
                qty_tonica = 0.2 / 1.5
                
            r2 = ProductRecipe(product_id=product.id, ingredient_id=ing_tonica.id, quantity=qty_tonica)
            db.session.add(r2)
            print(f"  + Added {ing_tonica.name}: {qty_tonica:.4f} (fraction)")
            
            # 3. Garnish (1 unidad)
            r3 = ProductRecipe(product_id=product.id, ingredient_id=ing_garnish.id, quantity=1.0)
            db.session.add(r3)
            print(f"  + Added {ing_garnish.name}: 1.0")
            
        db.session.commit()
        print("\nGin recipes configured successfully!")

if __name__ == '__main__':
    configure_gin_recipes()
