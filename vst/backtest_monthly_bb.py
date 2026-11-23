import sys
import os
import datetime as dt

import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backtest as bt
import backtest_dca as bd
from backtest_layers_bb import BB_OPTIONS, layer_flags, load_frames, stats


COMBOS = [
    ("12345+sentuh", (0, 1, 2, 3, 4), "sentuh"),
    ("1345+sentuh", (0, 2, 3, 4), "sentuh"),
    ("1235+sentuh", (0, 1, 2, 4), "sentuh"),
    ("1235+sentuh&lebar<5", (0, 1, 2, 4), "sentuh&lebar<5"),
    ("1245+sentuh&lebar<5", (0, 1, 3, 4), "sentuh&lebar<5"),
    ("12345 (prod, tanpa BB)", (0, 1, 2, 3, 4), "none"),
]


def main():
    frames = load_frames()
    prepared = {}
    flagmap = {}
    for s, df in frames.items():
        f, flags = layer_flags(bt.build_frame(df, True))
        prepared[s] = f
        flagmap[s] = flags
    months = []
    rows = []
    for name, combo, bb_name in COMBOS:
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
        by_month = {}
        for t in trades:
            m = pd.to_datetime(t["close_ts"], unit="ms").strftime("%Y-%m")
            by_month.setdefault(m, []).append(t)
        for m in by_month:
            if m not in months:
                months.append(m)
        rows.append((name, trades, by_month))
    months.sort()
    header = f"{'kombinasi':24s} {'total':>15s} " + " ".join(f"{m:>14s}" for m in months) + "  minWR  avgWR"
    print(header)
    for name, trades, by_month in rows:
        st = stats(trades)
        cells = []
        wrs = []
        for m in months:
            mt = by_month.get(m, [])
            sm = stats(mt)
            if sm:
                cells.append(f"{sm['wr']:5.1f}% ({sm['n']:2d})")
                wrs.append(sm["wr"])
            else:
                cells.append("     - ( 0)")
        min_wr = min(wrs) if wrs else 0.0
        avg_wr = sum(wrs) / len(wrs) if wrs else 0.0
        total_cell = f"{st['wr']:5.1f}% ({st['n']:3d})" if st else "-"
        print(f"{name:24s} {total_cell:>15s} " + " ".join(f"{c:>14s}" for c in cells) + f" {min_wr:5.1f}% {avg_wr:5.1f}%")


if __name__ == "__main__":
    main()
