#!/usr/bin/env python3
"""Do a seasonal window's own numbers predict how it does afterwards?

Walk-forward, every Saturday since 2019, the board's driver window (15 prior years, >= 12 of 15), one trade per
market at a time, from max(Saturday, window start) to the window end. At entry the window's own record is stored:
wins of 15, average move in the trade's direction (%), that move divided by the market's normal volatility over the
window's length, and hits in the last 4 years. Results split into groups, both halves.
Output: data/research/window_quality.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
from conflict_test import ret                          # noqa: E402

if __name__ == "__main__":
    end = C.TODAY - pd.Timedelta(days=1)
    rows = []
    for k in C.M:
        p = C.load_px(k)
        lp = np.log(p)
        cal = SS.Calendar(p)
        busy = pd.Timestamp("1900-01-01")
        for t in pd.date_range("2019-01-05", end, freq="W-SAT"):
            if t <= busy:
                continue
            d = cal.driver(t)
            if d in (None, "cancel"):
                continue
            x = ret(p, max(t, d["start"]), d["end"], d["side"])
            if not x or pd.Timestamp(x["exit"]) > end:
                continue
            i = p.index.searchsorted(t)
            vol = lp.diff().iloc[max(1, i - 252):i].std() * np.sqrt(d["len"])
            dir_avg = d["avg"] if d["side"] == "BUY" else -d["avg"]
            rows.append({"m": k, "t": str(t.date()), "wins": d["wins"], "avg": dir_avg, "avg_vol": dir_avg / 100 / vol,
                         "rec": d["rec"], **x})
            busy = pd.Timestamp(x["exit"])
        print(k, flush=True)
    df = pd.DataFrame(rows)

    def st(g):
        z = g.z[np.isfinite(g.z)]
        return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
                "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)} if len(g) > 2 else None
    res = {}
    groups = {"wins": lambda s: s.map(lambda w: "12" if w == 12 else "13" if w == 13 else "14-15"),
              "avg": lambda s: pd.qcut(s, 3, labels=["small move", "medium move", "big move"]).astype(str),
              "avg_vol": lambda s: pd.qcut(s, 3, labels=["small vs vol", "medium vs vol", "big vs vol"]).astype(str),
              "rec": lambda s: s.map(lambda r: "last4 0-2" if r <= 2 else "last4 3" if r == 3 else "last4 4")}
    for col, f in groups.items():
        df["g"] = f(df[col])
        res[col] = {per: {g: st(gg) for g, gg in (df if per == "all" else df[(df.t < "2022") == (per == "2019-21")]).groupby("g")}
                    for per in ("all", "2019-21", "2022-26")}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "window_quality.json"), "w"), indent=1)
    for col, v in res.items():
        print(col)
        for per, gs in v.items():
            print("  ", per, {g: (o["n"], o["win"], o["avg"], o["t"]) for g, o in gs.items() if o})
