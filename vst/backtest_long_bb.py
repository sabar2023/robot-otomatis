import sys
import os
import time
import datetime as dt

import ccxt
import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backtest as bt
import backtest_dca as bd
from backtest_layers_bb import layer_flags, BB_OPTIONS


CACHE = "/tmp/opencode/bt20"
SINCE = int(dt.datetime(2017, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)


def fetch_all(ex, symbol):
    path = os.path.join(CACHE, symbol.replace("/", "_").replace(":", "_") + ".pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    rows = {}
    cursor = SINCE
    while True:
        try:
            batch = ex.fetch_ohlcv(symbol, "1h", since=cursor, limit=1000)
        except Exception as exc:
            print(f"  fetch {symbol} error: {str(exc).splitlines()[0][:80]}")
            break
        if not batch:
            break
        for c in batch:
            rows[c[0]] = c
        last = batch[-1][0]
        if last < cursor:
            break
        nxt = last + 3600 * 1000
        cursor = nxt
        if cursor > int(time.time() * 1000):
            break
        time.sleep(0.2)
    df = pd.DataFrame([rows[k] for k in sorted(rows)], columns=["ts", "open", "high", "low", "close", "volume"])
    df.to_pickle(path)
    return df


def simulate_combo(prepared, flagmap, combo, bb_name):
    trades = []
    for s, f in prepared.items():
        flags = flagmap[s]
        long_sig = flags[combo[0]][0].copy()
        short_sig = flags[combo[0]][1].copy()
        for idx in combo[1:]:
            long_sig &= flags[idx][0]
            short_sig &= flags[idx][1]
        if bb_name != "none":
            ml, ms = BB_OPTIONS[bb_name](f)
            long_sig &= pd.Series(ml, index=f.index).fillna(False).to_numpy()
            short_sig &= pd.Series(ms, index=f.index).fillna(False).to_numpy()
        trades.extend(bt.simulate(f, long_sig, short_sig, bd.PROD_RISK))
    trades.sort(key=lambda t: t["close_ts"])
    return trades


def summarize(trades):
    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0.01]
    losses = [p for p in pnls if p <= 0.01]
    return len(pnls), (len(wins) / len(pnls) * 100.0 if pnls else 0.0), sum(pnls), (sum(wins) / len(wins) if wins else 0.0), (sum(losses) / len(losses) if losses else 0.0)


def main():
    os.makedirs(CACHE, exist_ok=True)
    ex = ccxt.binance({"enableRateLimit": True, "timeout": 30000, "options": {"defaultType": "swap"}})
    print("mengambil data H1 sejak 2017 (cache /tmp/opencode/bt20)")
    raw = {}
    for symbol in bt.SYMBOLS:
        df = fetch_all(ex, symbol)
        if len(df) < 500:
            print(f"  {symbol:20s} data tidak cukup ({len(df)})")
            continue
        raw[symbol] = df
        print(f"  {symbol:20s} {len(df):6d} bar {pd.to_datetime(df['ts'].iloc[0], unit='ms'):%Y-%m-%d} .. {pd.to_datetime(df['ts'].iloc[-1], unit='ms'):%Y-%m-%d}")
    btc = bt.daily_trend(raw["BTC/USDT:USDT"])
    prepared = {}
    flagmap = {}
    for s, df in raw.items():
        f, flags = layer_flags(bt.build_frame(bt.attach_trend(df, btc), True))
        prepared[s] = f
        flagmap[s] = flags
    runs = [
        ("12345 + sentuh band", (0, 1, 2, 3, 4), "sentuh"),
        ("12345 tanpa BB (prod)", (0, 1, 2, 3, 4), "none"),
    ]
    for name, combo, bb_name in runs:
        trades = simulate_combo(prepared, flagmap, combo, bb_name)
        n, wr, total, avgw, avgl = summarize(trades)
        print()
        print(f"{name}: trades={n} winrate={wr:.1f}% total={total:+.1f}% avgW={avgw:+.2f}% avgL={avgl:+.2f}%")
        years = {}
        for t in trades:
            years.setdefault(pd.to_datetime(t["close_ts"], unit="ms").year, []).append(t)
        print(f"{'tahun':6s} {'n':>4s} {'WR':>7s} {'total':>10s} {'avg':>8s}")
        for year in sorted(years):
            yn, ywr, ytot, _, _ = summarize(years[year])
            print(f"{year:6d} {yn:4d} {ywr:6.1f}% {ytot:+9.2f}% {ytot / yn:+7.2f}%")


if __name__ == "__main__":
    main()
