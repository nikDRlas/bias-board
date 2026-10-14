#!/usr/bin/env python3
"""The same walk-forward test on the 21 currency crosses (no USD leg).

Seasonal: the board's window scan on each cross, sequential trades, entry max(Saturday, start) -> window end.
COT: there is no COT for crosses, so the read is DERIVED from the two legs' futures COT (each vs USD):
  base bullish & quote bearish -> cross bullish (and the mirror); one leg with a side and the other neutral ->
  that leg decides; both legs the same way, or either leg with groups disagreeing -> no side. Held 8 weeks.
Prices: LSE daily spot (data_cache/lse_daily of the research repo, to 2026-08-21).
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                                 # noqa: E402
from conflict_test import Seas, ret, summary                     # noqa: E402

PX = "/Users/Niklas/supply_demand_intraday/data_cache/lse_daily"
LEG = {"EUR": "6E", "GBP": "6B", "JPY": "6J", "CHF": "6S", "AUD": "6A", "CAD": "6C", "NZD": "6N"}
CROSSES = ["EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD", "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD",
           "GBPNZD", "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD", "CADJPY", "CADCHF", "NZDJPY", "NZDCHF", "NZDCAD", "CHFJPY"]
READ = {c: C.CotReader(k) for c, k in LEG.items()}


def px(pair):
    p = pd.read_csv(f"{PX}/{pair}.csv", parse_dates=["ts"]).set_index("ts").close
    return p[p.index.dayofweek < 5]


def cross_read(pair, t):
    b, q = READ[pair[:3]].read(t), READ[pair[3:]].read(t)
    if "MIXED" in (b, q):
        return "NEUTRAL", 0
    vb = {"BULLISH": 1, "BEARISH": -1}.get(b, 0)
    vq = {"BULLISH": 1, "BEARISH": -1}.get(q, 0)
    if vb and vq and vb == vq:
        return "NEUTRAL", 0
    v = vb - vq
    return ("BULLISH" if v > 0 else "BEARISH" if v < 0 else "NEUTRAL"), (2 if vb and vq else 1 if v else 0)


if __name__ == "__main__":
    A, B = [], []
    for pair in CROSSES:
        p = px(pair)
        end = p.index[-1]
        S = Seas(p)
        busy_s = busy_c = pd.Timestamp("1900-01-01")
        for t in pd.date_range("2016-01-02", end, freq="W-SAT"):
            d = S.driver(t)
            sd = None if d in (None, "cancel") else ("BULLISH" if d["side"] == "BUY" else "BEARISH")
            cr, legs = cross_read(pair, t)
            if sd and t > busy_s:
                x = ret(p, max(t, d["start"]), d["end"], d["side"])
                if x and pd.Timestamp(x["exit"]) <= end:
                    rel = "none" if cr == "NEUTRAL" else ("agree" if cr == sd else "against")
                    A.append({"m": pair, "t": str(t.date()), "rel": rel, "wins": d["wins"], **x})
                    busy_s = pd.Timestamp(x["exit"])
            if cr != "NEUTRAL" and t > busy_c:
                x = ret(p, t + pd.Timedelta(days=1), t + pd.Timedelta(weeks=8), cr)
                if x and pd.Timestamp(x["exit"]) <= end:
                    rel = "none" if sd is None else ("agree" if sd == cr else "against")
                    B.append({"m": pair, "t": str(t.date()), "legs": legs, "rel": rel, **x})
                    busy_c = pd.Timestamp(x["exit"])
        print(pair, len([a for a in A if a["m"] == pair]), len([b for b in B if b["m"] == pair]), flush=True)
    out = {"seasonal_all": summary([dict(a, k="all") for a in A], "k")["all"], "seasonal_by_cot": summary(A, "rel"),
           "seasonal_first": min(a["t"] for a in A),
           "cot_all": summary([dict(b, k="all") for b in B], "k")["all"], "cot_by_legs": summary(B, "legs"),
           "cot_by_seasonal": summary(B, "rel"),
           "seasonal_by_pair": summary(A, "m"), "cot_by_pair": summary(B, "m"),
           "seasonal_by_year": summary([dict(a, y=a["t"][:4]) for a in A], "y"),
           "cot_by_year": summary([dict(b, y=b["t"][:4]) for b in B], "y")}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump({**out, "trades_seasonal": A, "trades_cot": B},
              open(os.path.join(HERE, "..", "data", "research", "crosses.json"), "w"), indent=1)
    for k in ("seasonal_first", "seasonal_all", "seasonal_by_cot", "cot_all", "cot_by_legs", "cot_by_seasonal", "seasonal_by_year", "cot_by_year"):
        print(k, json.dumps(out[k]))
