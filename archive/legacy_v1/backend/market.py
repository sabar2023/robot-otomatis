import random
import time
from collections import deque

PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]

BASE_PRICES = {
    "BTC/USDT": 64250.0,
    "ETH/USDT": 3120.0,
    "SOL/USDT": 148.4,
    "BNB/USDT": 585.0,
}

VOL = {
    "BTC/USDT": 0.0018,
    "ETH/USDT": 0.0024,
    "SOL/USDT": 0.0036,
    "BNB/USDT": 0.0021,
}


class MarketSimulator:
    def __init__(self, history_len=120):
        self.history_len = history_len
        self.candles = {p: deque(maxlen=history_len) for p in PAIRS}
        self.last = dict(BASE_PRICES)
        now = int(time.time())
        for pair in PAIRS:
            price = BASE_PRICES[pair]
            for i in range(history_len):
                ts = now - (history_len - i) * 60
                candle = self._step(pair, price, ts)
                price = candle["close"]
                self.candles[pair].append(candle)
            self.last[pair] = price

    def _step(self, pair, price, ts):
        sigma = VOL[pair]
        drift = 0.00004
        shock = random.gauss(drift, sigma)
        if random.random() < 0.04:
            shock += random.choice([-1, 1]) * sigma * 4
        o = price
        c = max(price * (1 + shock), price * 0.0001)
        high = max(o, c) * (1 + abs(random.gauss(0, sigma * 0.4)))
        low = min(o, c) * (1 - abs(random.gauss(0, sigma * 0.4)))
        volume = abs(random.gauss(120, 40)) * (1 + abs(shock) * 40)
        return {
            "timestamp": ts,
            "open": round(o, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(c, 4),
            "volume": round(volume, 2),
        }

    def tick(self):
        ts = int(time.time())
        snapshot = {}
        for pair in PAIRS:
            last_close = self.last[pair]
            candle = self._step(pair, last_close, ts)
            self.last[pair] = candle["close"]
            self.candles[pair].append(candle)
            snapshot[pair] = candle
        return snapshot

    def ohlcv(self, pair):
        return list(self.candles.get(pair, []))

    def ticker(self):
        out = {}
        for pair in PAIRS:
            series = list(self.candles[pair])
            if not series:
                continue
            last = series[-1]["close"]
            prev = series[-2]["close"] if len(series) > 1 else last
            change = ((last - prev) / prev) * 100 if prev else 0
            out[pair] = {
                "pair": pair,
                "price": last,
                "change_pct": round(change, 3),
                "high": series[-1]["high"],
                "low": series[-1]["low"],
                "volume": series[-1]["volume"],
            }
        return out


class HybridMarket:
    """Sumber data pasar Live: prioritas CCXT (Binance/OKX), fallback ke simulator.

    Sesuai PRD, mesin Python menarik data harga gratis via CCXT. Bila bursa
    tidak dapat dijangkau (offline/rate limit), simulator lokal dipakai agar
    engine tetap berjalan tanpa memalsukan order Live.
    """

    def __init__(self):
        self.sim = MarketSimulator()
        self.source = "SIMULATOR"
        self.last_error = ""

    def refresh_live(self, exchange_id, pairs):
        from execution import router

        tickers = router.fetch_ticker(exchange_id, pairs)
        if not tickers:
            self.source = "SIMULATOR"
            self.last_error = router.last_error
            return False
        self.source = f"LIVE:{exchange_id}"
        self.last_error = ""
        for pair, t in tickers.items():
            if pair not in self.sim.candles:
                continue
            last = t["price"]
            prev = self.sim.candles[pair][-1]["close"] if self.sim.candles[pair] else last
            self.sim.candles[pair].append(
                {
                    "timestamp": int(time.time()),
                    "open": prev,
                    "high": max(prev, last),
                    "low": min(prev, last),
                    "close": last,
                    "volume": t["volume"],
                }
            )
            self.sim.last[pair] = last
        return True

    def tick(self, exchange_id=None, pairs=None):
        if exchange_id and pairs:
            if self.refresh_live(exchange_id, pairs):
                return self.ticker()
        self.source = "SIMULATOR"
        return self.sim.tick()

    def ohlcv(self, pair):
        return self.sim.ohlcv(pair)

    def ticker(self):
        return self.sim.ticker()

    def info(self):
        return {"source": self.source, "last_error": self.last_error}


def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return None, None, None
    macd_line = ema(closes, fast) - ema(closes, slow)
    macd_series = []
    for i in range(slow, len(closes) + 1):
        window = closes[:i]
        if len(window) < slow:
            continue
        macd_series.append(ema(window, fast) - ema(window, slow))
    if len(macd_series) < signal:
        return macd_line, None, None
    signal_line = ema(macd_series, signal)
    hist = macd_line - signal_line if signal_line is not None else None
    return macd_line, signal_line, hist


def atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-period:]) / period


def support_resistance(candles, lookback=40):
    window = candles[-lookback:] if len(candles) >= lookback else candles
    if not window:
        return None, None
    lows = sorted(c["low"] for c in window)
    highs = sorted(c["high"] for c in window)
    support = sum(lows[: max(1, len(lows) // 5)]) / max(1, len(lows) // 5)
    resistance = sum(highs[-max(1, len(highs) // 5) :]) / max(1, len(highs) // 5)
    return support, resistance
