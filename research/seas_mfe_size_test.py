#!/usr/bin/env python3
"""Seasonal window strength by its usual best point along the way (MFE) instead of its start->end move (board).
Walk-forward board replay (research/verdict_test.py, SKIP_SLOW=1) per config:
  mf_base   size = start->end move >= 3 normal days (board)
  mf_sX     SEAS_SIZE=mfe SEAS_MIN_MOVE=X: size = usual best point >= X normal days (X = 3,4,5,6,8)
  mf_done   SEAS_DONE=mfe: 'move done' when this year's move so far >= the usual best point (board: >= the usual move)
Run each with OUT=<name>.json, then this script. Output: data/research/seas_mfe_size.json"""
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
    for f in ("mf_base", "mf_s3", "mf_s4", "mf_s5", "mf_s6", "mf_s8", "mf_done"):
        v = pd.DataFrame(json.load(open(os.path.join(D, f + ".json")))["trades"])
        v["t"] = pd.to_datetime(v.t)
        out[f] = {"board": agg(v), "calendar_only": agg(v[v.basis == "Calendar only"]),
                  "cot_calendar": agg(v[v.basis == "COT + calendar"]), "outside_fx": agg(v[v.sector != "Currencies"])}
    json.dump(out, open(os.path.join(D, "seas_mfe_size.json"), "w"), indent=1)
