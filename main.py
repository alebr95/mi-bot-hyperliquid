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
    """Return a trading signal based on EMA crosses and volume confirmation."""
    closes = [float(candle["c"]) for candle in candles if candle.get("c") is not None]
    volumes = [float(candle.get("v", 0) or 0) for candle in candles]

    if len(closes) < 210:
        return {"signal": "NONE", "reason": "Not enough candles for EMA 200"}

    ema9 = ema_series(closes, 9)
    ema21 = ema_series(closes, 21)
    ema200 = ema_series(closes, 200)

    window = min(20, len(volumes))
    avg_volume = sum(volumes[-window:]) / window
    current_hour = datetime.now(timezone.utc).hour
    in_trading_window = 6 <= current_hour < 18

    latest_close = closes[-1]
    current_ema9 = ema9[-1]
    current_ema21 = ema21[-1]
    current_ema200 = ema200[-1]
    prev_ema9 = ema9[-2]
    prev_ema21 = ema21[-2]

    volume_confirmed = volumes[-1] > avg_volume * 1.2
    trend_bullish = current_ema21 > current_ema200 and latest_close > current_ema200
    trend_bearish = current_ema21 < current_ema200 and latest_close < current_ema200

    if in_trading_window and volume_confirmed and current_ema9 > current_ema21 and prev_ema9 <= prev_ema21 and trend_bullish:
        return {
            "signal": "LONG",
            "price": latest_close,
            "reason": "EMA 9/21 bullish cross with trend confirmation and high volume",
        }

    if in_trading_window and volume_confirmed and current_ema9 < current_ema21 and prev_ema9 >= prev_ema21 and trend_bearish:
        return {
            "signal": "SHORT",
            "price": latest_close,
            "reason": "EMA 9/21 bearish cross with trend confirmation and high volume",
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


if __name__ == "__main__":
    print("Iniciando análisis de mercado en Hyperliquid...")
    try:
        main()
    except Exception as e:
        print(f"Error inesperado durante la ejecución: {e}")