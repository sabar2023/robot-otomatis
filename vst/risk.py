import config


def compute_levels(direction, entry_price, atr_value):
    price = float(entry_price)
    atr = float(atr_value)
    if direction == "LONG":
        stop_loss = price - config.ATR_SL_MULT * atr
        take_profit = price + config.ATR_TP_MULT * atr
    else:
        stop_loss = price + config.ATR_SL_MULT * atr
        take_profit = price - config.ATR_TP_MULT * atr
    return {
        "direction": direction,
        "entry": price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rr": config.ATR_TP_MULT / config.ATR_SL_MULT,
        "atr": atr,
        "size_usdt": config.POSITION_SIZE_USDT,
        "leverage": config.LEVERAGE,
    }
