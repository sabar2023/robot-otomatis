import time

import ccxt
import pandas as pd

COLUMNS = ["ts", "open", "high", "low", "close", "volume"]
FALLBACK_EXCHANGES = ["bybit", "kraken", "bitget", "gate", "kucoin"]
MAX_RETRIES = 2


def build_exchange(exchange_id):
    klass = getattr(ccxt, exchange_id)
    return klass({"enableRateLimit": True, "timeout": 20000})


def build_chain(primary_id):
    chain = []
    seen = set()
    for cid in [primary_id] + FALLBACK_EXCHANGES:
        if cid in seen or cid not in ccxt.exchanges:
            continue
        seen.add(cid)
        chain.append(build_exchange(cid))
    return chain


def fetch_ohlcv(exchange, symbol, timeframe, limit):
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not raw:
                raise RuntimeError("respons OHLCV kosong")
            df = pd.DataFrame(raw, columns=COLUMNS)
            df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
            return df
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Gagal di {exchange.id}: {str(last_error).splitlines()[0]}")


def make_fetcher(chain):
    order = list(chain)

    def fetch(symbol, timeframe, limit):
        errors = []
        for exchange in order:
            try:
                df = fetch_ohlcv(exchange, symbol, timeframe, limit)
                if exchange is not order[0]:
                    order.remove(exchange)
                    order.insert(0, exchange)
                return df, exchange.id
            except Exception as exc:
                errors.append(str(exc).splitlines()[0][:120])
        raise RuntimeError(f"Semua bursa gagal untuk {symbol} {timeframe}:\n  " + "\n  ".join(errors))

    return fetch


def closed_candles(df):
    return df.iloc[:-1].reset_index(drop=True)
