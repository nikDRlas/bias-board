#!/usr/bin/env python3
"""Macro score at an extreme: does it change the drawdown (MAE) of the board's verdicts?

Board verdicts (research/verdict_test.py, current rules), 2019 to the end of the EdgeFinder replica (16 Sep 2026).
Extreme = the market's macro_score (and ef_score) at or above the 80th / at or below the 20th percentile of its own
daily values over the previous 3 years (like COT). Each verdict: macro extreme agreeing with it, extreme against it,
or not extreme. Along each trade (entry to exit, daily closes, in the verdict's direction): MAE = worst point, MFE =
best point, end. Output: data/research/macro_extreme_mae.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
from macro_filter_test import MAP, SRC                 # noqa: E402


def st(g):
    if len(g) < 8:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "end": round(float(g.r.mean()), 2),
            "mae": round(float(g.mae.mean()), 2), "mae_median": round(float(g.mae.median()), 2),
            "mfe": round(float(g.mfe.mean()), 2), "mae_z": round(float(g.mae_z.mean()), 2),
            "2019-22 mae_z": round(float(g[g.t < "2023"].mae_z.mean()), 2) if (g.t < "2023").sum() else None,
            "2023-26 mae_z": round(float(g[g.t >= "2023"].mae_z.mean()), 2) if (g.t >= "2023").sum() else None}


if __name__ == "__main__":
    ef = pd.read_csv(SRC, usecols=["date", "symbol", "macro_score", "ef_score"], parse_dates=["date"])
    T = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
    T = T[T.m.isin(MAP) & (pd.to_datetime(T.t) <= ef.date.max())].copy()
    rows = []
    for _, r in T.iterrows():
        p = C.load_px(r.m)
        a, b = p.index.searchsorted(pd.Timestamp(r.entry)), p.index.searchsorted(pd.Timestamp(r.exit))
        sg = 1 if r.v == "BULLISH" else -1
        seg = 100 * sg * (p.iloc[a:b + 1].to_numpy() / p.iloc[a] - 1)
        vol = 100 * np.diff(np.log(p.iloc[max(0, a - 253):a].to_numpy())).std() * np.sqrt(max(1, b - a))
        o = {**r.to_dict(), "mae": float(seg.min()), "mfe": float(seg.max()), "mae_z": float(seg.min() / vol)}
        s = ef[ef.symbol == MAP[r.m]].set_index("date")
        t = pd.Timestamp(r.t)
        for col in ("macro_score", "ef_score"):
            hist = s[col][(s.index <= t) & (s.index > t - pd.DateOffset(years=3))]
            if len(hist) < 250:
                o["x_" + col] = "no data"
                continue
            now = hist.iloc[-1]
            pc = 100 * float((hist.iloc[:-1] < now).mean())
            side = 1 if pc >= 80 else -1 if pc <= 20 else 0
            o["x_" + col] = "not extreme" if side == 0 else ("extreme, agrees" if side == sg else "extreme, against")
        rows.append(o)
    df = pd.DataFrame(rows)
    res = {"all": st(df)}
    for col in ("macro_score", "ef_score"):
        res[col] = {k: st(g) for k, g in df.groupby("x_" + col)}
        res[col + " by sector"] = {f"{s} · {k}": st(g) for (s, k), g in df.groupby(["sector", "x_" + col])}
    df.to_csv(os.path.join(HERE, "..", "data", "research", "macro_extreme_mae_trades.csv"), index=False)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "macro_extreme_mae.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:3d} won {o['win']:4.1f}% end {o['end']:+.2f}% | MAE avg {o['mae']:+.2f}% median {o['mae_median']:+.2f}% (vol-units {o['mae_z']:+.2f}; 19-22 {o['2019-22 mae_z']:+.2f} / 23-26 {o['2023-26 mae_z']:+.2f}) | MFE {o['mfe']:+.2f}%" if o else "-"
    print("all", f(res["all"]))
    for col in ("macro_score", "ef_score"):
        print(f"\n{col}")
        for k, o in res[col].items():
            print(f"   {k:17s} {f(o)}")
        for k, o in res[col + " by sector"].items():
            if o:
                print(f"      {k:34s} {f(o)}")
