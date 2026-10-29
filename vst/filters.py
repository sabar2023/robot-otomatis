import config
import indicators as ind


def _metrics(base):
    close = float(base["close"].iloc[-1])
    ema200 = float(ind.ema(base["close"], config.EMA_TREND_PERIOD).iloc[-1])
    swing_low = float(ind.swing_low(base, config.SWING_LOOKBACK).iloc[-1])
    swing_high = float(ind.swing_high(base, config.SWING_LOOKBACK).iloc[-1])
    rsi_series = ind.rsi(base["close"], config.RSI_PERIOD)
    rsi_now = float(rsi_series.iloc[-1])
    rsi_prev = float(rsi_series.iloc[-2])
    vol_sma = float(ind.sma(base["volume"], config.VOLUME_SMA_PERIOD).iloc[-1])
    vol_now = float(base["volume"].iloc[-1])
    adx_now = float(ind.adx(base, config.ADX_PERIOD).iloc[-1])
    atr_now = float(ind.atr(base, config.ATR_PERIOD).iloc[-1])
    return {
        "close": close,
        "ema200": ema200,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "rsi_now": rsi_now,
        "rsi_prev": rsi_prev,
        "vol_now": vol_now,
        "vol_sma": vol_sma,
        "adx": adx_now,
        "atr": atr_now,
    }


def _common_layers(m):
    tol = config.SUPPORT_TOLERANCE_PCT / 100.0
    l4 = {
        "name": "L4 Validasi Volume",
        "passed": m["vol_now"] > m["vol_sma"] * config.VOLUME_MULT,
        "detail": {"volume": m["vol_now"], "volume_sma20": m["vol_sma"]},
    }
    l5 = {"name": "L5 ADX Anti-Sideways", "passed": m["adx"] > config.ADX_MIN, "detail": {"adx": m["adx"]}}
    return l4, l5, tol


def _daily_trend(df):
    if df is None or len(df) < config.DAILY_TREND_PERIOD + config.DAILY_SLOPE_BARS + 1:
        return None
    close = float(df["close"].iloc[-1])
    series = ind.ema(df["close"], config.DAILY_TREND_PERIOD)
    now = float(series.iloc[-1])
    then = float(series.iloc[-1 - config.DAILY_SLOPE_BARS])
    return {
        "bull": close > now and now > then,
        "bear": close < now and now < then,
        "close": close,
        "ema50": now,
        "ema50_then": then,
    }


def _trend_layers(daily, btc_daily):
    d = _daily_trend(daily)
    b = _daily_trend(btc_daily)
    if d is None:
        l7 = {"name": "L7 Tren Harian EMA-50", "passed": False, "detail": {"data": "tidak tersedia"}}
    else:
        l7 = {
            "name": "L7 Tren Harian EMA-50",
            "passed": d["bull"],
            "detail": {"close_d1": d["close"], "ema50_d1": d["ema50"], "ema50_then": d["ema50_then"]},
        }
    if b is None:
        l8 = {"name": "L8 Tren BTC Harian", "passed": False, "detail": {"data": "tidak tersedia"}}
    else:
        l8 = {
            "name": "L8 Tren BTC Harian",
            "passed": b["bull"],
            "detail": {"btc_close_d1": b["close"], "btc_ema50_d1": b["ema50"], "btc_ema50_then": b["ema50_then"]},
        }
    if d is None:
        l7_short = {"name": "L7 Tren Harian EMA-50", "passed": False, "detail": {"data": "tidak tersedia"}}
    else:
        l7_short = {
            "name": "L7 Tren Harian EMA-50",
            "passed": d["bear"],
            "detail": {"close_d1": d["close"], "ema50_d1": d["ema50"], "ema50_then": d["ema50_then"]},
        }
    if b is None:
        l8_short = {"name": "L8 Tren BTC Harian", "passed": False, "detail": {"data": "tidak tersedia"}}
    else:
        l8_short = {
            "name": "L8 Tren BTC Harian",
            "passed": b["bear"],
            "detail": {"btc_close_d1": b["close"], "btc_ema50_d1": b["ema50"], "btc_ema50_then": b["ema50_then"]},
        }
    return l7, l8, l7_short, l8_short


def _ema_stack(base):
    values = [float(ind.ema(base["close"], period).iloc[-1]) for period in config.EMA_STACK_PERIODS]
    tol = config.EMA_STACK_TOLERANCE_PCT / 100.0
    e7, e10, e20, e50 = values
    if config.EMA_STACK_MODE == "med":
        bull = e20 >= e50 * (1.0 - tol)
        bear = e20 <= e50 * (1.0 + tol)
        name = "L6 EMA 20 vs 50"
        detail = {"ema20": e20, "ema50": e50}
    else:
        bull = e7 >= e50 * (1.0 - tol) and e20 >= e50 * (1.0 - tol)
        bear = e7 <= e50 * (1.0 + tol) and e20 <= e50 * (1.0 + tol)
        name = "L6 EMA 7/10 vs 50"
        detail = {"ema7": e7, "ema10": e10, "ema20": e20, "ema50": e50}
    return bull, bear, name, detail


def _long_layers(m):
    l4, l5, tol = _common_layers(m)
    l1 = {
        "name": "L1 Tren EMA-200",
        "passed": m["close"] > m["ema200"],
        "detail": {"close": m["close"], "ema200": m["ema200"]},
    }
    l2 = {
        "name": f"L2 Support Swing-{config.SWING_LOOKBACK}",
        "passed": m["close"] <= m["swing_low"] * (1.0 + tol),
        "detail": {"close": m["close"], "swing_low": m["swing_low"]},
    }
    l3 = {
        "name": "L3 RSI Momentum Naik",
        "passed": m["rsi_prev"] < config.RSI_ENTRY_LONG_LO and m["rsi_now"] > m["rsi_prev"],
        "detail": {"rsi": m["rsi_now"], "rsi_prev": m["rsi_prev"]},
    }
    return [l1, l2, l3, l4, l5]


def _short_layers(m):
    l4, l5, tol = _common_layers(m)
    l1 = {
        "name": "L1 Tren EMA-200",
        "passed": m["close"] < m["ema200"],
        "detail": {"close": m["close"], "ema200": m["ema200"]},
    }
    l2 = {
        "name": f"L2 Resistance Swing-{config.SWING_LOOKBACK}",
        "passed": m["close"] >= m["swing_high"] * (1.0 - tol),
        "detail": {"close": m["close"], "swing_high": m["swing_high"]},
    }
    l3 = {
        "name": "L3 RSI Momentum Turun",
        "passed": m["rsi_prev"] > config.RSI_ENTRY_SHORT_HI and m["rsi_now"] < m["rsi_prev"],
        "detail": {"rsi": m["rsi_now"], "rsi_prev": m["rsi_prev"]},
    }
    return [l1, l2, l3, l4, l5]


def evaluate(symbol, base, daily=None, btc_daily=None):
    m = _metrics(base)
    l7, l8, l7_short, l8_short = _trend_layers(daily, btc_daily)
    bull_stack, bear_stack, stack_name, stack_detail = _ema_stack(base)
    long_layers = _long_layers(m)
    short_layers = _short_layers(m)
    long_layers.append({"name": stack_name, "passed": bull_stack, "detail": dict(stack_detail)})
    short_layers.append({"name": stack_name, "passed": bear_stack, "detail": dict(stack_detail)})
    long_layers.append(l7)
    long_layers.append(l8)
    short_layers.append(l7_short)
    short_layers.append(l8_short)
    long_pass = all(layer["passed"] for layer in long_layers)
    short_pass = all(layer["passed"] for layer in short_layers)

    if long_pass and not short_pass:
        direction, layers = "LONG", long_layers
    elif short_pass and not long_pass:
        direction, layers = "SHORT", short_layers
    else:
        direction = None
        layers = long_layers if m["close"] >= m["ema200"] else short_layers

    candle_open = base["ts"].iloc[-1]
    return {
        "symbol": symbol,
        "timeframe": config.TIMEFRAME_LABEL,
        "candle_open": candle_open,
        "price": m["close"],
        "atr": m["atr"],
        "direction": direction,
        "passed": direction is not None,
        "layers": layers,
        "failed_layers": [layer["name"] for layer in layers if not layer["passed"]],
    }
