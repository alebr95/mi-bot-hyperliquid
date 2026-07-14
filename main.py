import requests


URL = "https://api.hyperliquid.xyz/info"
PAYLOAD = {"type": "metaAndAssetContexts"}


def main() -> None:
    print("Conectando con Hyperliquid...")
    try:
        response = requests.post(URL, json=PAYLOAD, timeout=15)
        response.raise_for_status()
        print("Conexión exitosa. La API respondió correctamente.")
        print(response.text[:500])
    except requests.RequestException as exc:
        print(f"Hubo un problema al conectar: {exc}")


if __name__ == "__main__":
    main()
