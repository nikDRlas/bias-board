#!/usr/bin/env python3
"""Seasonal window size relative to the asset's own volatility: do 'bigger' windows pay better?

  size = |window's average move over its 15 past years| / (daily volatility over the past year x sqrt(window length))
i.e. the usual move in units of a normal random swing over the same number of trading days, comparable across assets.
Walk-forward 2019-26: every Saturday the board's driver window (only data known that day). One observation per market,
window and year (the first Saturday it led). Outcome from the next close (or window start) to the window end, in the
window's direction, in % and in volatility units. Buckets by size; also the share of windows a cut would keep.
Output: data/research/window_size.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402

CUTS = (0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8)


def st(g):
    if len(g) < 5:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "z": round(float(g.z.mean()), 3), "t": round(float(g.z.mean() / g.z.std(ddof=1) * np.sqrt(len(g))), 2)}


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p = C.load_px(k)
        lc = np.log(p.to_numpy(float))
        dl = np.diff(lc, prepend=lc[0])
        cal = SS.Calendar(p)
        seen = set()
        for t in pd.date_range("2019-01-05", C.TODAY - pd.Timedelta(days=1), freq="W-SAT"):
            ws, status = cal.windows(t)
            if status != "driver":
                continue
            d = ws[0]
            key = (str(d["start"])[:10], d["side"])
            if key in seen:
                continue
            seen.add(key)
            ti = p.index.searchsorted(t)
            sig = dl[max(1, ti - 252):ti].std()
            size = abs(d["avg"]) / 100 / (sig * np.sqrt(d["len"]))
            a = p.index.searchsorted(max(t, pd.Timestamp(d["start"])))
            b = p.index.searchsorted(pd.Timestamp(d["end"]))
            if b >= len(p) or b <= a or p.index[b] > C.TODAY:
                continue
            sg = 1 if d["side"] == "BUY" else -1
            r = sg * (lc[b] - lc[a])
            rows.append({"m": k, "sector": C.M[k][3], "d": str(t.date()), "size": float(size), "len": int(d["len"]),
                         "wins": int(d["wins"]), "r": 100 * (np.exp(r) - 1), "z": float(r / (sig * np.sqrt(b - a)))})
        print(k, flush=True)
    df = pd.DataFrame(rows)
    df["q"] = pd.qcut(df["size"], 5, labels=["Q1 smallest", "Q2", "Q3", "Q4", "Q5 biggest"])
    res = {"quintiles": {}, "cuts": {}, "size_quantiles": [round(float(x), 2) for x in df["size"].quantile([.2, .4, .6, .8])]}
    for q, g in df.groupby("q", observed=True):
        res["quintiles"][str(q)] = {"range": [round(float(g["size"].min()), 2), round(float(g["size"].max()), 2)],
                                    "all": st(g), "2019-22": st(g[g.d < "2023"]), "2023-26": st(g[g.d >= "2023"])}
    for c in CUTS:
        g = df[df["size"] >= c]
        res["cuts"][str(c)] = {"keep": round(100 * len(g) / len(df), 1), "all": st(g), "2019-22": st(g[g.d < "2023"]),
                               "2023-26": st(g[g.d >= "2023"])}
    res["by_sector_median_size"] = {s: round(float(g["size"].median()), 2) for s, g in df.groupby("sector")}
    json.dump({**res, "rows": rows}, open(os.path.join(HERE, "..", "data", "research", "window_size.json"), "w"), indent=1)
    f = lambda o: f"{o['win']:4.1f}% {o['avg']:+.2f}% z {o['z']:+.3f} t {o['t']:+.2f} n{o['n']}" if o else "-"
    print("size quintile edges", res["size_quantiles"], "| median by sector", res["by_sector_median_size"])
    for q, v in res["quintiles"].items():
        print(f"{q:12s} {v['range']}  all {f(v['all'])} | 19-22 {f(v['2019-22'])} | 23-26 {f(v['2023-26'])}")
    for c, v in res["cuts"].items():
        print(f"size >= {c:4s} keep {v['keep']:5.1f}%  all {f(v['all'])} | 19-22 {f(v['2019-22'])} | 23-26 {f(v['2023-26'])}")
