#!/usr/bin/env python3
"""COT read record when retail AND commercials agree (commercials long extreme + retail short extreme, or the mirror),
versus when only one group carries the read. Every case since prices start: the week the read switched into that
state; 8-week result from the first close after the Friday release. Output: data/research/both_groups.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

SECTOR = lambda k: {"FX": "Currencies", "Indices": "Indices", "Agriculture": "Agriculture"}.get(C.M[k][3], "Metals & energy")


def cases(k):
    """two separate sequential passes: trades only on 'both groups agree' weeks, and only on 'one group' weeks.
    One position at a time, held 8 weeks from the first close after the release; the next case only after exit."""
    p, rd = C.load_px(k), C.CotReader(k)
    lp = np.log(p)
    out = []
    for want_both in (True, False):
        busy = pd.Timestamp("1900-01-01")
        for i in range(len(rd.dates)):
            v = rd.read_at(i)
            if v not in ("BULLISH", "BEARISH") or (rd.last_groups == 2) != want_both:
                continue
            rel = rd.dates[i] + pd.Timedelta(days=3)
            if rel < p.index[0] or rel <= busy:
                continue
            a, b = p.index.searchsorted(rel), p.index.searchsorted(rel + pd.Timedelta(weeks=8))
            if b >= len(p):
                continue
            sg = 1 if v == "BULLISH" else -1
            vol = lp.diff().iloc[max(1, a - 60):a].std() * np.sqrt(b - a)
            out.append({"m": k, "d": str(rd.dates[i].date()), "dir": v, "both": want_both,
                        "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1), "z": float(sg * (lp.iloc[b] - lp.iloc[a]) / vol)})
            busy = p.index[b]
    return out


def agg(rows):
    if len(rows) < 3:
        return None
    r, z = np.array([x["r"] for x in rows]), np.array([x["z"] for x in rows])
    z = z[np.isfinite(z)]
    return {"n": len(rows), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)}


if __name__ == "__main__":
    rows = [c for k in C.M for c in cases(k)]
    res = {"pooled": {lab: agg([r for r in rows if r["both"] == f]) for lab, f in (("both", True), ("one", False))},
           "by_sector": {s: {lab: agg([r for r in rows if r["both"] == f and SECTOR(r["m"]) == s]) for lab, f in (("both", True), ("one", False))}
                         for s in ("Currencies", "Metals & energy", "Indices", "Agriculture")},
           "by_market": {k: {lab: agg([r for r in rows if r["both"] == f and r["m"] == k]) for lab, f in (("both", True), ("one", False))} for k in C.M},
           "by_half": {h: {lab: agg([r for r in rows if r["both"] == f and (r["d"] < "2015") == (h == "2003-14")]) for lab, f in (("both", True), ("one", False))}
                       for h in ("2003-14", "2015-26")}}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump({**res, "cases": rows}, open(os.path.join(HERE, "..", "data", "research", "both_groups.json"), "w"), indent=1)
    print("pooled", res["pooled"]); print("halves", res["by_half"])
    for s, v in res["by_sector"].items(): print(" ", s, v)
    for k, v in res["by_market"].items(): print("   ", k, "both", v["both"], "| one", v["one"])
