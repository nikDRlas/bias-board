#!/usr/bin/env python3
"""Does Bernd's evidence gate improve the COT read?

Three COT reads, each run every Saturday with only what was known that day, 8-week hold, one trade per market:
  plain2   the board's tested read: a group counts with >= 2 of 5 lookbacks at the same extreme
  plain1   a group counts with >= 1 lit lookback
  gated    Bernd's way: a group counts with >= 1 lit lookback, but only if one of its lit rows "qualifies":
           >= 6 past cases, >= 60% wins, average > 0 at 4 or 8 weeks. Past cases use his rule (extreme reached
           after the opposite extreme), his history spans, returns from the report Tuesday's close, and only
           cases whose 4/8-week result was already known on that Saturday.
In every read, retail and commercials pointing opposite ways = no side.
Output: data/research/qualify.json
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                      # noqa: E402
from conflict_test import ret, summary               # noqa: E402


from bernd import Gate                                 # noqa: E402  (the gate now lives in bias/bernd.py)


class Market(Gate):
    def read(self, t, mode):
        if mode == "gated":
            return Gate.read(self, t)
        return self._plain(t, mode)

    def _plain(self, t, mode):
        i = self.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
        if i < 300:
            return None
        dirs = {}
        for g, follow in (("retail", -1), ("comm", 1)):
            lit_rows = [(lb, side) for lb in C.LB for side in ("hi", "lo") if self.rows[g, lb, side][0][i]]
            sides = {s for _, s in lit_rows}
            if not lit_rows or len(sides) > 1 or (mode == "plain2" and len(lit_rows) < 2):
                continue
            s = next(iter(sides))
            dirs[g] = "BULLISH" if follow * (1 if s == "hi" else -1) > 0 else "BEARISH"
        if not dirs or len(set(dirs.values())) > 1:
            return None
        return next(iter(dirs.values()))


if __name__ == "__main__":
    end = C.TODAY - pd.Timedelta(days=1)
    sats = pd.date_range("2016-01-02", end, freq="W-SAT")
    trades = {m: [] for m in ("plain2", "plain1", "gated")}
    for k in C.M:
        mk = Market(k)
        for mode in trades:
            busy = pd.Timestamp("1900-01-01")
            for t in sats:
                if t <= busy:
                    continue
                v = mk.read(t, mode)
                if not v:
                    continue
                x = ret(mk.p, t + pd.Timedelta(days=1), t + pd.Timedelta(weeks=8), v)
                if x and pd.Timestamp(x["exit"]) <= end:
                    trades[mode].append({"m": k, "t": str(t.date()), "dir": v,
                                         "sec": "FX" if C.M[k][3] == "FX" else "Commodities", **x})
                    busy = pd.Timestamp(x["exit"])
        print(k, {m: sum(r["m"] == k for r in v) for m, v in trades.items()}, flush=True)
    out = {}
    for m, rows in trades.items():
        out[m] = {"all": summary([dict(r, a="all") for r in rows], "a")["all"], "by_sector": summary(rows, "sec"),
                  "by_half": summary([dict(r, half="2016-20" if r["t"] < "2021" else "2021-26") for r in rows], "half")}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump({**out, "trades": trades}, open(os.path.join(HERE, "..", "data", "research", "qualify.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
