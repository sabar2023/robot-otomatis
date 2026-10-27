import config


def _clamp(value, lo, hi):
    return max(lo, min(hi, float(value)))


def compute_levels(direction, entry_price, atr_value, sl_pct=None, tp_pct=None, leverage=None, margin_pct=None):
    price = float(entry_price)
    atr = float(atr_value)
    if sl_pct is None:
        sl_pct = _clamp(atr * config.ATR_SL_MULT / price * 100.0, config.SL_PCT_MIN, config.SL_PCT_MAX)
    else:
        sl_pct = _clamp(float(sl_pct), config.SL_PCT_USER_MIN, config.SL_PCT_USER_MAX)
    if tp_pct is None:
        tp_pct = _clamp(atr * config.ATR_TP_MULT / price * 100.0, config.TP_PCT_MIN, config.TP_PCT_MAX)
    else:
        tp_pct = _clamp(float(tp_pct), config.TP_PCT_USER_MIN, config.TP_PCT_USER_MAX)
    if leverage:
        lev = int(leverage)
    else:
        lev = config.LEVERAGE_DEFAULT
    lev = max(config.LEVERAGE_MIN, min(config.LEVERAGE_MAX, lev))
    mg = float(margin_pct) if margin_pct else config.MARGIN_PCT
    mg = max(1.0, min(100.0, mg))
    if direction == "LONG":
        stop_loss = price * (1.0 - sl_pct / 100.0)
        take_profit = price * (1.0 + tp_pct / 100.0)
    else:
        stop_loss = price * (1.0 + sl_pct / 100.0)
        take_profit = price * (1.0 - tp_pct / 100.0)
    sl_distance_pct = abs(stop_loss - price) / price * 100.0
    tp_distance_pct = abs(take_profit - price) / price * 100.0
    return {
        "direction": direction,
        "entry": price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rr": tp_distance_pct / sl_distance_pct if sl_distance_pct else 0.0,
        "atr": atr,
        "sl_distance_pct": sl_distance_pct,
        "tp_distance_pct": tp_distance_pct,
        "margin_pct": mg,
        "leverage": lev,
    }
