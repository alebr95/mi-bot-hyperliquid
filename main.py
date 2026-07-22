import os
import json
from flask import Flask, request, jsonify
from hyperliquid.utils import constants
from hyperliquid.exchange import Exchange
from eth_account import Account

app = Flask(__name__)

# Cargar claves de entorno
SECRET_KEY = os.getenv("HYPERLIQUID_PRIVATE_KEY", "")
ACCOUNT_ADDRESS = os.getenv("HYPERLIQUID_ADDRESS", "")

@app.route('/', methods=['GET'])
def health_check():
    return "Bot de Webhooks activo y listo en Render.", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        print("\n==========================================")
        print("¡ALERTA RECIBIDA DESDE TRADINGVIEW!")
        print(f"Datos recibidos: {json.dumps(data, indent=2)}")
        print("==========================================\n")

        action = data.get("action", "").upper()
        ticker = data.get("ticker", "ETH").replace("PERP", "").replace("USDT", "")
        
        # Conexión con Hyperliquid si hay claves configuradas
        if SECRET_KEY and ACCOUNT_ADDRESS:
            account = Account.from_key(SECRET_KEY)
            exchange = Exchange(account, constants.MAINNET_API_URL)

            if action in ["BUY", "LONG"]:
                print(f"🚀 Ejecutando LONG en Hyperliquid para {ticker}...")
                # Ejemplo de orden a mercado por $10 USD
                # (Ajustable a tu tamaño de posición preferido)
                res = exchange.market_open(ticker, is_buy=True, sz=0.005, px=None, slippage=0.01)
                print(f"Resultado de la orden: {res}")

            elif action in ["SELL", "SHORT"]:
                print(f"🔻 Ejecutando SHORT en Hyperliquid para {ticker}...")
                res = exchange.market_open(ticker, is_buy=False, sz=0.005, px=None, slippage=0.01)
                print(f"Resultado de la orden: {res}")

            elif action in ["EXIT", "CLOSE"]:
                print(f"🛑 Cerrando posición para {ticker}...")
                res = exchange.market_close(ticker)
                print(f"Resultado del cierre: {res}")
        else:
            print("⚠️ Alerta recibida correctamente en MODO SIMULACIÓN (sin claves API configuradas en Render).")

        return jsonify({"status": "success", "message": "Alerta procesada"}), 200

    except Exception as e:
        print(f"❌ Error al procesar la orden: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)