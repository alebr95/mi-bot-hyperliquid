import requests

url = "https://api.hyperliquid.xyz/info"
payload = {"type": "metaAndAssetContexts"}

print("Conectando con Hyperliquid con ExpressVPN en España...")
try:
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("¡CONEXIÓN EXITOSA! La API no bloqueó tu localización. ¡ExpressVPN funciona perfecto!")
    else:
        print(f"Error de conexión. Código de estado: {response.status_code}")
except Exception as e:
    print(f"Hubo un problema al conectar: {e}")