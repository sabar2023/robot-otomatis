import sys
import os
import datetime as dt

import ccxt
import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backtest as bt
import backtest_dca as bd


CACHE = "/tmp/opencode/bb_cache"


def add_bollinger(f, period=20, mult=2.0):
    mid = f["close"].rolling(period).mean()
    std = f["close"].rolling(period).std(ddof=0)
    f = f.copy()
    f["bb_mid"] = mid
    f["bb_up"] = mid + mult * std
    f["bb_low"] = mid - mult * std
    f["bb_width"] = (f["bb_up"] - f["bb_low"]) / f["bb_mid"] * 100.0
    f["bb_width_prev5"] = f["bb_width"].shift(5)
    return f


def base_signals(f):
    long_sig, short_sig = bt.signals(f, dict(bt.BASE_F))
    long_sig = long_sig & f["up"].fillna(False).to_numpy() & f["btc_up"].fillna(False).to_numpy()
    short_sig = short_sig & f["dn"].fillna(False).to_numpy() & f["btc_dn"].fillna(False).to_numpy()
    return long_sig, short_sig


def with_mask(f, long_sig, short_sig, mask_long, mask_short):
    ml = pd.Series(mask_long, index=f.index).fillna(False).to_numpy()
    ms = pd.Series(mask_short, index=f.index).fillna(False).to_numpy()
    return long_sig & ml, short_sig & ms


def load_frames(ex):
    os.makedirs(CACHE, exist_ok=True)
    since = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=bd.MONTHS * 30)).timestamp() * 1000)
    btc = bt.daily_trend(bt.fetch_candles(ex, "BTC/USDT:USDT", since_ts=since))
    frames = {}
    for symbol in bt.SYMBOLS:
        path = os.path.join(CACHE, symbol.replace("/", "_").replace(":", "_") + ".pkl")
        if os.path.exists(path):
            df = pd.read_pickle(path)
        else:
            try:
                df = bt.fetch_candles(ex, symbol, since_ts=since)
            except Exception as exc:
                print(f"data {symbol} gagal: {str(exc).splitlines()[0][:100]}")
                continue
            df.to_pickle(path)
        frames[symbol] = bt.attach_trend(df, btc)
    return frames


VARIANTS = {
    "A prod": lambda f: (None, None),
    "B + sentuh band": lambda f: (f["close"] <= f["bb_low"], f["close"] >= f["bb_up"]),
    "C + close < mid (L)": lambda f: (f["close"] < f["bb_mid"], f["close"] > f["bb_mid"]),
    "D + close > mid (L)": lambda f: (f["close"] > f["bb_mid"], f["close"] < f["bb_mid"]),
    "E + lebar < 4%": lambda f: (f["bb_width"] < 4.0, f["bb_width"] < 4.0),
    "F + lebar >= 4%": lambda f: (f["bb_width"] >= 4.0, f["bb_width"] >= 4.0),
    "G + lebar melebar": lambda f: (f["bb_width"] > f["bb_width_prev5"], f["bb_width"] > f["bb_width_prev5"]),
    "H + sentuh & lebar<5%": lambda f: ((f["close"] <= f["bb_low"]) & (f["bb_width"] < 5.0), (f["close"] >= f["bb_up"]) & (f["bb_width"] < 5.0)),
    "I + band dalam (low>mid*0.97)": lambda f: (f["bb_low"] > f["bb_mid"] * 0.97, f["bb_up"] < f["bb_mid"] * 1.03),
}


def main():
    ex = ccxt.binance({"enableRateLimit": True, "timeout": 30000, "options": {"defaultType": "swap"}})
    frames = load_frames(ex)
    prepared = {s: add_bollinger(bt.build_frame(df, True)) for s, df in frames.items()}
    sig = {s: base_signals(f) for s, f in prepared.items()}
    first_ts = min(int(f["ts"].iloc[0]) for f in prepared.values())
    last_ts = max(int(f["ts"].iloc[-1]) for f in prepared.values())
    print(
        f"data {len(prepared)} simbol {pd.to_datetime(first_ts, unit='ms'):%Y-%m-%d} .. "
        f"{pd.to_datetime(last_ts, unit='ms'):%Y-%m-%d} | BB20 2sd"
    )
    for name, masker in VARIANTS.items():
        trades = []
        for s, f in prepared.items():
            long_sig, short_sig = sig[s]
            ml, ms = masker(f)
            if ml is not None:
                long_sig, short_sig = with_mask(f, long_sig, short_sig, ml, ms)
            trades.extend(bt.simulate(f, long_sig, short_sig, bd.PROD_RISK))
        trades.sort(key=lambda t: t["open_ts"])
        bt.report(name, trades)


if __name__ == "__main__":
    main()
