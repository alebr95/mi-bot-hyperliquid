import os
import threading
from flask import Flask, request, jsonify
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

app = Flask(__name__)

# Cargar claves de entorno
SECRET_KEY = os.environ.get("HYPERLIQUID_PRIVATE_KEY", "")
ACCOUNT_ADDRESS = os.environ.get("HYPERLIQUID_ADDRESS", "")

@app.route("/", methods=['GET'])
def health_check():
    return "Bot de webhooks activo y listo en Render.", 200
def procesar_orden_hyperliquid(action, ticker):
    try:
        # Conexión con Hyperliquid si hay claves configuradas
        if SECRET_KEY and ACCOUNT_ADDRESS:
            account = Account.from_key(SECRET_KEY)
            exchange = Exchange(account, constants.MAINNET_API_URL)

            if action in ["BUY", "LONG"]:
                print(f"🚀 Ejecutando LONG en Hyperliquid para {ticker}...", flush=True)
                res = exchange.market_open(ticker, is_buy=True, sz=0.01, px=None, slippage=0.01)
                print(f"Resultado de la orden: {res}", flush=True)

            elif action in ["SELL", "SHORT"]:
                print(f"📉 Ejecutando SHORT en Hyperliquid para {ticker}...", flush=True)
                res = exchange.market_open(ticker, is_buy=False, sz=0.01, px=None, slippage=0.01)
                print(f"Resultado de la orden: {res}", flush=True)

            elif action in ["EXIT", "CLOSE"]:
                print(f"⚠️ Cerrando posición para {ticker}...", flush=True)
                res = exchange.market_close(ticker)
                print(f"Resultado del cierre: {res}", flush=True)

            else:
                print(f"⚠️ Acción no reconocida o en MODO SIMULACIÓN: {action}", flush=True)
    except Exception as e:
        print(f"❌ Error al procesar la orden en Hyperliquid: {e}", flush=True)


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"status": "error", "message": "No JSON payload"}), 400

        # Normalizamos la acción y el ticker
        action = str(data.get("action", "")).upper()
        raw_ticker = str(data.get("ticker", "ETH"))
        ticker = raw_ticker.split(".")[0].replace("USDC", "").replace("USDT", "").replace("USD", "").strip()

        print("========================================", flush=True)
        print("ALERTA RECIBIDA DESDE TRADINGVIEW!", flush=True)
        print(f"Acción procesada: {action} | Ticker procesado: {ticker}", flush=True)
        print("========================================", flush=True)

        # 1. Ejecutar en segundo plano sin bloquear
        threading.Thread(target=procesar_orden_hyperliquid, args=(action, ticker)).start()

        # 2. Responder a TradingView de forma inmediata (0.05s)
        return jsonify({"status": "success", "message": "Alerta procesada correctamente"}), 200

    except Exception as e:
        print(f"❌ Error al recibir el webhook: {e}", flush=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)