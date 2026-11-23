import sys
import os
import itertools

import ccxt
import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backtest as bt
import backtest_dca as bd
import indicators as ind


CACHE = "/tmp/opencode/bb_cache"
LAYERS = ["L1", "L2", "L3", "L4", "L5"]

BB_OPTIONS = {
    "none": lambda f: (None, None),
    "sentuh": lambda f: (f["close"] <= f["bb_low"], f["close"] >= f["bb_up"]),
    "lebar>=4": lambda f: (f["bb_width"] >= 4.0, f["bb_width"] >= 4.0),
    "sentuh&lebar<5": lambda f: (
        (f["close"] <= f["bb_low"]) & (f["bb_width"] < 5.0),
        (f["close"] >= f["bb_up"]) & (f["bb_width"] < 5.0),
    ),
}


def load_frames():
    btc_df = pd.read_pickle(os.path.join(CACHE, "BTC_USDT_USDT.pkl"))
    btc = bt.daily_trend(btc_df)
    frames = {}
    for symbol in bt.SYMBOLS:
        path = os.path.join(CACHE, symbol.replace("/", "_").replace(":", "_") + ".pkl")
        if not os.path.exists(path):
            continue
        frames[symbol] = bt.attach_trend(pd.read_pickle(path), btc)
    return frames


def layer_flags(f):
    sw10 = ind.swing_low(f, 10)
    sh10 = ind.swing_high(f, 10)
    mid = f["close"].rolling(20).mean()
    std = f["close"].rolling(20).std(ddof=0)
    f = f.copy()
    f["sw10"] = sw10
    f["sh10"] = sh10
    f["bb_mid"] = mid
    f["bb_up"] = mid + 2.0 * std
    f["bb_low"] = mid - 2.0 * std
    f["bb_width"] = (f["bb_up"] - f["bb_low"]) / f["bb_mid"] * 100.0
    flags = {
        0: ((f["close"] > f["ema200"]) & (f["e20"] >= f["e50"] * 0.9985), (f["close"] < f["ema200"]) & (f["e20"] <= f["e50"] * 1.0015)),
        1: (f["close"] <= f["sw10"] * 1.02, f["close"] >= f["sh10"] * 0.98),
        2: ((f["rsi"].shift(1) < 40) & (f["rsi"] > f["rsi"].shift(1)), (f["rsi"].shift(1) > 60) & (f["rsi"] < f["rsi"].shift(1))),
        3: ((f["volume"] > f["vol_sma"]) & (f["adx"] > 20), (f["volume"] > f["vol_sma"]) & (f["adx"] > 20)),
        4: (f["up"].fillna(False) & f["btc_up"].fillna(False), f["dn"].fillna(False) & f["btc_dn"].fillna(False)),
    }
    return f, {k: (pd.Series(v[0], index=f.index).fillna(False).to_numpy(), pd.Series(v[1], index=f.index).fillna(False).to_numpy()) for k, v in flags.items()}


def stats(trades):
    if not trades:
        return None
    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0.01]
    losses = [p for p in pnls if p <= 0.01]
    streak = 0
    worst = 0
    for p in pnls:
        if p <= 0.01:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    return {
        "n": len(pnls),
        "wr": len(wins) / len(pnls) * 100.0,
        "avg": sum(pnls) / len(pnls),
        "total": sum(pnls),
        "streak": worst,
        "avgW": sum(wins) / len(wins) if wins else 0.0,
        "avgL": sum(losses) / len(losses) if losses else 0.0,
    }


def half_wr(trades, mid_ts):
    a = [t for t in trades if t["open_ts"] < mid_ts]
    b = [t for t in trades if t["open_ts"] >= mid_ts]
    sa, sb = stats(a), stats(b)
    return (sa["wr"] if sa else 0.0), (sa["n"] if sa else 0), (sb["wr"] if sb else 0.0), (sb["n"] if sb else 0)


def main():
    ex = ccxt.binance({"enableRateLimit": True, "timeout": 30000, "options": {"defaultType": "swap"}})
    frames = load_frames()
    prepared = {}
    flagmap = {}
    for s, df in frames.items():
        f, flags = layer_flags(bt.build_frame(df, True))
        prepared[s] = f
        flagmap[s] = flags
    if not prepared:
        print("cache data kosong, jalankan vst/backtest_bb.py dulu")
        return
    all_ts = [int(f["ts"].iloc[-1]) for f in prepared.values()]
    first_ts = min(int(f["ts"].iloc[0]) for f in prepared.values())
    last_ts = max(all_ts)
    mid_ts = (first_ts + last_ts) // 2
    print(
        f"data {len(prepared)} simbol {pd.to_datetime(first_ts, unit='ms'):%Y-%m-%d} .. "
        f"{pd.to_datetime(last_ts, unit='ms'):%Y-%m-%d} | split {pd.to_datetime(mid_ts, unit='ms'):%Y-%m-%d}"
    )
    print("kombinasi layer (subset) x filter BB, risk prod SL3/TP6 TP1 1.5% 70%")
    rows = []
    for size in range(1, 6):
        for combo in itertools.combinations(range(5), size):
            for bb_name, bb_fn in BB_OPTIONS.items():
                trades = []
                for s, f in prepared.items():
                    flags = flagmap[s]
                    long_sig = flags[combo[0]][0].copy()
                    short_sig = flags[combo[0]][1].copy()
                    for idx in combo[1:]:
                        long_sig &= flags[idx][0]
                        short_sig &= flags[idx][1]
                    if bb_name != "none":
                        ml, ms = bb_fn(f)
                        long_sig &= pd.Series(ml, index=f.index).fillna(False).to_numpy()
                        short_sig &= pd.Series(ms, index=f.index).fillna(False).to_numpy()
                    trades.extend(bt.simulate(f, long_sig, short_sig, bd.PROD_RISK))
                trades.sort(key=lambda t: t["open_ts"])
                st = stats(trades)
                if not st:
                    continue
                h1_wr, h1_n, h2_wr, h2_n = half_wr(trades, mid_ts)
                rows.append(
                    {
                        "layers": "".join(str(i + 1) for i in combo),
                        "bb": bb_name,
                        **st,
                        "h1_wr": h1_wr, "h1_n": h1_n, "h2_wr": h2_wr, "h2_n": h2_n,
                        "min_half": min(h1_wr, h2_wr) if h1_n >= 8 and h2_n >= 8 else 0.0,
                    }
                )

    def show(title, items):
        print()
        print(title)
        print(f"{'layers':8s} {'bb':15s} {'n':>4s} {'WR':>6s} {'avg':>7s} {'total':>9s} {'avgW':>7s} {'avgL':>7s} {'Lstreak':>7s} {'WRh1':>6s} {'WRh2':>6s}")
        for r in items:
            print(
                f"{r['layers']:8s} {r['bb']:15s} {r['n']:4d} {r['wr']:5.1f}% {r['avg']:+6.2f}% {r['total']:+8.2f}% "
                f"{r['avgW']:+6.2f}% {r['avgL']:+6.2f}% {r['streak']:7d} {r['h1_wr']:5.1f}% {r['h2_wr']:5.1f}%"
            )

    base = next((r for r in rows if r["layers"] == "12345" and r["bb"] == "none"), None)
    if base:
        show("BASELINE (5 layer penuh, tanpa BB)", [base])
    strong = [r for r in rows if r["n"] >= 40]
    show("TOP 15 WINRATE (min 40 trade)", sorted(strong, key=lambda r: (-r["wr"], -r["n"]))[:15])
    show("TOP 10 TOTAL PROFIT (min 40 trade)", sorted(strong, key=lambda r: -r["total"])[:10])
    show(
        "TOP 10 WINRATE STABIL (min 30 trade, min-half>=60%)",
        sorted([r for r in rows if r["n"] >= 30 and r["min_half"] >= 60.0], key=lambda r: (-r["min_half"], -r["wr"]))[:10],
    )


if __name__ == "__main__":
    main()
