import time

import ccxt
import pandas as pd

import config

COLUMNS = ["ts", "open", "high", "low", "close", "volume"]
MAX_RETRIES = 2


def build_exchange(exchange_id):
    return getattr(ccxt, exchange_id)(
        {"enableRateLimit": True, "timeout": 20000, "options": {"defaultType": "swap"}}
    )


def build_chain():
    primary = config.DATA_EXCHANGES[0] if config.DATA_EXCHANGES else "bingx"
    ordered = [primary] + [e for e in config.DATA_EXCHANGES if e != primary]
    chain = []
    for cid in ordered:
        if cid in ccxt.exchanges:
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
