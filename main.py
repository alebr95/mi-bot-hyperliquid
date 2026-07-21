import time
import threading
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List

import requests


HYPERLIQUID_INFO_URL = os.getenv("HYPERLIQUID_INFO_URL", "https://api.hyperliquid.xyz/info")
HYPERLIQUID_PRIVATE_KEY = os.getenv("HYPERLIQUID_PRIVATE_KEY", "")
HYPERLIQUID_ADDRESS = os.getenv("HYPERLIQUID_ADDRESS", "")
RENDER_PORT = int(os.getenv("PORT", "10000"))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK\n")

    def log_message(self, format: str, *args: Any) -> None:
        return


def fetch_hourly_candles(coin: str = "ETH", interval: str = "1h", lookback: int = 250) -> List[Dict[str, Any]]:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - (lookback * 60 * 60 * 1000)

    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": start_ms,
            "endTime": now_ms,
        },
    }

    response = requests.post(HYPERLIQUID_INFO_URL, json=payload, timeout=20)
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, list):
        raise ValueError(f"Unexpected response format: {data}")

    return data


def ema_series(values: List[float], period: int) -> List[float]:
    if not values:
        return []

    multiplier = 2 / (period + 1)
    ema = float(values[0])
    result: List[float] = []

    for index, value in enumerate(values):
        if index == 0:
            ema = float(value)
        elif index < period:
            ema = (ema * index + float(value)) / (index + 1)
        else:
            ema = (float(value) - ema) * multiplier + ema
        result.append(ema)

    return result


def detect_signal(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Réplica exacta del Pine Script: Bot ETH Hyper Optimized V3 - Gemini"""
    closes_all = [float(candle["c"]) for candle in candles if candle.get("c") is not None]
    volumes_all = [float(candle.get("v", 0) or 0) for candle in candles]

    # Tomamos solo las velas CERRADAS (descartamos la vela que acaba de abrir a las :00:05)
    closes = closes_all[:-1]
    volumes = volumes_all[:-1]

    if len(closes) < 210:
        return {"signal": "NONE", "reason": "Not enough candles for EMA 200"}

    # --- INDICADORES EN VELAS CERRADAS ---
    ema9 = ema_series(closes, 9)
    ema21 = ema_series(closes, 21)
    ema200 = ema_series(closes, 200)

    window = 20
    media_volumen = sum(volumes[-window:]) / window if len(volumes) >= window else 0

    latest_close = closes[-1]
    latest_volume = volumes[-1]
    
    v_ema_rapida = ema9[-1]
    v_ema_lenta = ema21[-1]
    v_ema_filtro = ema200[-1]

    prev_ema_rapida = ema9[-2]
    prev_ema_lenta = ema21[-2]

    # --- CONDICIONES PINE SCRIPT ---
    volumen_alto = latest_volume > media_volumen 
    tendencia_alcista = latest_close > v_ema_filtro
    tendencia_bajista = latest_close < v_ema_filtro

    crossover = (v_ema_rapida > v_ema_lenta) and (prev_ema_rapida <= prev_ema_lenta)
    crossunder = (v_ema_rapida < v_ema_lenta) and (prev_ema_rapida >= prev_ema_lenta)

    condicion_long = crossover and volumen_alto and tendencia_alcista
    condicion_short = crossunder and volumen_alto and tendencia_bajista

    if condicion_long:
        return {
            "signal": "LONG",
            "price": latest_close,
            "reason": "Long ETH: Crossover EMA 9/21, volumen alto y tendencia alcista (Pine Script Match)",
        }

    if condicion_short:
        return {
            "signal": "SHORT",
            "price": latest_close,
            "reason": "Short ETH: Crossunder EMA 9/21, volumen alto y tendencia bajista (Pine Script Match)",
        }

    return {
        "signal": "NONE",
        "price": latest_close,
        "reason": "No entry signal at this moment",
    }


def place_order(signal: str, entry_price: float, stop_loss_pct: float = 0.02, take_profit_pct: float = 0.07) -> Dict[str, Any]:
    if not HYPERLIQUID_PRIVATE_KEY or not HYPERLIQUID_ADDRESS:
        return {
            "status": "simulated",
            "signal": signal,
            "entry_price": entry_price,
            "notes": "Simulated order (No API Keys configured yet)",
        }

    return {
        "status": "simulated",
        "signal": signal,
        "entry_price": entry_price,
    }


def main() -> None:
    print("Conectando con Hyperliquid para el análisis ETH 1H...")

    try:
        candles = fetch_hourly_candles("ETH", interval="1h", lookback=250)
    except Exception as exc:
        print(f"No se pudieron obtener velas reales: {exc}")
        return

    signal = detect_signal(candles)
    print(f"Señal detectada: {signal['signal']}")
    print(f"Razón: {signal['reason']}")
    print(f"Precio actual: {signal['price']:.2f}")

    if signal["signal"] == "NONE":
        print("Ciclo finalizado sin operaciones. Terminando ejecución.")
        return

    order_result = place_order(
        signal["signal"],
        signal["price"],
        stop_loss_pct=0.02,
        take_profit_pct=0.07,
    )
    print(order_result)


def arrancar_servidor_render():
    try:
        puerto = int(os.environ.get("PORT", 10000))
        servidor = ThreadingHTTPServer(("0.0.0.0", puerto), HealthHandler)
        print(f"Servidor de Render activo en el puerto {puerto}")
        servidor.serve_forever()
    except Exception as e:
        print(f"Error servidor web: {e}")


if __name__ == "__main__":
    t = threading.Thread(target=arrancar_servidor_render, daemon=True)
    t.start()

    while True:
        ahora = datetime.now(timezone.utc)
        minutos_restantes = 60 - ahora.minute
        segundos_restantes = 60 - ahora.second
        
        if ahora.minute != 0:
            tiempo_espera = ((minutos_restantes - 1) * 60) + segundos_restantes
            print(f"Sincronizando reloj. Esperando {tiempo_espera} segundos hasta la hora en punto...")
            time.sleep(tiempo_espera)
            
        print("¡Hora en punto detectada! Iniciando análisis de mercado en Hyperliquid...")
        try:
            main()
        except Exception as e:
            print(f"Error en la ejecución: {e}")
        
        print("Ciclo completado. Esperando 1 hora para el siguiente análisis...")
        time.sleep(3600)