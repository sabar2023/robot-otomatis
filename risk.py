import config


def compute_levels(entry_price, atr_value):
    entry_low = float(entry_price)
    entry_high = entry_low * (1.0 + config.ENTRY_SPREAD_PCT / 100.0)
    stop_loss = entry_low - config.ATR_SL_MULT * atr_value
    take_profit = entry_low + config.ATR_TP_MULT * atr_value
    rr = (take_profit - entry_low) / (entry_low - stop_loss)
    return {
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rr": rr,
        "atr": atr_value,
    }
