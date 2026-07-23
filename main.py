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
        if not data:
            return jsonify({"status": "error", "message": "No JSON payload"}), 400

        # Normalizamos la acción a mayúsculas ('sell' -> 'SELL', 'buy' -> 'BUY')
        action = str(data.get("action", "")).upper()

        # Limpiamos el ticker (convierte 'ETHUSDC.P', 'ETHUSDT', etc. en solo 'ETH')
        raw_ticker = str(data.get("ticker", "ETH"))
        ticker = raw_ticker.split('.')[0].replace("USDC", "").replace("USDT", "").replace("USD", "").strip()

        print(f"==========================================")
        print(f"¡ALERTA RECIBIDA DESDE TRADINGVIEW!")
        print(f"Acción procesada: {action} | Ticker procesado: {ticker}")
        print(f"==========================================")

        # Conexión con Hyperliquid si hay claves configuradas
        if SECRET_KEY and ACCOUNT_ADDRESS:
            account = Account.from_key(SECRET_KEY)
            exchange = Exchange(account, constants.MAINNET_API_URL)

            if action in ["BUY", "LONG"]:
                print(f"🚀 Ejecutando LONG en Hyperliquid para {ticker}...")
                res = exchange.market_open(ticker, is_buy=True, sz=0.005, px=None, slippage=0.01)
                print(f"Resultado de la orden: {res}")

            elif action in ["SELL", "SHORT"]:
                print(f"📉 Ejecutando SHORT en Hyperliquid para {ticker}...")
                res = exchange.market_open(ticker, is_buy=False, sz=0.005, px=None, slippage=0.01)
                print(f"Resultado de la orden: {res}")

            elif action in ["EXIT", "CLOSE"]:
                print(f"⚠️ Cerrando posición para {ticker}...")
                res = exchange.market_close(ticker)
                print(f"Resultado del cierre: {res}")

            else:
                print(f"⚠️ Acción no reconocida o en MODO SIMULACIÓN: {action}")

        return jsonify({"status": "success", "message": "Alerta procesada correctamente"}), 200

    except Exception as e:
        print(f"❌ Error al procesar la orden: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)