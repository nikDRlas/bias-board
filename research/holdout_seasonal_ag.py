"""HOLDOUT check of calendar-alone-only-in-agriculture (chosen on 2019-26) on 2013-18 with 10-year windows (15-year windows need data before 2003). Result 2026-10-24: ag +0.29% vs blind (t 1.4), metals & energy +0.52% (t 0.2), currencies +0.15%, indices -0.20%: weak, not contradicted."""
import os, sys
os.environ["SEAS_YEARS"] = "10"
import numpy as np, pandas as pd
sys.path.insert(0, "bias"); import core as C, seasonal as SS
rows = []
for k, meta in C.M.items():
    p = C.load_px(k); cal = SS.Calendar(p); x = p.to_numpy(float); busy = pd.Timestamp("1900")
    for t in pd.date_range("2013-01-05", "2018-12-29", freq="W-SAT"):
        if t <= busy: continue
        ws, st = cal.windows(t, min_move=SS.SOLO_MIN_MOVE)
        if st != "driver": continue
        w = ws[0]; s = max(t + pd.Timedelta(days=1), pd.Timestamp(w["start"])); e = pd.Timestamp(w["end"])
        a, b = p.index.searchsorted(s), p.index.searchsorted(e)
        if b >= len(p) or b <= a: continue
        sg = 1 if w["side"] == "BUY" else -1
        q = x[(p.index >= "2013-01-01") & (p.index <= "2018-12-31")]; L = b - a
        rows.append({"sec": "Agriculture" if meta[3] == "Agriculture" else "Currencies" if meta[3] == "FX" else "Indices" if meta[3] == "Indices" else "Metals & energy",
                     "t": t, "r": 100 * sg * (x[b] / x[a] - 1), "x": 100 * sg * (x[b] / x[a] - 1) - float(np.mean(sg * (q[L:] / q[:-L] - 1) * 100))})
        busy = p.index[b]
d = pd.DataFrame(rows)
print("HOLDOUT 2013-18, calendar-only verdicts (10-year windows, >= 8 of 10, size >= 3 normal days), one per market at a time")
for s, g in [("all", d)] + list(d.groupby("sec")):
    per = g.groupby(g.t.dt.to_period("M")).x.mean(); t = per.mean()/per.std(ddof=1)*np.sqrt(len(per)) if len(per) > 2 else np.nan
    print(f"  {s:16s} n {len(g):3d} won {100*(g.r>0).mean():5.1f}% avg {g.r.mean():+.2f}% minus blind {g.x.mean():+.2f}% t {t:+.1f}")
