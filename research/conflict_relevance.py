#!/usr/bin/env python3
"""In a COT-vs-calendar contradiction, when does COT matter?

Same walk-forward as conflict_test.py (every Saturday, the board's own rules, only what was known that day).
For each seasonal trade taken while COT pointed the other way, two candidate definitions of "COT is relevant":

  played_out   look back at this window in its past 15 years: in the years where COT was ALSO against it at the
               window start, did the window still pay? "Played out" = it paid in at least 2/3 of those years,
               with at least 3 such years. If it played out, COT is treated as NOT relevant (calendar stands).
  both_groups  COT read carried by both retail and commercials (vs one group).

Output: data/research/conflict_relevance.json
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
from conflict_test import Seas, ret, summary           # noqa: E402

MIN_YEARS, SHARE = 3, 2 / 3


def past_against(S, reader, d, t):
    """the driver window in its 15 past years: (years COT was against at the start, of which the window paid)"""
    a = S.past(t.year, d, reader)["summary"]["against"]
    return a["n"], a["w"]


if __name__ == "__main__":
    end = C.TODAY - pd.Timedelta(days=1)
    rows = []
    for k in C.M:
        p = C.load_px(k)
        S, Q = Seas(p), C.CotReader(k)
        busy = pd.Timestamp("1900-01-01")
        for t in pd.date_range("2016-01-02", end, freq="W-SAT"):
            if t <= busy:
                continue
            d = S.driver(t)
            if d in (None, "cancel"):
                continue
            sd = "BULLISH" if d["side"] == "BUY" else "BEARISH"
            cr = Q.read(t)
            groups = Q.last_groups
            x = ret(p, max(t, d["start"]), d["end"], d["side"])
            if not x or pd.Timestamp(x["exit"]) > end:
                continue
            busy = pd.Timestamp(x["exit"])
            if cr not in ("BULLISH", "BEARISH") or cr == sd:
                continue                                         # only contradictions
            n, w = past_against(S, Q, d, t)
            played = n >= MIN_YEARS and w / n >= SHARE
            rows.append({"m": k, "t": str(t.date()), "side": d["side"], "groups": groups, "past_n": n, "past_w": int(w),
                         "played_out": "played out" if played else ("too few years" if n < MIN_YEARS else "did not play out"),
                         "sec": "FX" if C.M[k][3] == "FX" else "Commodities", **x})
        print(k, sum(r["m"] == k for r in rows), flush=True)
    out = {"all": summary([dict(r, a="all") for r in rows], "a")["all"],
           "by_played_out": summary(rows, "played_out"),
           "by_groups": summary(rows, "groups"),
           "by_played_out_sector": summary([dict(r, ps=r["played_out"] + " · " + r["sec"]) for r in rows], "ps"),
           "by_played_out_half": summary([dict(r, ph=r["played_out"] + " · " + ("2019-22" if r["t"] < "2023" else "2023-26")) for r in rows], "ph")}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump({**out, "trades": rows}, open(os.path.join(HERE, "..", "data", "research", "conflict_relevance.json"), "w"), indent=1)
    for key, v in out.items():
        print(key, json.dumps(v))
