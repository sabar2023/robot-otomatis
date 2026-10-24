import math

import config


def compute_levels(direction, entry_price, atr_value):
    price = float(entry_price)
    spread = config.ENTRY_SPREAD_PCT / 100.0
    atr = float(atr_value)
    if direction == "LONG":
        entry_low = price
        entry_high = price * (1.0 + spread)
        stop_loss = price - config.ATR_SL_MULT * atr
        take_profit = price + config.ATR_TP_MULT * atr
    else:
        entry_low = price * (1.0 - spread)
        entry_high = price
        stop_loss = price + config.ATR_SL_MULT * atr
        take_profit = price - config.ATR_TP_MULT * atr

    sl_distance_pct = abs(stop_loss - price) / price * 100.0
    if sl_distance_pct > 0:
        raw_leverage = config.RISK_PER_TRADE_PCT / sl_distance_pct
        leverage = int(min(config.MAX_LEVERAGE, max(config.MIN_LEVERAGE, math.floor(raw_leverage))))
    else:
        leverage = config.MIN_LEVERAGE

    return {
        "direction": direction,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rr": 2.0,
        "atr": atr,
        "sl_distance_pct": sl_distance_pct,
        "leverage": leverage,
    }
