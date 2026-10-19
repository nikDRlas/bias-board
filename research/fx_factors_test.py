#!/usr/bin/env python3
"""Currencies: carry (level of the 2-year yield gap to the US: own minus US, DX = US minus Germany) and momentum
(3- and 12-month return) - as a direction on their own and as a filter on the board's currency verdicts.
(a) every 4th Saturday 2016 - Sep 2026 (where LSE's yield table ends), 4- and 13-week hold, vs drift;
(b) the board's currency verdicts (research/verdict_test.py, current rules) split by the factor agreeing or against.
Output: data/research/fx_factors.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
from yields_filter_test import Y, OWN                  # noqa: E402

FX = ["6E", "6B", "6J", "6S", "6A", "6C", "6N", "DX"]
END = Y["US2Y"].index.max()


def carry(k):
    return (Y[OWN[k]] - Y["US2Y"]) if k in OWN else (Y["US2Y"] - Y["DE2Y"])


def factors(k, p, t):
    c = carry(k)
    c = c[c.index <= t].dropna()
    pp = p[p.index <= t]
    return {"carry": int(np.sign(c.iloc[-1])) if len(c) else 0,
            "mom3": int(np.sign(pp.iloc[-1] / pp.iloc[-64] - 1)) if len(pp) > 64 else 0,
            "mom12": int(np.sign(pp.iloc[-1] / pp.iloc[-253] - 1)) if len(pp) > 253 else 0}


def st(r, ex):
    r, ex = np.array(r), np.array(ex)
    if len(r) < 8:
        return None
    return {"n": len(r), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "vs_drift": round(float(ex.mean()), 2), "t": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(ex))), 2)}


if __name__ == "__main__":
    px = {k: C.load_px(k) for k in FX}
    res = {"direction": {}, "filter": {}}
    acc = {}
    for k in FX:
        p = px[k]
        lc = np.log(p.to_numpy(float))
        for t in pd.date_range("2016-01-02", END - pd.Timedelta(weeks=14), freq="4W-SAT"):
            a = p.index.searchsorted(t)
            f = factors(k, p, t)
            for h in (4, 13):
                b = p.index.searchsorted(t + pd.Timedelta(weeks=h))
                if b >= len(p):
                    continue
                L, lo = b - a, max(0, a - 2520)
                dr = float((lc[lo + L:a] - lc[lo:a - L]).mean())
                for n, sg in f.items():
                    if not sg:
                        continue
                    r = 100 * (np.exp(sg * (lc[b] - lc[a])) - 1)
                    key = (n, h, "2016-20" if t.year < 2021 else "2021-26")
                    acc.setdefault((n, h), ([], [])); acc.setdefault(key, ([], []))
                    for kk in ((n, h), key):
                        acc[kk][0].append(r); acc[kk][1].append(r - 100 * (np.exp(sg * dr) - 1))
    for (kk), v in acc.items():
        res["direction"][" · ".join(map(str, kk))] = st(*v)
    T = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
    T = T[(T.sector == "Currencies") & (pd.to_datetime(T.t) <= END)]
    rows = []
    for _, r in T.iterrows():
        f = factors(r.m, px[r.m], pd.Timestamp(r.t))
        sg = 1 if r.v == "BULLISH" else -1
        rows.append({**r.to_dict(), **{n: ("agrees" if v == sg else "against" if v else "flat") for n, v in f.items()}})
    d = pd.DataFrame(rows)
    for n in ("carry", "mom3", "mom12"):
        for lab, g in d.groupby(n):
            res["filter"][f"{n} · {lab}"] = {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
                                             "2019-22": round(float(g[g.t < "2023"].r.mean()), 2), "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2)}
        for (b, lab), g in d.groupby(["basis", n]):
            if b in ("COT only", "COT + calendar") and len(g) >= 8:
                res["filter"][f"{n} · {b} · {lab}"] = {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2)}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "fx_factors.json"), "w"), indent=1)
    print("(a) as a direction on its own (8 currencies, every 4th Saturday 2016 - Sep 2026)")
    for k2, o in sorted(res["direction"].items()):
        if o: print(f"   {k2:24s} n{o['n']:4d} won {o['win']:4.1f}% avg {o['avg']:+.2f}% vs drift {o['vs_drift']:+.2f}% (t {o['t']:+.1f})")
    print("\n(b) the board's currency verdicts split by the factor")
    for k2, o in res["filter"].items():
        print(f"   {k2:40s} n{o['n']:3d} won {o['win']:4.1f}% avg {o['avg']:+.2f}%" + (f" | 19-22 {o['2019-22']:+.2f} 23-26 {o['2023-26']:+.2f}" if "2019-22" in o else ""))
