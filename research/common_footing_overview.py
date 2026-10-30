"""RESULT 2026-10-30 (10 markets, best stop by ratio): daily canon zone stop ratio 1.58 (19-22 1.15 / 23-26 2.42),
+1.09 R/verdict; Big-Brother 4h fixed 0.75 wk 1.51 (0.80 / 2.27), +0.17; weekly canon 0.99; canon 4h >=0.25 wk 0.74,
+1.47 R/verdict (most R); Nested weekly->4h 0.60 (19-22 0.13); V4 4h 0.55; verdict entry 0.54; three-tier B 4h 0.50;
the daily/weekly V4, three-tier, prev-day/prev-week and Nested Daily->4h at or below 0.41.
All entries on ONE footing (2026-10-30): the 10 markets with 4h data (6E 6B 6J 6S 6A 6C GC SI ES NQ), so the R/DD
ratios compare across timeframes. Read from the per-trade outputs of daily_stop_grid_test.py, weekly_stop_grid_test.py
and nested_bigbrother_test.py. Per entry: every stop variant, then the best by ratio (R per year / max drawdown after
0.02 weekly-ATR cost per trade, 1R per trade). Also the same ranking on 2019-22 and 2023-26 separately."""
import numpy as np, pandas as pd
BB = "/Users/Niklas/bias-board/data/research"
TEN = ["6E", "6B", "6J", "6S", "6A", "6C", "GC", "SI", "ES", "NQ"]
D = pd.read_csv(f"{BB}/daily_stop_grid.csv.gz", parse_dates=["t", "d"]); D["tf"] = "Daily"
W = pd.read_csv(f"{BB}/weekly_stop_grid.csv.gz", parse_dates=["t", "d"]); W["tf"] = np.where(W.set == "Nested W->4h", "Weekly->4h", "Weekly")
H = pd.read_csv(f"{BB}/nested_bigbrother.csv", parse_dates=["t", "d"]); H["tf"] = "4h"
D.loc[D.set.isin(["weekly"]), "tf"] = "Weekly"
D = D[D.set != "weekly"]                                   # weekly canon comes from the weekly grid (same numbers)
A = pd.concat([D, W, H], ignore_index=True)
A = A[A.k.isin(TEN)]
A.loc[A.set.isin(["verdict", "verdict entry"]), "tf"] = "-"
A.loc[A.set.isin(["verdict", "verdict entry"]), "set"] = "verdict entry"
A = A.drop_duplicates(["tf", "set", "stop", "vid", "d", "r"])
NAME = {"canon D": "Canon", "V4 D": "V4", "3T B D": "Three-tier B", "prev-day": "Close beyond prev. day", "canon W": "Canon",
        "V4 W": "V4", "3T B W": "Three-tier B", "prev-week": "Close beyond prev. week", "Nested W->4h": "Nested",
        "canon 4h": "Canon", "V4 4h": "V4", "three-tier B 4h": "Three-tier B", "Nested (D->4h)": "Nested (Daily->4h)",
        "Big-Brother 4h": "Big-Brother", "verdict entry": "Enter at the verdict"}


def stats(g, yrs):
    g = g.assign(rc=g.r - np.where(g.took, 0.02 / g.stop_wk.clip(lower=0.1), 0.0))
    pv = g.groupby("vid").agg(r=("r", "sum"), n=("took", "sum"), t=("t", "first"))
    tk = g[g.took].sort_values("d")
    eq = tk.rc.groupby(tk.d).sum().cumsum(); dd = (eq - eq.cummax()).min() if len(eq) else np.nan
    ry = tk.rc.sum() / yrs
    t = pv.r.mean() / pv.r.std(ddof=1) * np.sqrt(len(pv))
    return {"verdicts": len(pv), "w/entry": 100 * (pv.n > 0).mean(), "won": 100 * (tk.r > 0).mean(), "R/verdict": pv.r.mean(),
            "t": t, "R/yr": ry, "maxDD": dd, "ratio": ry / abs(dd) if dd else np.nan}


rows = []
for (tf, st, sp), g in A.groupby(["tf", "set", "stop"]):
    full = stats(g, 7.8)
    e = stats(g[g.t < "2023"], 4.0); l = stats(g[g.t >= "2023"], 3.8)
    rows.append({"tf": tf, "entry": NAME.get(st, st), "stop": sp, **full, "R/v 19-22": e["R/verdict"], "R/v 23-26": l["R/verdict"],
                 "ratio 19-22": e["ratio"], "ratio 23-26": l["ratio"]})
R = pd.DataFrame(rows)
R.to_csv(f"{BB}/common_footing_overview.csv", index=False)
best = R.sort_values("ratio", ascending=False).groupby(["tf", "entry"]).head(1).sort_values("ratio", ascending=False)
pd.set_option("display.width", 250)
cols = ["tf", "entry", "stop", "w/entry", "won", "R/verdict", "R/v 19-22", "R/v 23-26", "R/yr", "maxDD", "ratio", "ratio 19-22", "ratio 23-26"]
print(best[cols].round(2).to_string(index=False))
