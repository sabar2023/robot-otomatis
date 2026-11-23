import sys
import os
import datetime as dt

import ccxt
import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backtest as bt


MONTHS = 6

PROD_RISK = {
    "mode": "pct",
    "sl_pct": 3.0,
    "tp_pct": 6.0,
    "sl_cap": 5.0,
    "max_bars": 300,
    "partial_pct": 1.5,
    "partial_frac": 0.7,
}

DCA_SETS = [
    ("DCA3 TP2 step1.5 stop8", {"levels": 3, "step_pct": 1.5, "tp_pct": 2.0, "stop_pct": 8.0, "max_bars": 336}),
    ("DCA3 TP2 step1.5 noSL", {"levels": 3, "step_pct": 1.5, "tp_pct": 2.0, "stop_pct": 0.0, "max_bars": 336}),
    ("DCA3 TP3 step2 stop8", {"levels": 3, "step_pct": 2.0, "tp_pct": 3.0, "stop_pct": 8.0, "max_bars": 336}),
    ("DCA5 TP2 step1 stop10", {"levels": 5, "step_pct": 1.0, "tp_pct": 2.0, "stop_pct": 10.0, "max_bars": 336}),
]


def simulate_dca(f, long_sig, short_sig, cfg):
    n = len(f)
    ts = f["ts"].to_numpy()
    close = f["close"].to_numpy()
    high = f["high"].to_numpy()
    low = f["low"].to_numpy()
    levels = int(cfg["levels"])
    step = float(cfg["step_pct"])
    tp = float(cfg["tp_pct"])
    stop_pct = float(cfg.get("stop_pct") or 0.0)
    max_bars = int(cfg["max_bars"])
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
        first = float(close[i])
        filled = [first]
        exit_price = None
        exit_bar = None
        for j in range(i + 1, min(i + 1 + max_bars, n)):
            threshold = None
            while len(filled) < levels:
                threshold = first * (1 - step * len(filled) / 100.0) if direction == "LONG" else first * (1 + step * len(filled) / 100.0)
                reached = low[j] <= threshold if direction == "LONG" else high[j] >= threshold
                if not reached:
                    break
                filled.append(threshold)
            avg = sum(filled) / len(filled)
            if stop_pct:
                stop_price = first * (1 - stop_pct / 100.0) if direction == "LONG" else first * (1 + stop_pct / 100.0)
                hit_stop = low[j] <= stop_price if direction == "LONG" else high[j] >= stop_price
                if hit_stop:
                    exit_price = stop_price
                    exit_bar = j
                    break
            tp_price = avg * (1 + tp / 100.0) if direction == "LONG" else avg * (1 - tp / 100.0)
            hit_tp = high[j] >= tp_price if direction == "LONG" else low[j] <= tp_price
            if hit_tp:
                exit_price = tp_price
                exit_bar = j
                break
        if exit_price is None:
            exit_bar = min(i + max_bars, n - 1)
            exit_price = float(close[exit_bar])
        avg = sum(filled) / len(filled)
        move = (exit_price - avg) / avg * 100.0
        if direction == "SHORT":
            move = -move
        trades.append(
            {
                "dir": direction,
                "open_ts": int(ts[i]),
                "close_ts": int(ts[exit_bar]),
                "pnl_pct": move,
                "cap_pct": move * len(filled) / levels,
                "bars": exit_bar - i,
                "levels": len(filled),
            }
        )
        i = exit_bar + 1
    return trades


def report_reserved(name, trades):
    if not trades:
        print(f"{name:34s} trades=0")
        return
    pnls = [t["cap_pct"] for t in trades]
    wins = [p for p in pnls if p > 0.01]
    losses = [p for p in pnls if p <= 0.01]
    total = sum(pnls)
    streak = 0
    worst = 0
    for p in pnls:
        if p <= 0.01:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    print(
        f"{name:34s} trades={len(pnls):3d} winrate={len(wins)/len(pnls)*100:5.1f}% "
        f"avg={total/len(pnls):+.2f}% total={total:+7.2f}% "
        f"avgW={(sum(wins)/len(wins) if wins else 0):+.2f}% avgL={(sum(losses)/len(losses) if losses else 0):+.2f}% "
        f"maxStreakL={worst}"
    )


def levels_summary(trades):
    if not trades:
        return "levels=0"
    counts = {}
    for t in trades:
        counts[t["levels"]] = counts.get(t["levels"], 0) + 1
    parts = ", ".join(f"{k}x:{v}" for k, v in sorted(counts.items()))
    return f"level_fill[{parts}]"


def main():
    ex = ccxt.binance({"enableRateLimit": True, "timeout": 30000, "options": {"defaultType": "swap"}})
    since = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=MONTHS * 30)).timestamp() * 1000)
    btc_trend = bt.daily_trend(bt.fetch_candles(ex, "BTC/USDT:USDT", since_ts=since))
    frames = {}
    for symbol in bt.SYMBOLS:
        try:
            df = bt.fetch_candles(ex, symbol, since_ts=since)
            frames[symbol] = bt.attach_trend(df, btc_trend)
        except Exception as exc:
            print(f"data {symbol} gagal: {str(exc).splitlines()[0][:100]}")
    if not frames:
        print("tidak ada data")
        return
    first_ts = min(int(df["ts"].iloc[0]) for df in frames.values())
    last_ts = max(int(df["ts"].iloc[-1]) for df in frames.values())
    print(
        f"data {len(frames)} simbol {pd.to_datetime(first_ts, unit='ms'):%Y-%m-%d} .. "
        f"{pd.to_datetime(last_ts, unit='ms'):%Y-%m-%d}"
    )
    prepared = {s: bt.build_frame(df, True) for s, df in frames.items()}
    fcfg = dict(bt.BASE_F)
    sig_cache = {s: bt.signals(f, fcfg) for s, f in prepared.items()}
    for s, f in prepared.items():
        long_sig, short_sig = sig_cache[s]
        sig_cache[s] = (
            long_sig & f["up"].fillna(False).to_numpy() & f["btc_up"].fillna(False).to_numpy(),
            short_sig & f["dn"].fillna(False).to_numpy() & f["btc_dn"].fillna(False).to_numpy(),
        )
    prod_trades = []
    for s, f in prepared.items():
        long_sig, short_sig = sig_cache[s]
        prod_trades.extend(bt.simulate(f, long_sig, short_sig, PROD_RISK))
    prod_trades.sort(key=lambda t: t["open_ts"])
    bt.report("PROD SL3/TP6 p1.5 f0.7", prod_trades)
    for name, cfg in DCA_SETS:
        trades = []
        for s, f in prepared.items():
            long_sig, short_sig = sig_cache[s]
            trades.extend(simulate_dca(f, long_sig, short_sig, cfg))
        trades.sort(key=lambda t: t["open_ts"])
        bt.report(name, trades)
        report_reserved("  ^ per modal cadangan", trades)
        print(f"{'':34s} {levels_summary(trades)}")


if __name__ == "__main__":
    main()
