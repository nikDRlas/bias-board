#!/usr/bin/env python3
"""What makes a calendar-alone verdict work: amplitude (SEAS_MIN_MOVE 3 board / 4 / 5 / 6 / 8 normal days), beating the
drift (SEAS_TRUE 11 / 12 of 15 detrended years, calendar-alone windows only), and where (SEAS_SOLO_SECTORS=Agriculture:
the calendar may stand alone only on agricultural markets; NoSector: nowhere). Walk-forward board replay
(research/verdict_test.py, SKIP_SLOW=1) per config with OUT=am_<name>.json, then this script.
Output: data/research/seas_solo_where.json (incl. the board's calendar-only verdicts by sector and market)"""
import json, os
import numpy as np, pandas as pd

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "research")


def agg(g):
    if len(g) < 3:
        return {"n": len(g)}
    per = g.groupby(g.t.dt.to_period("M")).r.mean()
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "total": round(float(g.r.sum())), "t": round(float(per.mean() / per.std(ddof=1) * np.sqrt(len(per))), 1),
            "2019-22": round(float(g[g.t < "2023"].r.mean()), 2), "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2)}


if __name__ == "__main__":
    out = {}
    for f in ("base", "4", "5", "6", "8", "t11", "t12", "ag", "none"):
        v = pd.DataFrame(json.load(open(os.path.join(D, f"am_{f}.json")))["trades"])
        v["t"] = pd.to_datetime(v.t)
        c = v[v.basis == "Calendar only"]
        out[f] = {"board": agg(v), "outside_fx": agg(v[v.sector != "Currencies"]), "currencies": agg(v[v.sector == "Currencies"]),
                  "calendar_only": agg(c), "top_setups": agg(v[(v.basis == "COT + calendar") & (v.sector != "Currencies")])}
        if f == "base":
            out[f]["calendar_only_by_sector"] = {s: agg(g) for s, g in c.groupby("sector")}
            out[f]["calendar_only_by_market"] = {m: agg(g) for m, g in c.groupby("m")}
    json.dump(out, open(os.path.join(D, "seas_solo_where.json"), "w"), indent=1)
