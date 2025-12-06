import pandas as pd
import os
import sys
from app import create_app
from app.models import db
from app.models.product_models import Product

def migrate_products():
    app = create_app()
    with app.app_context():
        file_path = 'i/Productos a la venta.xlsx'
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return

        print(f"Reading {file_path}...")
        try:
            # Read excel, header is at row 0
            df = pd.read_excel(file_path, header=0)
            
            # Columns based on inspection:
            # 'Nombre del kit' -> Name
            # 'Categoría' -> Category
            # 'Costo' -> Cost Price
            # 'Precio de venta' -> Price
            
            count_created = 0
            count_updated = 0
            
            for index, row in df.iterrows():
                name = str(row['Nombre del kit']).strip()
                if not name or name == 'nan':
                    continue
                
                category = str(row['Categoría']).strip() if not pd.isna(row['Categoría']) else 'General'
                
                try:
                    cost = int(float(row['Costo'])) if not pd.isna(row['Costo']) else 0
                except:
                    cost = 0
                    
                try:
                    price = int(float(row['Precio de venta'])) if not pd.isna(row['Precio de venta']) else 0
                except:
                    price = 0
                
                # Check if product exists
                product = Product.query.filter_by(name=name).first()
                
                if product:
                    # Update
                    product.category = category
                    product.cost_price = cost
                    product.price = price
                    count_updated += 1
                    print(f"Updated: {name}")
                else:
                    # Create
                    product = Product(
                        name=name,
                        category=category,
                        cost_price=cost,
                        price=price,
                        stock_quantity=0, # Initial stock 0
                        is_active=True
                    )
                    db.session.add(product)
                    count_created += 1
                    print(f"Created: {name}")
            
            db.session.commit()
            print(f"\nMigration completed!")
            print(f"Created: {count_created}")
            print(f"Updated: {count_updated}")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error migrating products: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    migrate_products()
