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
    ema20 = float(ind.ema(base["close"], config.EMA_STACK_PERIODS[2]).iloc[-1])
    ema50 = float(ind.ema(base["close"], config.EMA_STACK_PERIODS[3]).iloc[-1])
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
        "ema20": ema20,
        "ema50": ema50,
    }


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


def _trend_direction_layer(m, coin_trend, btc_trend, direction):
    stack_tol = config.EMA_STACK_TOLERANCE_PCT / 100.0
    if direction == "LONG":
        trend = m["close"] > m["ema200"] and m["ema20"] >= m["ema50"] * (1.0 - stack_tol)
    else:
        trend = m["close"] < m["ema200"] and m["ema20"] <= m["ema50"] * (1.0 + stack_tol)
    return {
        "name": "L1 Tren Arah",
        "passed": trend,
        "detail": {"close": m["close"], "ema200": m["ema200"], "ema20": m["ema20"], "ema50": m["ema50"]},
    }


def _pullback_layer(m, direction):
    tol = config.SUPPORT_TOLERANCE_PCT / 100.0
    if direction == "LONG":
        passed = m["close"] <= m["swing_low"] * (1.0 + tol)
        detail = {"close": m["close"], "swing_low": m["swing_low"]}
        name = "L2 Pullback Support"
    else:
        passed = m["close"] >= m["swing_high"] * (1.0 - tol)
        detail = {"close": m["close"], "swing_high": m["swing_high"]}
        name = "L2 Pullback Resistance"
    return {"name": name, "passed": passed, "detail": detail}


def _rsi_layer(m, direction):
    if direction == "LONG":
        passed = m["rsi_prev"] < config.RSI_ENTRY_LONG_LO and m["rsi_now"] > m["rsi_prev"]
    else:
        passed = m["rsi_prev"] > config.RSI_ENTRY_SHORT_HI and m["rsi_now"] < m["rsi_prev"]
    return {
        "name": "L3 Momentum RSI",
        "passed": passed,
        "detail": {"rsi": m["rsi_now"], "rsi_prev": m["rsi_prev"]},
    }


def _quality_layer(m):
    passed = m["vol_now"] > m["vol_sma"] * config.VOLUME_MULT and m["adx"] > config.ADX_MIN
    return {
        "name": "L4 Kualitas Pasar",
        "passed": passed,
        "detail": {"volume": m["vol_now"], "volume_sma20": m["vol_sma"], "adx": m["adx"]},
    }


def _daily_trend_layer(coin_trend, btc_trend, direction):
    nan = float("nan")
    if coin_trend is None:
        coin_ok = False
        coin_close, coin_ema50 = nan, nan
    else:
        coin_ok = coin_trend["bull"] if direction == "LONG" else coin_trend["bear"]
        coin_close, coin_ema50 = coin_trend["close"], coin_trend["ema50"]
    if btc_trend is None:
        btc_ok = False
        btc_close, btc_ema50 = nan, nan
    else:
        btc_ok = btc_trend["bull"] if direction == "LONG" else btc_trend["bear"]
        btc_close, btc_ema50 = btc_trend["close"], btc_trend["ema50"]
    return {
        "name": "L5 Tren Harian (koin+BTC)",
        "passed": coin_ok and btc_ok,
        "detail": {
            "coin_close_d1": coin_close,
            "coin_ema50_d1": coin_ema50,
            "btc_close_d1": btc_close,
            "btc_ema50_d1": btc_ema50,
        },
    }


def _layers_for_direction(m, direction, coin_trend, btc_trend):
    return [
        _trend_direction_layer(m, coin_trend, btc_trend, direction),
        _pullback_layer(m, direction),
        _rsi_layer(m, direction),
        _quality_layer(m),
        _daily_trend_layer(coin_trend, btc_trend, direction),
    ]


def evaluate(symbol, base, daily=None, btc_daily=None):
    m = _metrics(base)
    coin_trend = _daily_trend(daily)
    btc_trend = _daily_trend(btc_daily)
    long_layers = _layers_for_direction(m, "LONG", coin_trend, btc_trend)
    short_layers = _layers_for_direction(m, "SHORT", coin_trend, btc_trend)
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