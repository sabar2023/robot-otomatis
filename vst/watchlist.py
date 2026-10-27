import re

import config

SWAP_USDT = re.compile(r"^[A-Z0-9]+/USDT:USDT$")


def default_watchlist(chain, limit=None):
    limit = limit or config.WATCHLIST_SIZE
    errors = []
    for exchange in chain:
        try:
            tickers = exchange.fetch_tickers()
            rows = []
            for symbol, ticker in (tickers or {}).items():
                if not SWAP_USDT.match(symbol):
                    continue
                quote_volume = float((ticker or {}).get("quoteVolume") or 0)
                if quote_volume > 0:
                    rows.append((symbol, quote_volume))
            if not rows:
                raise RuntimeError("tidak ada ticker USDT swap")
            rows.sort(key=lambda item: item[1], reverse=True)
            return [symbol for symbol, _ in rows[:limit]], exchange.id
        except Exception as exc:
            errors.append(f"{exchange.id}: {str(exc).splitlines()[0][:80]}")
    raise RuntimeError("Gagal memuat watchlist default:\n  " + "\n  ".join(errors))
