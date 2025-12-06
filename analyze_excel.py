import pandas as pd
import os

file_path = 'i/Ingredientes.xlsx'
try:
    # Read without header to see the raw structure
    df = pd.read_excel(file_path, header=None)
    print("Shape:", df.shape)
    print("\nFirst 10 rows raw:")
    print(df.head(10).to_string())
except Exception as e:
    print(f"Error reading excel: {e}")
