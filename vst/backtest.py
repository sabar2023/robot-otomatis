import sys
import time
import datetime as dt

import ccxt
import pandas as pd


sys.path.insert(0, ".")

import indicators as ind


SYMBOLS = [
    "BTC/USDT:USDT",
    "TRX/USDT:USDT",
    "DOT/USDT:USDT",
    "LTC/USDT:USDT",
    "BCH/USDT:USDT",
    "SUI/USDT:USDT",
    "APT/USDT:USDT",
    "NEAR/USDT:USDT",
    "FIL/USDT:USDT",
    "ATOM/USDT:USDT",
    "INJ/USDT:USDT",
    "ARB/USDT:USDT",
    "OP/USDT:USDT",
    "SEI/USDT:USDT",
    "TIA/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT",
    "ADA/USDT:USDT",
    "BNB/USDT:USDT",
    "LINK/USDT:USDT",
    "AVAX/USDT:USDT",
    "ZEC/USDT:USDT",
]

BARS = 4500


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def fetch_candles(ex, symbol, bars):
    now = int(time.time() * 1000)
    cursor = now - bars * 3600 * 1000
    rows = {}
    while len(rows) < bars:
        batch = ex.fetch_ohlcv(symbol, "1h", since=cursor, limit=1000)
        if not batch:
            break
        for c in batch:
            rows[c[0]] = c
        cursor = batch[-1][0] + 3600 * 1000
        if cursor > now:
            break
        time.sleep(0.3)
    data = [rows[k] for k in sorted(rows)][-bars:]
    return pd.DataFrame(data, columns=["ts", "open", "high", "low", "close", "volume"])


def daily_trend(h1):
    d = h1.set_index(pd.to_datetime(h1["ts"], unit="ms"))
    dd = d.resample("1D").agg({"close": "last"}).dropna()
    dd["e50"] = ind.ema(dd["close"], 50)
    dd["up"] = (dd["close"] > dd["e50"]) & (dd["e50"] > dd["e50"].shift(3))
    dd["dn"] = (dd["close"] < dd["e50"]) & (dd["e50"] < dd["e50"].shift(3))
    out = dd[["up", "dn"]].reset_index()
    out.columns = ["dt", "up", "dn"]
    return out


def attach_trend(h1, btc_trend):
    d = h1.copy()
    d["dt"] = pd.to_datetime(d["ts"], unit="ms")
    own = daily_trend(h1)
    d = pd.merge_asof(d.sort_values("dt"), own.sort_values("dt"), on="dt", direction="backward")
    btc = btc_trend.rename(columns={"up": "btc_up", "dn": "btc_dn"})
    d = pd.merge_asof(d.sort_values("dt"), btc.sort_values("dt"), on="dt", direction="backward")
    return d.sort_values("dt").reset_index(drop=True)


def build_frame(df, use_stack):
    f = df.copy()
    f["ema200"] = ind.ema(f["close"], 200)
    f["swing_low"] = ind.swing_low(f, 20)
    f["swing_high"] = ind.swing_high(f, 20)
    f["rsi"] = ind.rsi(f["close"], 14)
    f["vol_sma"] = ind.sma(f["volume"], 20)
    f["adx"] = ind.adx(f, 14)
    f["atr"] = ind.atr(f, 14)
    if use_stack:
        f["e7"] = ind.ema(f["close"], 7)
        f["e10"] = ind.ema(f["close"], 10)
        f["e20"] = ind.ema(f["close"], 20)
        f["e50"] = ind.ema(f["close"], 50)
        tol = 0.0015
        f["stack_long"] = (
            (f["e7"] >= f["e10"] * (1 - tol))
            & (f["e10"] >= f["e20"] * (1 - tol))
            & (f["e20"] >= f["e50"] * (1 - tol))
            & (f["close"] > f["e50"])
        )
        f["stack_short"] = (
            (f["e7"] <= f["e10"] * (1 + tol))
            & (f["e10"] <= f["e20"] * (1 + tol))
            & (f["e20"] <= f["e50"] * (1 + tol))
            & (f["close"] < f["e50"])
        )
        crossed_up = (f["e7"] > f["e10"]) & (f["e7"].shift(1) <= f["e10"].shift(1))
        crossed_dn = (f["e7"] < f["e10"]) & (f["e7"].shift(1) >= f["e10"].shift(1))
        f["cross_up3"] = crossed_up.rolling(3).max().fillna(0).astype(bool) & (f["e7"] > f["e10"])
        f["cross_up5"] = crossed_up.rolling(5).max().fillna(0).astype(bool) & (f["e7"] > f["e10"])
        f["cross_dn3"] = crossed_dn.rolling(3).max().fillna(0).astype(bool) & (f["e7"] < f["e10"])
        f["cross_dn5"] = crossed_dn.rolling(5).max().fillna(0).astype(bool) & (f["e7"] < f["e10"])
        f["med_up"] = f["e20"] > f["e50"]
        f["med_dn"] = f["e20"] < f["e50"]
        f["short_up"] = f["e10"] > f["e20"]
        f["short_dn"] = f["e10"] < f["e20"]
        f["near_up"] = (f["e7"] - f["e10"]).abs() / f["close"] <= 0.002
        f["near_med"] = (f["e10"] - f["e20"]).abs() / f["close"] <= 0.003
        spread = (f[["e7", "e10", "e20", "e50"]].max(axis=1) / f[["e7", "e10", "e20", "e50"]].min(axis=1) - 1.0) * 100.0
        f["conv_long"] = (spread <= 0.6) & (f["close"] > f["e50"])
        f["conv_short"] = (spread <= 0.6) & (f["close"] < f["e50"])
        up_move = f["high"].diff()
        down_move = -f["low"].diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
        tr = ind.true_range(f)
        atr_s = tr.ewm(alpha=1.0 / 14, adjust=False).mean()
        f["plus_di"] = 100.0 * plus_dm.ewm(alpha=1.0 / 14, adjust=False).mean() / atr_s
        f["minus_di"] = 100.0 * minus_dm.ewm(alpha=1.0 / 14, adjust=False).mean() / atr_s
        f["e50_slope_up"] = f["e50"] > f["e50"].shift(3)
        f["e50_slope_dn"] = f["e50"] < f["e50"].shift(3)
        cross50_up = (f["e7"] > f["e50"]) & (f["e7"].shift(1) <= f["e50"].shift(1))
        cross50_dn = (f["e7"] < f["e50"]) & (f["e7"].shift(1) >= f["e50"].shift(1))
        f["x50_up3"] = cross50_up.rolling(3).max().fillna(0).astype(bool) & (f["e7"] > f["e50"])
        f["x50_up5"] = cross50_up.rolling(5).max().fillna(0).astype(bool) & (f["e7"] > f["e50"])
        f["x50_dn3"] = cross50_dn.rolling(3).max().fillna(0).astype(bool) & (f["e7"] < f["e50"])
        f["x50_dn5"] = cross50_dn.rolling(5).max().fillna(0).astype(bool) & (f["e7"] < f["e50"])
    return f


def signals(f, cfg):
    tol = cfg.get("support_tol", 0.002)
    lookback = cfg.get("lookback", 20)
    if lookback == 20:
        swing_low_s = f["swing_low"]
        swing_high_s = f["swing_high"]
    else:
        swing_low_s = ind.swing_low(f, lookback)
        swing_high_s = ind.swing_high(f, lookback)
    if cfg.get("rsi_mode") == "rising":
        rsi_lo = cfg.get("rsi_lo", 35)
        long_rsi = (f["rsi"].shift(1) < rsi_lo) & (f["rsi"] > f["rsi"].shift(1))
        rsi_hi = cfg.get("rsi_hi", 65)
        short_rsi = (f["rsi"].shift(1) > rsi_hi) & (f["rsi"] < f["rsi"].shift(1))
    else:
        long_rsi = (f["rsi"].shift(1) < 30) & (f["rsi"] >= 30)
        short_rsi = (f["rsi"].shift(1) > 70) & (f["rsi"] <= 70)
    long_ok = (
        (f["close"] > f["ema200"])
        & (f["close"] <= swing_low_s * (1.0 + tol))
        & long_rsi
        & (f["volume"] > f["vol_sma"] * cfg.get("vol_mult", 1.0))
        & (f["adx"] > cfg.get("adx_min", 20))
    )
    short_ok = (
        (f["close"] < f["ema200"])
        & (f["close"] >= swing_high_s * (1.0 - tol))
        & short_rsi
        & (f["volume"] > f["vol_sma"] * cfg.get("vol_mult", 1.0))
        & (f["adx"] > cfg.get("adx_min", 20))
    )
    if cfg.get("use_di"):
        long_ok = long_ok & (f["plus_di"] > f["minus_di"])
        short_ok = short_ok & (f["minus_di"] > f["plus_di"])
    if cfg.get("use_slope"):
        long_ok = long_ok & f["e50_slope_up"]
        short_ok = short_ok & f["e50_slope_dn"]
    if cfg.get("x50_window"):
        w = cfg["x50_window"]
        long_ok = long_ok & (f["x50_up3"] if w == 3 else f["x50_up5"])
        short_ok = short_ok & (f["x50_dn3"] if w == 3 else f["x50_dn5"])
    mode = cfg.get("stack_mode", "strict")
    if mode == "strict":
        long_ok = long_ok & f["stack_long"]
        short_ok = short_ok & f["stack_short"]
    elif mode == "converge":
        long_ok = long_ok & f["conv_long"]
        short_ok = short_ok & f["conv_short"]
    elif mode == "either":
        long_ok = long_ok & (f["stack_long"] | f["conv_long"])
        short_ok = short_ok & (f["stack_short"] | f["conv_short"])
    elif mode == "med":
        long_ok = long_ok & f["med_up"]
        short_ok = short_ok & f["med_dn"]
    elif mode == "med_short":
        long_ok = long_ok & f["med_up"] & f["short_up"]
        short_ok = short_ok & f["med_dn"] & f["short_dn"]
    elif mode == "cross3":
        long_ok = long_ok & f["cross_up3"] & f["med_up"]
        short_ok = short_ok & f["cross_dn3"] & f["med_dn"]
    elif mode == "cross5":
        long_ok = long_ok & f["cross_up5"] & f["med_up"]
        short_ok = short_ok & f["cross_dn5"] & f["med_dn"]
    elif mode == "meet":
        long_ok = long_ok & f["near_up"] & f["near_med"] & (f["close"] > f["e50"])
        short_ok = short_ok & f["near_up"] & f["near_med"] & (f["close"] < f["e50"])
    elif mode == "fast_above_slow":
        long_ok = long_ok & (f["e7"] > f["e50"])
        short_ok = short_ok & (f["e7"] < f["e50"])
    elif mode == "fast_med":
        long_ok = long_ok & (f["e7"] > f["e50"]) & f["med_up"]
        short_ok = short_ok & (f["e7"] < f["e50"]) & f["med_dn"]
    elif mode == "e7e20e50":
        long_ok = long_ok & (f["e7"] > f["e20"]) & f["med_up"]
        short_ok = short_ok & (f["e7"] < f["e20"]) & f["med_dn"]
    elif mode == "e7e10e50":
        long_ok = long_ok & f["short_up"] & (f["e10"] > f["e50"])
        short_ok = short_ok & f["short_dn"] & (f["e10"] < f["e50"])
    return long_ok.fillna(False).to_numpy(), short_ok.fillna(False).to_numpy()


def rnd(pct):
    return int(round(pct * 100)) / 100


def simulate(f, long_sig, short_sig, cfg):
    n = len(f)
    ts = f["ts"].to_numpy()
    close = f["close"].to_numpy()
    high = f["high"].to_numpy()
    low = f["low"].to_numpy()
    atr = f["atr"].to_numpy()
    trades = []
    i = 260
    while i < n - 1:
        direction = None
        if long_sig[i]:
            direction = "LONG"
        elif short_sig[i]:
            direction = "SHORT"
        if direction is None:
            i += 1
            continue
        price = float(close[i])
        if cfg["mode"] == "atr":
            sl_pct = clamp(atr[i] * cfg["sl_mult"] / price * 100.0, 1.0, cfg["sl_cap"])
            tp_pct = clamp(atr[i] * cfg["tp_mult"] / price * 100.0, 3.0, 12.0)
        else:
            sl_pct = cfg["sl_pct"]
            tp_pct = cfg["tp_pct"]
        sl_pct = min(sl_pct, cfg["sl_cap"])
        if direction == "LONG":
            sl = price * (1 - sl_pct / 100.0)
            tp = price * (1 + tp_pct / 100.0)
            tp1 = price * (1 + cfg.get("partial_pct", 0) / 100.0)
            be = price * (1 + cfg.get("be_pct", 0) / 100.0)
        else:
            sl = price * (1 + sl_pct / 100.0)
            tp = price * (1 - tp_pct / 100.0)
            tp1 = price * (1 - cfg.get("partial_pct", 0) / 100.0)
            be = price * (1 - cfg.get("be_pct", 0) / 100.0)
        partial_done = False
        partial_frac = cfg.get("partial_frac", 0.5)
        booked = 0.0
        exit_price = None
        exit_bar = None
        for j in range(i + 1, min(i + 1 + cfg["max_bars"], n)):
            if direction == "LONG":
                hit_sl = low[j] <= sl
                hit_tp = high[j] >= tp
            else:
                hit_sl = high[j] >= sl
                hit_tp = low[j] <= tp
            if hit_sl:
                exit_price = sl
                exit_bar = j
                break
            if cfg.get("partial_pct") and not partial_done:
                reached = high[j] >= tp1 if direction == "LONG" else low[j] <= tp1
                if reached:
                    booked = partial_frac * abs(tp1 - price) / price * 100.0
                    partial_done = True
                    sl = price
                    if direction == "LONG":
                        hit_sl_now = low[j] <= sl
                    else:
                        hit_sl_now = high[j] >= sl
                    if hit_sl_now:
                        exit_price = sl
                        exit_bar = j
                        break
            if hit_tp:
                exit_price = tp
                exit_bar = j
                break
            if cfg.get("be_pct"):
                reached = high[j] >= be if direction == "LONG" else low[j] <= be
                if reached:
                    sl = price
        if exit_price is None:
            exit_bar = min(i + cfg["max_bars"], n - 1)
            exit_price = float(close[exit_bar])
        move = (exit_price - price) / price * 100.0
        if direction == "SHORT":
            move = -move
        pnl = booked + move * ((1.0 - partial_frac) if partial_done else 1.0)
        trades.append(
            {
                "dir": direction,
                "open_ts": int(ts[i]),
                "close_ts": int(ts[exit_bar]),
                "pnl_pct": pnl,
                "bars": exit_bar - i,
            }
        )
        i = exit_bar + 1
    return trades


def report(name, trades):
    if not trades:
        print(f"{name:34s} trades=0")
        return
    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0.01]
    losses = [p for p in pnls if p <= 0.01]
    total = sum(pnls)
    avg = total / len(pnls)
    streak = 0
    worst = 0
    for p in pnls:
        if p <= 0.01:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    print(
        f"{name:34s} trades={len(pnls):3d} winrate={len(wins)/len(pnls)*100:5.1f}% "
        f"avg={avg:+.2f}% total={total:+7.2f}% avgW={avg_win:+.2f}% avgL={avg_loss:+.2f}% "
        f"maxStreakL={worst} avgBars={sum(t['bars'] for t in trades)/len(trades):.1f}"
    )


BASE_F = {
    "support_tol": 0.015,
    "lookback": 10,
    "rsi_mode": "rising",
    "rsi_lo": 40,
    "adx_min": 20,
    "stack_mode": "fast_med",
    "vol_mult": 1.2,
    "trend_align": True,
}

FILTER_SETS = [
    ("prod", dict(BASE_F)),
    ("prod-adx25", dict(BASE_F, adx_min=25)),
]

OLD_FILTER_SETS = [
    ("A-base", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "none"}),
    ("B-med", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "med"}),
    ("C-med-short", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "med_short"}),
    ("D-cross3", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "cross3"}),
    ("E-cross5", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "cross5"}),
    ("F-meet", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "meet"}),
    ("G-fast-slow", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "fast_above_slow"}),
    ("H-fast-med", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "fast_med"}),
    ("I-e7e20e50", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "e7e20e50"}),
    ("J-e7e10e50", {"support_tol": 0.005, "lookback": 10, "rsi_mode": "rising", "rsi_lo": 40, "adx_min": 20, "stack_mode": "e7e10e50"}),
]

RISK_SETS = [
    ("prod SL2/TP6 p1.2 f0.7", {"mode": "pct", "sl_pct": 2.0, "tp_pct": 6.0, "sl_cap": 5.0, "max_bars": 168, "partial_pct": 1.2, "partial_frac": 0.7}),
    ("prod SL2/TP5 p1.2 f0.7", {"mode": "pct", "sl_pct": 2.0, "tp_pct": 5.0, "sl_cap": 5.0, "max_bars": 168, "partial_pct": 1.2, "partial_frac": 0.7}),
    ("prod SL2.5/TP6 p1.2 f0.7", {"mode": "pct", "sl_pct": 2.5, "tp_pct": 6.0, "sl_cap": 5.0, "max_bars": 168, "partial_pct": 1.2, "partial_frac": 0.7}),
    ("SL2/TP6 full", {"mode": "pct", "sl_pct": 2.0, "tp_pct": 6.0, "sl_cap": 5.0, "max_bars": 168}),
]


def main():
    ex = ccxt.bingx({"enableRateLimit": True, "timeout": 20000, "options": {"defaultType": "swap"}})
    frames = {}
    btc_trend = daily_trend(fetch_candles(ex, "BTC/USDT:USDT", BARS))
    for symbol in SYMBOLS:
        try:
            df = fetch_candles(ex, symbol, BARS)
            frames[symbol] = attach_trend(df, btc_trend)
        except Exception as exc:
            print(f"data {symbol} gagal: {str(exc).splitlines()[0][:100]}")
    print(f"data siap: {len(frames)} simbol x ~{BARS} candle H1")
    prepared = {s: build_frame(df, True) for s, df in frames.items()}
    for fname, fcfg in FILTER_SETS:
        sig_cache = {s: signals(f, fcfg) for s, f in prepared.items()}
        for rname, rcfg in RISK_SETS:
            all_trades = []
            for symbol, f in prepared.items():
                long_sig, short_sig = sig_cache[symbol]
                if fcfg.get("trend_align"):
                    long_sig = long_sig & f["up"].fillna(False).to_numpy() & f["btc_up"].fillna(False).to_numpy()
                    short_sig = short_sig & f["dn"].fillna(False).to_numpy() & f["btc_dn"].fillna(False).to_numpy()
                all_trades.extend(simulate(f, long_sig, short_sig, rcfg))
            all_trades.sort(key=lambda t: t["open_ts"])
            report(f"{fname} | {rname}", all_trades)


if __name__ == "__main__":
    main()
