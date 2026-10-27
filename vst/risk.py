import config


def compute_levels(direction, entry_price, atr_value):
    price = float(entry_price)
    atr = float(atr_value)
    sl_pct = config.SL_PCT / 100.0
    tp_pct = config.TP_PCT / 100.0
    if direction == "LONG":
        stop_loss = price * (1.0 - sl_pct)
        take_profit = price * (1.0 + tp_pct)
    else:
        stop_loss = price * (1.0 + sl_pct)
        take_profit = price * (1.0 - tp_pct)
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
        "size_usdt": config.POSITION_SIZE_USDT,
        "leverage": config.LEVERAGE,
    }