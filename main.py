import time
import threading
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List

import requests


# IMPORTANT: set these in your deployment platform (Render, GitHub Actions, etc.)
# as environment variables, not hard-coded in the repository.
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
    """Fetch hourly OHLCV candles from Hyperliquid's info endpoint."""
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
    """Calculate exponential moving averages for a list of values."""
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
    closes = [float(candle["c"]) for candle in candles if candle.get("c") is not None]
    volumes = [float(candle.get("v", 0) or 0) for candle in candles]

    if len(closes) < 210:
        return {"signal": "NONE", "reason": "Not enough candles for EMA 200"}

    # --- INDICADORES ---
    ema9 = ema_series(closes, 9)
    ema21 = ema_series(closes, 21)
    ema200 = ema_series(closes, 200)

    # media_volumen = ta.sma(volume, periodos_vol) -> 20 periodos
    window = 20
    media_volumen = sum(volumes[-window:]) / window if len(volumes) >= window else 0

    # --- DATOS ACTUALES Y PREVIOS ---
    latest_close = closes[-1]
    latest_volume = volumes[-1]
    
    v_ema_rapida = ema9[-1]
    v_ema_lenta = ema21[-1]
    v_ema_filtro = ema200[-1]

    prev_ema_rapida = ema9[-2]
    prev_ema_lenta = ema21[-2]

    # --- FILTROS DE PINE SCRIPT ---
    current_hour = datetime.now(timezone.utc).hour
    
    # permitir_operar = (hour >= hora_inicio and hour <= hora_fin)
    permitir_operar = (6 <= current_hour <= 18)  
    
    # volumen_alto = volume > media_volumen
    volumen_alto = latest_volume > media_volumen 
    
    # tendencia_alcista = close > v_ema_filtro / tendencia_bajista = close < v_ema_filtro
    tendencia_alcista = latest_close > v_ema_filtro
    tendencia_bajista = latest_close < v_ema_filtro

    # --- CONDICIONES (ta.crossover y ta.crossunder) ---
    crossover = (v_ema_rapida > v_ema_lenta) and (prev_ema_rapida <= prev_ema_lenta)
    crossunder = (v_ema_rapida < v_ema_lenta) and (prev_ema_rapida >= prev_ema_lenta)

    condicion_long = crossover and volumen_alto and tendencia_alcista and permitir_operar
    condicion_short = crossunder and volumen_alto and tendencia_bajista and permitir_operar

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
    """Placeholder for sending a signed order to Hyperliquid."""
    if not HYPERLIQUID_PRIVATE_KEY or not HYPERLIQUID_ADDRESS:
        raise RuntimeError(
            "Set HYPERLIQUID_PRIVATE_KEY and HYPERLIQUID_ADDRESS as environment variables before trading."
        )

    return {
        "status": "simulated",
        "signal": signal,
        "entry_price": entry_price,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "notes": "Replace this placeholder with a signed Hyperliquid order payload.",
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


def run_web_server(port: int) -> None:
    server_address = ("", port)

    with ThreadingHTTPServer(server_address, HealthHandler) as httpd:
        print(f"Servidor web activo en el puerto {port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
            print("Servidor web detenido.")


def arrancar_servidor_render():
    try:
        # Esto arranca el servidor web en el puerto que pide Render para que sea gratis
        puerto = int(os.environ.get("PORT", 10000))
        servidor = ThreadingHTTPServer(("0.0.0.0", puerto), HealthHandler)
        print(f"Servidor de Render activo en el puerto {puerto}")
        servidor.serve_forever()
    except Exception as e:
        print(f"No se pudo arrancar el servidor de Render (No importa si estás en local): {e}")

if __name__ == "__main__":
    # 1. Arrancamos el servidor de Render de fondo para que no moleste ni dé Timed Out
    t = threading.Thread(target=arrancar_servidor_render, daemon=True)
    t.start()

    # 2. Tu bot normal con su sincronización a la hora cero
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
            main()  # Tu estrategia
        except Exception as e:
            print(f"Error en la ejecución: {e}")
        
        print("Ciclo completado. Esperando 1 hora para el siguiente análisis...")
        time.sleep(3600)