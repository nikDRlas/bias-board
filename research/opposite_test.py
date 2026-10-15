#!/usr/bin/env python3
"""COT reads that require opposite extremes between commercials and the speculators.

A group is at an extreme when >= 2 of its 5 lookbacks sit at the same extreme (>= 80th or <= 20th percentile).
The read always follows the commercials' side. Variants:
  board            the board's read (retail faded, commercials followed, either may carry it)
  comm_alone       commercials at an extreme, nothing else required
  comm_vs_any      commercials at an extreme AND retail or funds at the opposite extreme
  comm_vs_retail   ... AND retail at the opposite extreme
  comm_vs_funds    ... AND funds (non-commercials) at the opposite extreme
  comm_vs_both     ... AND retail AND funds both at the opposite extreme
Each: one position per market at a time, 8 weeks from the first close after the Friday release, since 2003.
Output: data/research/opposite.json
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

SECTOR = lambda k: {"FX": "Currencies", "Indices": "Indices", "Agriculture": "Agriculture"}.get(C.M[k][3], "Metals & energy")
VARIANTS = ["board", "comm_alone", "comm_vs_any", "comm_vs_retail", "comm_vs_funds", "comm_vs_both"]


def side(P, g, i):
    s = [("hi" if v >= C.HI else "lo") for v in (P[g][lb][i] for lb in C.LB) if np.isfinite(v) and (v >= C.HI or v <= C.LO)]
    return s[0] if len(s) >= 2 and len(set(s)) == 1 else None


def read(variant, rd, P, i):
    if variant == "board":
        v = rd.read_at(i)
        return v if v in ("BULLISH", "BEARISH") else None
    c = side(P, "comm", i)
    if not c:
        return None
    opp = "lo" if c == "hi" else "hi"
    r, f = side(P, "retail", i) == opp, side(P, "fund", i) == opp
    ok = {"comm_alone": True, "comm_vs_any": r or f, "comm_vs_retail": r, "comm_vs_funds": f, "comm_vs_both": r and f}[variant]
    return ("BULLISH" if c == "hi" else "BEARISH") if ok else None


def agg(rows):
    if len(rows) < 3:
        return None
    r, z = np.array([x["r"] for x in rows]), np.array([x["z"] for x in rows])
    z = z[np.isfinite(z)]
    return {"n": len(rows), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)}


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, rd = C.load_px(k), C.CotReader(k)
        x = C.load_cot(k)
        P = {g: {lb: C.pctile(x[g], L).to_numpy() for lb, L in C.LB.items()} for g in ("retail", "comm", "fund")}
        lp = np.log(p)
        for var in VARIANTS:
            busy = pd.Timestamp("1900-01-01")
            for i in range(len(rd.dates)):
                v = read(var, rd, P, i)
                if not v:
                    continue
                rel = rd.dates[i] + pd.Timedelta(days=3)
                if rel < p.index[0] or rel <= busy:
                    continue
                a, b = p.index.searchsorted(rel), p.index.searchsorted(rel + pd.Timedelta(weeks=8))
                if b >= len(p) or a < 61:
                    continue
                sg = 1 if v == "BULLISH" else -1
                vol = lp.diff().iloc[a - 60:a].std() * np.sqrt(b - a)
                rows.append({"var": var, "m": k, "sector": SECTOR(k), "d": str(rd.dates[i].date()),
                             "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1), "z": float(sg * (lp.iloc[b] - lp.iloc[a]) / vol)})
                busy = p.index[b]
        print(k, flush=True)
    res = {}
    for var in VARIANTS:
        R = [x for x in rows if x["var"] == var]
        res[var] = {"2003-26": agg(R), "2016-26": agg([x for x in R if x["d"] >= "2016"]),
                    "2003-15": agg([x for x in R if x["d"] < "2016"]),
                    "by_sector": {s: agg([x for x in R if x["sector"] == s]) for s in ("Currencies", "Metals & energy", "Indices", "Agriculture")},
                    "by_market": {k: agg([x for x in R if x["m"] == k]) for k in C.M}}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "opposite.json"), "w"), indent=1)
    for var, v in res.items():
        print(f"{var:15s} all {v['2003-26']} | 2003-15 {v['2003-15']} | 2016-26 {v['2016-26']}")
        print("                ", {s: (o["n"], o["win"], o["t"]) if o else None for s, o in v["by_sector"].items()})
