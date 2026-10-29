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
        "passed": m["vol_now"] > m["vol_sma"],
        "detail": {"volume": m["vol_now"], "volume_sma20": m["vol_sma"]},
    }
    l5 = {"name": "L5 ADX Anti-Sideways", "passed": m["adx"] > config.ADX_MIN, "detail": {"adx": m["adx"]}}
    return l4, l5, tol


def _ema_stack(base):
    values = [float(ind.ema(base["close"], period).iloc[-1]) for period in config.EMA_STACK_PERIODS]
    tol = config.EMA_STACK_TOLERANCE_PCT / 100.0
    e7, e10, e20, e50 = values
    bull = e7 >= e50 * (1.0 - tol) and e20 >= e50 * (1.0 - tol)
    bear = e7 <= e50 * (1.0 + tol) and e20 <= e50 * (1.0 + tol)
    detail = {"ema7": e7, "ema10": e10, "ema20": e20, "ema50": e50}
    return bull, bear, detail


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


def evaluate(symbol, base):
    m = _metrics(base)
    bull_stack, bear_stack, stack_detail = _ema_stack(base)
    long_layers = _long_layers(m)
    short_layers = _short_layers(m)
    long_layers.append({"name": "L6 EMA 7/10 vs 50", "passed": bull_stack, "detail": dict(stack_detail)})
    short_layers.append({"name": "L6 EMA 7/10 vs 50", "passed": bear_stack, "detail": dict(stack_detail)})
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
