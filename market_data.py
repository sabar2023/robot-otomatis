import time

import ccxt
import pandas as pd

COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


def build_exchange(exchange_id):
    klass = getattr(ccxt, exchange_id)
    return klass({"enableRateLimit": True, "timeout": 20000})


def fetch_ohlcv(exchange, symbol, timeframe, limit):
    last_error = None
    for attempt in range(3):
        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not raw:
                raise RuntimeError("respons OHLCV kosong")
            df = pd.DataFrame(raw, columns=COLUMNS)
            df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
            return df
        except Exception as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Gagal mengambil OHLCV {symbol} {timeframe} setelah 3 percobaan: {last_error}")


def closed_candles(df):
    return df.iloc[:-1].reset_index(drop=True)
