#!/usr/bin/env python3
"""Macro pair score on cross pairs (EdgeFinder pair rule: base minus quote per indicator slot, clipped +-2, summed),
for the 10 crosses among EUR GBP JPY AUD CAD (CHF / NZD: no calendar history on LSE). LSE daily closes.
Every Saturday 2016 - Sep 2026; move of the cross over the next 1, 2, 4, 8 weeks in units of a normal move; t divided
by sqrt(weeks) for the overlap of weekly starts. (a) followed as a direction, (b) by score size, (c) correlation.
Prices: fetched to the scratch folder given as the first argument. Output: data/research/macro_crosses.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import macro as MC                                     # noqa: E402
from macro_pair_test import slots                      # noqa: E402

END = pd.Timestamp("2026-09-10")
CROSSES = ["EURGBP", "EURJPY", "EURAUD", "EURCAD", "GBPJPY", "GBPAUD", "GBPCAD", "AUDJPY", "AUDCAD", "CADJPY"]
BINS = [(-99, -7, "-7 or lower"), (-6, -3, "-6 to -3"), (-2, 2, "-2 to +2"), (3, 6, "+3 to +6"), (7, 99, "+7 or higher")]

if __name__ == "__main__":
    pxdir = sys.argv[1]
    cal = MC.load_calendar()
    days = pd.date_range("2015-06-01", END)
    S = {c: slots(cal, c, days) for c in ("EUR", "GBP", "JPY", "AUD", "CAD")}
    rows = []
    for cx in CROSSES:
        base, quote = cx[:3], cx[3:]
        sc = (S[base] - S[quote]).clip(-2, 2).sum(axis=1)
        raw = json.load(open(os.path.join(pxdir, cx + ".json")))
        p = pd.Series([x[1] for x in raw], index=pd.to_datetime([x[0] for x in raw])).astype(float)
        p = p[p.index.dayofweek < 5].groupby(level=0).last()
        lc = np.log(p.to_numpy())
        for t in pd.date_range("2016-01-02", END - pd.Timedelta(weeks=9), freq="W-SAT"):
            a = p.index.searchsorted(t)
            if a < 300:
                continue
            s = float(sc[sc.index <= t].iloc[-1])
            dv = np.diff(lc[max(0, a - 253):a]).std()
            for h in (1, 2, 4, 8):
                b = p.index.searchsorted(t + pd.Timedelta(weeks=h))
                if b >= len(p):
                    continue
                rows.append({"cx": cx, "h": h, "score": s, "d": str(t.date()), "z": (lc[b] - lc[a]) / (dv * np.sqrt(b - a)),
                             "r": 100 * (np.exp(lc[b] - lc[a]) - 1)})
    d = pd.DataFrame(rows)
    res = {}
    for h in (1, 2, 4, 8):
        x = d[d.h == h]
        f = x[x.score != 0].copy()
        f["dz"] = np.sign(f.score) * f.z
        f["dr"] = np.sign(f.score) * f.r
        res[f"{h}w"] = {"followed": {"n": len(f), "right": round(100 * float((f.dz > 0).mean()), 1), "avg": round(float(f.dr.mean()), 3),
                                     "t": round(float(f.dz.mean() / f.dz.std() * np.sqrt(len(f)) / np.sqrt(h)), 2),
                                     "2016-20": round(float(f[f.d < "2021"].dz.mean()), 3), "2021-26": round(float(f[f.d >= "2021"].dz.mean()), 3)},
                        "corr": round(float(np.corrcoef(x.score, x.z)[0, 1]), 3),
                        "by_size": {lab: {"n": int(((x.score >= lo) & (x.score <= hi)).sum()),
                                          "up": round(100 * float((x[(x.score >= lo) & (x.score <= hi)].z > 0).mean()), 1),
                                          "avg": round(float(x[(x.score >= lo) & (x.score <= hi)].r.mean()), 3)} for lo, hi, lab in BINS},
                        "by_cross_t": {c: round(float((np.sign(g[g.score != 0].score) * g[g.score != 0].z).mean() / (np.sign(g[g.score != 0].score) * g[g.score != 0].z).std() * np.sqrt((g.score != 0).sum()) / np.sqrt(h)), 2) for c, g in x.groupby("cx")}}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "macro_crosses.json"), "w"), indent=1)
    for h, v in res.items():
        fo = v["followed"]
        print(f"\n{h}: followed n{fo['n']} right {fo['right']}% avg {fo['avg']:+.3f}% t {fo['t']:+.2f} (16-20 {fo['2016-20']:+.3f} / 21-26 {fo['2021-26']:+.3f}) | corr score vs next move {v['corr']:+.3f}")
        print("    by size (share of times the cross rose):", {k: (o['n'], o['up'], o['avg']) for k, o in v["by_size"].items()})
        print("    t per cross:", v["by_cross_t"])
