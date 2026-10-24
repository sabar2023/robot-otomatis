import config
import indicators as ind


def layer1_trend(m15, h1):
    close_m15 = float(m15["close"].iloc[-1])
    ema200_m15 = float(ind.ema(m15["close"], config.EMA_TREND_M15).iloc[-1])
    close_h1 = float(h1["close"].iloc[-1])
    ema50_h1 = float(ind.ema(h1["close"], config.EMA_TREND_H1).iloc[-1])
    passed = close_m15 > ema200_m15 and close_h1 > ema50_h1
    detail = {
        "close_m15": close_m15,
        "ema200_m15": ema200_m15,
        "close_h1": close_h1,
        "ema50_h1": ema50_h1,
    }
    return passed, detail


def layer2_zone_vwap(m15):
    close = float(m15["close"].iloc[-1])
    prev_close = float(m15["close"].iloc[-2])
    support = float(ind.swing_support(m15, config.SWING_LOOKBACK))
    resistance = float(ind.swing_resistance_prev(m15, config.SWING_LOOKBACK))
    tol = config.SUPPORT_TOLERANCE_PCT / 100.0
    near_support = support * (1.0 - tol) <= close <= support * (1.0 + tol)
    breakout = prev_close <= resistance < close
    vwap = float(ind.session_vwap(m15).iloc[-1])
    above_vwap = close > vwap
    passed = (near_support or breakout) and above_vwap
    detail = {
        "support": support,
        "resistance": resistance,
        "vwap": vwap,
        "near_support": near_support,
        "breakout": breakout,
        "above_vwap": above_vwap,
    }
    return passed, detail


def layer3_momentum_volume(m15):
    rsi_series = ind.rsi(m15["close"], config.RSI_PERIOD)
    rsi_now = float(rsi_series.iloc[-1])
    rsi_prev = float(rsi_series.iloc[-2])
    bounce = rsi_prev < config.RSI_OVERSOLD and rsi_now >= config.RSI_OVERSOLD
    strong = rsi_now > config.RSI_STRONG
    volume = m15["volume"]
    vol_now = float(volume.iloc[-1])
    vol_sma = float(volume.rolling(config.VOLUME_SMA_PERIOD).mean().iloc[-2])
    volume_ok = vol_now > vol_sma
    ratio = vol_now / vol_sma if vol_sma > 0 else 0.0
    passed = (bounce or strong) and volume_ok
    detail = {
        "rsi": rsi_now,
        "rsi_prev": rsi_prev,
        "bounce": bounce,
        "strong": strong,
        "volume": vol_now,
        "volume_sma20": vol_sma,
        "volume_ratio": ratio,
    }
    return passed, detail


def layer4_adx(m15):
    adx_now = float(ind.adx(m15, config.ADX_PERIOD).iloc[-1])
    passed = adx_now > config.ADX_MIN
    return passed, {"adx": adx_now}


def layer5_btc_rule(btc_m15):
    close = float(btc_m15["close"].iloc[-1])
    support = float(ind.swing_support(btc_m15, config.SWING_LOOKBACK))
    ema200 = float(ind.ema(btc_m15["close"], config.EMA_TREND_M15).iloc[-1])
    support_break = close < support
    far_below_ema200 = close < ema200 * (1.0 - config.BTC_FAR_BELOW_EMA_PCT / 100.0)
    passed = not (support_break or far_below_ema200)
    detail = {
        "btc_close": close,
        "btc_support": support,
        "btc_ema200": ema200,
        "support_break": support_break,
        "far_below_ema200": far_below_ema200,
    }
    return passed, detail


def evaluate(symbol, m15, h1, btc_m15, is_altcoin):
    l1, d1 = layer1_trend(m15, h1)
    l2, d2 = layer2_zone_vwap(m15)
    l3, d3 = layer3_momentum_volume(m15)
    l4, d4 = layer4_adx(m15)

    layers = [
        {"name": "L1 Tren Multi-TF", "passed": l1, "detail": d1},
        {"name": "L2 Zona + VWAP", "passed": l2, "detail": d2},
        {"name": "L3 Momentum + Volume", "passed": l3, "detail": d3},
        {"name": "L4 ADX Anti-Sideways", "passed": l4, "detail": d4},
    ]

    if is_altcoin:
        l5, d5 = layer5_btc_rule(btc_m15)
        layers.append({"name": "L5 Bitcoin Rule", "passed": l5, "detail": d5})
    else:
        layers.append({"name": "L5 Bitcoin Rule", "passed": True, "detail": {"note": "BTC adalah referensi, layer dilewati"}})

    passed = all(layer["passed"] for layer in layers)
    failed = [layer["name"] for layer in layers if not layer["passed"]]
    atr_value = float(ind.atr(m15, config.ATR_PERIOD).iloc[-1])
    return {
        "symbol": symbol,
        "is_altcoin": is_altcoin,
        "price": float(m15["close"].iloc[-1]),
        "atr": atr_value,
        "timeframe": "M15",
        "layers": layers,
        "passed": passed,
        "failed_layers": failed,
    }
