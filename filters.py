import config
import indicators as ind


def _side_metrics(base, higher):
    close = float(base["close"].iloc[-1])
    prev_close = float(base["close"].iloc[-2])
    ema200_base = float(ind.ema(base["close"], config.EMA_TREND_BASE).iloc[-1])
    close_high = float(higher["close"].iloc[-1])
    ema50_high = float(ind.ema(higher["close"], config.EMA_TREND_HIGHER).iloc[-1])
    support = float(ind.swing_support(base, config.SWING_LOOKBACK))
    resistance = float(ind.swing_resistance(base, config.SWING_LOOKBACK))
    support_prev = float(base["low"].iloc[-config.SWING_LOOKBACK - 1:-1].min())
    resistance_prev = float(ind.swing_resistance_prev(base, config.SWING_LOOKBACK))
    vwap = float(ind.session_vwap(base).iloc[-1])
    rsi_series = ind.rsi(base["close"], config.RSI_PERIOD)
    rsi_now = float(rsi_series.iloc[-1])
    rsi_prev = float(rsi_series.iloc[-2])
    volume = base["volume"]
    vol_now = float(volume.iloc[-1])
    vol_sma = float(volume.rolling(config.VOLUME_SMA_PERIOD).mean().iloc[-2])
    adx_now = float(ind.adx(base, config.ADX_PERIOD).iloc[-1])
    return {
        "close": close,
        "prev_close": prev_close,
        "ema200_base": ema200_base,
        "close_high": close_high,
        "ema50_high": ema50_high,
        "support": support,
        "resistance": resistance,
        "support_prev": support_prev,
        "resistance_prev": resistance_prev,
        "vwap": vwap,
        "rsi_now": rsi_now,
        "rsi_prev": rsi_prev,
        "vol_now": vol_now,
        "vol_sma": vol_sma,
        "adx": adx_now,
    }


def _l5_long(btc_base, is_altcoin):
    if not is_altcoin:
        return True, {"note": "BTC adalah referensi, layer dilewati"}
    close = float(btc_base["close"].iloc[-1])
    support = float(ind.swing_support(btc_base, config.SWING_LOOKBACK))
    ema200 = float(ind.ema(btc_base["close"], config.EMA_TREND_BASE).iloc[-1])
    support_break = close < support
    far_below_ema200 = close < ema200 * (1.0 - config.BTC_FAR_BELOW_EMA_PCT / 100.0)
    passed = not (support_break or far_below_ema200)
    return passed, {
        "btc_close": close,
        "btc_support": support,
        "btc_ema200": ema200,
        "support_break": support_break,
        "far_below_ema200": far_below_ema200,
    }


def _l5_short(btc_base, is_altcoin):
    if not is_altcoin:
        return True, {"note": "BTC adalah referensi, layer dilewati"}
    close = float(btc_base["close"].iloc[-1])
    resistance = float(ind.swing_resistance(btc_base, config.SWING_LOOKBACK))
    ema200 = float(ind.ema(btc_base["close"], config.EMA_TREND_BASE).iloc[-1])
    resistance_break = close > resistance
    far_above_ema200 = close > ema200 * (1.0 + config.BTC_FAR_BELOW_EMA_PCT / 100.0)
    passed = not (resistance_break or far_above_ema200)
    return passed, {
        "btc_close": close,
        "btc_resistance": resistance,
        "btc_ema200": ema200,
        "support_break": resistance_break,
        "far_below_ema200": far_above_ema200,
    }


def _long_layers(m, btc_base, is_altcoin):
    tol = config.SUPPORT_TOLERANCE_PCT / 100.0
    l1 = m["close"] > m["ema200_base"] and m["close_high"] > m["ema50_high"]
    l1_detail = {
        "close_base": m["close"],
        "ema200_base": m["ema200_base"],
        "close_high": m["close_high"],
        "ema50_high": m["ema50_high"],
    }

    near_support = m["support"] * (1.0 - tol) <= m["close"] <= m["support"] * (1.0 + tol)
    breakout_up = m["prev_close"] <= m["resistance_prev"] < m["close"]
    above_vwap = m["close"] > m["vwap"]
    l2 = (near_support or breakout_up) and above_vwap
    l2_detail = {
        "support": m["support"],
        "resistance": m["resistance_prev"],
        "vwap": m["vwap"],
        "near_support": near_support,
        "breakout": breakout_up,
        "above_vwap": above_vwap,
    }

    bounce = m["rsi_prev"] < config.RSI_OVERSOLD and m["rsi_now"] >= config.RSI_OVERSOLD
    strong = m["rsi_now"] > config.RSI_STRONG
    volume_ok = m["vol_now"] > m["vol_sma"]
    l3 = (bounce or strong) and volume_ok
    l3_detail = {
        "rsi": m["rsi_now"],
        "rsi_prev": m["rsi_prev"],
        "bounce": bounce,
        "strong": strong,
        "volume": m["vol_now"],
        "volume_sma20": m["vol_sma"],
        "volume_ratio": m["vol_now"] / m["vol_sma"] if m["vol_sma"] > 0 else 0.0,
    }

    l4 = m["adx"] > config.ADX_MIN
    l5, l5_detail = _l5_long(btc_base, is_altcoin)

    return [
        {"name": "L1 Tren Multi-TF", "passed": l1, "detail": l1_detail},
        {"name": "L2 Zona + VWAP", "passed": l2, "detail": l2_detail},
        {"name": "L3 Momentum + Volume", "passed": l3, "detail": l3_detail},
        {"name": "L4 ADX Anti-Sideways", "passed": l4, "detail": {"adx": m["adx"]}},
        {"name": "L5 Bitcoin Rule", "passed": l5, "detail": l5_detail},
    ]


def _short_layers(m, btc_base, is_altcoin):
    tol = config.SUPPORT_TOLERANCE_PCT / 100.0
    l1 = m["close"] < m["ema200_base"] and m["close_high"] < m["ema50_high"]
    l1_detail = {
        "close_base": m["close"],
        "ema200_base": m["ema200_base"],
        "close_high": m["close_high"],
        "ema50_high": m["ema50_high"],
    }

    near_resistance = m["resistance"] * (1.0 - tol) <= m["close"] <= m["resistance"] * (1.0 + tol)
    breakdown_down = m["prev_close"] >= m["support_prev"] > m["close"]
    below_vwap = m["close"] < m["vwap"]
    l2 = (near_resistance or breakdown_down) and below_vwap
    l2_detail = {
        "support": m["support_prev"],
        "resistance": m["resistance"],
        "vwap": m["vwap"],
        "near_support": near_resistance,
        "breakout": breakdown_down,
        "above_vwap": below_vwap,
    }

    dead_cross = m["rsi_prev"] > config.RSI_OVERBOUGHT and m["rsi_now"] <= config.RSI_OVERBOUGHT
    weak = m["rsi_now"] < config.RSI_WEAK
    volume_ok = m["vol_now"] > m["vol_sma"]
    l3 = (dead_cross or weak) and volume_ok
    l3_detail = {
        "rsi": m["rsi_now"],
        "rsi_prev": m["rsi_prev"],
        "bounce": dead_cross,
        "strong": weak,
        "volume": m["vol_now"],
        "volume_sma20": m["vol_sma"],
        "volume_ratio": m["vol_now"] / m["vol_sma"] if m["vol_sma"] > 0 else 0.0,
    }

    l4 = m["adx"] > config.ADX_MIN
    l5, l5_detail = _l5_short(btc_base, is_altcoin)

    return [
        {"name": "L1 Tren Multi-TF", "passed": l1, "detail": l1_detail},
        {"name": "L2 Zona + VWAP", "passed": l2, "detail": l2_detail},
        {"name": "L3 Momentum + Volume", "passed": l3, "detail": l3_detail},
        {"name": "L4 ADX Anti-Sideways", "passed": l4, "detail": {"adx": m["adx"]}},
        {"name": "L5 Bitcoin Rule", "passed": l5, "detail": l5_detail},
    ]


def evaluate(symbol, base, higher, btc_base, is_altcoin):
    m = _side_metrics(base, higher)
    long_layers = _long_layers(m, btc_base, is_altcoin)
    short_layers = _short_layers(m, btc_base, is_altcoin)
    long_pass = all(layer["passed"] for layer in long_layers)
    short_pass = all(layer["passed"] for layer in short_layers)

    if long_pass and not short_pass:
        direction, layers = "LONG", long_layers
    elif short_pass and not long_pass:
        direction, layers = "SHORT", short_layers
    else:
        direction = None
        layers = long_layers if m["close"] > m["ema200_base"] else short_layers

    failed = [layer["name"] for layer in layers if not layer["passed"]]
    atr_value = float(ind.atr(base, config.ATR_PERIOD).iloc[-1])
    return {
        "symbol": symbol,
        "is_altcoin": is_altcoin,
        "price": m["close"],
        "atr": atr_value,
        "timeframe": config.TIMEFRAME_LABEL,
        "direction": direction,
        "layers": layers,
        "passed": direction is not None,
        "failed_layers": failed,
    }
