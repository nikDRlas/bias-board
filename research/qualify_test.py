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


class Market:
    def __init__(self, k):
        self.p = C.load_px(k)
        x = C.load_cot(k)
        self.dates = x.index
        self.rows = {}
        for g in ("retail", "comm"):
            for lb, L in C.LB.items():
                v = C.pctile(x[g], L).to_numpy()
                for side in ("hi", "lo"):
                    lit = (v >= C.HI) if side == "hi" else (v <= C.LO)
                    opp = (v <= C.LO) if side == "hi" else (v >= C.HI)
                    cases, armed = [], True
                    for i in range(len(v)):
                        if lit[i] and not (i and lit[i - 1]):
                            if armed:
                                cases.append(i)
                                armed = False
                        elif opp[i]:
                            armed = True
                    sgn = (1 if side == "hi" else -1) * (1 if g == "comm" else -1)
                    res = []
                    for i in cases:
                        d = self.dates[i]
                        out = {"i": i, "d": d}
                        for h in (4, 8):
                            a = self.p.index.searchsorted(d)
                            b = self.p.index.searchsorted(d + pd.Timedelta(weeks=h))
                            out[h] = (sgn * (self.p.iloc[b] / self.p.iloc[a] - 1), self.p.index[b]) if b < len(self.p) else None
                        res.append(out)
                    self.rows[g, lb, side] = (lit, res)

    def read(self, t, mode):
        i = self.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
        if i < 300:
            return None
        dirs = {}
        for g, follow in (("retail", -1), ("comm", 1)):
            lit_rows = []
            for lb in C.LB:
                for side in ("hi", "lo"):
                    if self.rows[g, lb, side][0][i]:
                        lit_rows.append((lb, side))
            sides = {s for _, s in lit_rows}
            if not lit_rows or len(sides) > 1:
                continue
            if mode == "plain2" and len(lit_rows) < 2:
                continue
            if mode == "gated":
                ok = False
                for lb, side in lit_rows:
                    lit, cases = self.rows[g, lb, side]
                    j = i
                    while j > 0 and lit[j - 1]:
                        j -= 1                                    # start of the live episode
                    t0 = self.dates[i] - pd.DateOffset(years=C.HIST[lb])
                    for h in (4, 8):
                        r = [c[h][0] for c in cases if c["i"] < j and c["d"] >= t0 and c[h] and c[h][1] <= t]
                        if len(r) >= C.BAR_N and np.mean([x > 0 for x in r]) >= C.BAR_WIN / 100 and np.mean(r) > 0:
                            ok = True
                if not ok:
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
