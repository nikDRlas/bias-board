#!/usr/bin/env python3
"""Seasonal windows picked from the last 10 years (>= 8 of 10) vs the last 15 years (>= 12 of 15).
Same walk-forward as conflict_test.py: every Saturday the board's window scan with only earlier years,
one trade per market at a time, from max(Saturday, window start) to the window end.
Output: data/research/seasonal_ny.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
from conflict_test import ret, summary                 # noqa: E402

SECTOR = lambda k: {"FX": "Currencies", "Indices": "Indices", "Agriculture": "Agriculture"}.get(C.M[k][3], "Metals & energy")


def run(ny, gate, start):
    SS.NY, SS.GATE = ny, gate
    end = C.TODAY - pd.Timedelta(days=1)
    rows = []
    for k in C.M:
        p = C.load_px(k)
        cal = SS.Calendar(p)
        busy = pd.Timestamp("1900-01-01")
        for t in pd.date_range(start, end, freq="W-SAT"):
            if t <= busy:
                continue
            d = cal.driver(t)
            if d in (None, "cancel"):
                continue
            x = ret(p, max(t, d["start"]), d["end"], d["side"])
            if x and pd.Timestamp(x["exit"]) <= end:
                rows.append({"m": k, "t": str(t.date()), "side": d["side"], "sector": SECTOR(k), **x})
                busy = pd.Timestamp(x["exit"])
    return rows


def report(rows):
    return {"all": summary([dict(r, a="all") for r in rows], "a").get("all"), "by_sector": summary(rows, "sector"),
            "by_side": summary(rows, "side")}


if __name__ == "__main__":
    r15 = run(15, 12, "2019-01-05")
    r10 = run(10, 8, "2014-01-04")
    res = {"15y_2019_26": report(r15), "10y_2019_26": report([r for r in r10 if r["t"] >= "2019"]),
           "10y_2014_26": report(r10), "10y_2014_18": report([r for r in r10 if r["t"] < "2019"])}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "seasonal_ny.json"), "w"), indent=1)
    for k, v in res.items():
        print(k, v["all"]); print("   ", {s: (o["n"], o["win"], o["t"]) for s, o in v["by_sector"].items()})
