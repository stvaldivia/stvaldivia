"""
Script para verificar datos de guardarropía directamente desde la web
"""
import requests
import json

def check_web_data():
    """Verifica datos accediendo a la API web"""
    base_url = "https://stvaldivia.cl"
    
    print("🔍 Verificando datos en la web...")
    print(f"🌐 URL: {base_url}")
    print("")
    
    # Intentar acceder a la API de estadísticas
    try:
        # Primero intentar con la API
        api_url = f"{base_url}/admin/guardarropia/api/stats"
        print(f"📡 Consultando: {api_url}")
        
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Respuesta de la API:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"⚠️  Status code: {response.status_code}")
            print(f"   Respuesta: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Error al consultar API: {e}")
    
    print("\n" + "="*50)
    print("💡 Si los datos están en la web pero no en la BD,")
    print("   puede ser que estén en otra tabla o formato.")
    print("   ¿Puedes indicar exactamente dónde ves los datos?")
    print("   - ¿En qué URL los ves?")
    print("   - ¿Qué información muestran?")

if __name__ == '__main__':
    check_web_data()




