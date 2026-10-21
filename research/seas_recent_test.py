#!/usr/bin/env python3
"""Seasonal windows that must also have worked in the last 5 years (on top of 12 of 15). Walk-forward board replay
(research/verdict_test.py, SKIP_SLOW=1): rc_base (board), rc_3 / rc_4 / rc_5 (SEAS_RECENT=3/4/5, every window),
rc_4s / rc_5s (SEAS_RECENT=4/5 SEAS_RECENT_SOLO=1: only windows that must stand alone, i.e. calendar-only verdicts).
Run each with OUT=<name>.json, then this script. Output: data/research/seas_recent.json"""
import json, os
import numpy as np, pandas as pd

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "research")


def agg(g):
    if not len(g):
        return {"n": 0}
    per = g.groupby(g.t.dt.to_period("M")).r.mean()
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "total": round(float(g.r.sum())), "t": round(float(per.mean() / per.std(ddof=1) * np.sqrt(len(per))), 1),
            "2019-22": round(float(g[g.t < "2023"].r.mean()), 2), "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2)}


if __name__ == "__main__":
    out = {}
    for f in ("rc_base", "rc_3", "rc_4", "rc_5", "rc_4s", "rc_5s"):
        v = pd.DataFrame(json.load(open(os.path.join(D, f + ".json")))["trades"])
        v["t"] = pd.to_datetime(v.t)
        nf = v[v.sector != "Currencies"]
        out[f] = {"board": agg(v), "outside_fx": agg(nf), "calendar_only": agg(v[v.basis == "Calendar only"]),
                  "calendar_only_not_fx": agg(nf[nf.basis == "Calendar only"]), "top_setups": agg(nf[nf.basis == "COT + calendar"])}
    json.dump(out, open(os.path.join(D, "seas_recent.json"), "w"), indent=1)
