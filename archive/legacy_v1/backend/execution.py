import logging

import database as db

try:
    import ccxt
except ImportError:
    ccxt = None


log = logging.getLogger("execution")

SUPPORTED_EXCHANGES = ["binance", "okx", "bybit", "kucoin"]


class ExecutionRouter:
    def __init__(self):
        self.last_error = ""

    def _public_exchange(self, exchange_id):
        if ccxt is None:
            raise RuntimeError("ccxt not installed")
        return getattr(ccxt, exchange_id)({"enableRateLimit": True})

    def _private_exchange(self, secrets):
        if ccxt is None:
            raise RuntimeError("ccxt not installed")
        exchange_id = secrets.get("exchange_id") or "binance"
        klass = getattr(ccxt, exchange_id, None)
        if klass is None:
            raise RuntimeError(f"exchange {exchange_id} unsupported")
        return klass(
            {
                "apiKey": secrets.get("api_key"),
                "secret": secrets.get("api_secret"),
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )

    def fetch_ohlcv(self, exchange_id, pair, timeframe="1m", limit=120):
        try:
            exchange = self._public_exchange(exchange_id)
            raw = exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
            return [
                {
                    "timestamp": int(row[0] / 1000),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
                for row in raw
            ]
        except Exception as exc:
            self.last_error = str(exc)
            log.warning("fetch_ohlcv failed: %s", exc)
            return None

    def fetch_ticker(self, exchange_id, pairs):
        try:
            exchange = self._public_exchange(exchange_id)
            out = {}
            for pair in pairs:
                t = exchange.fetch_ticker(pair)
                last = t.get("last") or t.get("close")
                prev = t.get("previousClose") or last
                change = ((last - prev) / prev) * 100 if prev else 0
                out[pair] = {
                    "pair": pair,
                    "price": float(last),
                    "change_pct": round(change, 3),
                    "high": float(t.get("high") or last),
                    "low": float(t.get("low") or last),
                    "volume": float(t.get("baseVolume") or 0),
                }
            return out
        except Exception as exc:
            self.last_error = str(exc)
            log.warning("fetch_ticker failed: %s", exc)
            return None

    def place_bracket_buy(self, pair, quote_amount, stop_loss, take_profit):
        """Mengirim order Live + bracket TP/SL ke bursa via CCXT.

        Mengembalikan dict berisi status dan id order. Jika kredensial atau
        bursa tidak tersedia, status 'UNAVAILABLE' dikembalikan agar engine
        menolak order Live (tidak memalsukan eksekusi).
        """
        secrets = db.get_secrets()
        if not secrets.get("api_key") or not secrets.get("api_secret"):
            return {"status": "UNAVAILABLE", "reason": "Exchange API key/secret belum dikonfigurasi."}
        try:
            exchange = self._private_exchange(secrets)
            exchange.load_markets()
            ticker = exchange.fetch_ticker(pair)
            price = float(ticker["last"])
            amount = float(quote_amount) / price
            amount = float(exchange.amount_to_precision(pair, amount))
            if amount <= 0:
                return {"status": "REJECTED", "reason": "Jumlah order nol."}

            params = {
                "stopLoss": {"triggerPrice": float(exchange.price_to_precision(pair, stop_loss))},
                "takeProfit": {"triggerPrice": float(exchange.price_to_precision(pair, take_profit))},
            }
            order = exchange.create_order(pair, "market", "buy", amount, None, params)
            return {
                "status": "FILLED",
                "reason": f"Live bracket order tereksekusi di {secrets['exchange_id']}.",
                "order_id": str(order.get("id", "")),
                "price": price,
                "amount": amount,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            }
        except Exception as exc:
            self.last_error = str(exc)
            return {"status": "ERROR", "reason": f"Order Live gagal: {exc}"}

    def connection_status(self):
        secrets = db.get_secrets()
        status = {
            "exchange_id": secrets.get("exchange_id"),
            "ccxt_installed": ccxt is not None,
            "has_credentials": bool(secrets.get("api_key") and secrets.get("api_secret")),
            "live_ready": False,
            "last_error": self.last_error,
        }
        if ccxt is None:
            return status
        try:
            exchange = self._public_exchange(secrets.get("exchange_id") or "binance")
            exchange.load_markets()
            status["public_ok"] = True
        except Exception as exc:
            status["public_ok"] = False
            status["last_error"] = str(exc)
        if status["has_credentials"]:
            try:
                private = self._private_exchange(secrets)
                private.load_markets()
                private.fetch_balance()
                status["live_ready"] = True
            except Exception as exc:
                status["last_error"] = str(exc)
        return status


router = ExecutionRouter()
