"""Bernd's evidence gate, used for the CURRENCY COT read (provisional, chosen 2026-10-19).

A group (retail faded, commercials followed) counts only if one of its live rows 'qualifies': the lookback's extreme
has at least BAR_N earlier cases (his rule: an extreme reached after the group was last at the opposite extreme, within
his history span, results from the report Tuesday's close, only results known by that day) with at least BAR_WIN %
going the group's way and a positive average, at 4 or 8 weeks. Retail and commercials pointing opposite ways = no side.
Tested in research/verdict_test.py (FX_COT=bernd): data/research/fx_cot_rule.json (2019-22 / 2023-26) and the
2020-24 / 2025-26 split, where it was picked by t and held."""
import numpy as np, pandas as pd

import core as C

import os
HORIZONS = tuple(int(x) for x in os.environ.get("BERND_H", "4,8").split(","))   # research switch: horizons (weeks) a row may qualify on


class Gate:
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
                        for h in HORIZONS:
                            a = self.p.index.searchsorted(d)
                            b = self.p.index.searchsorted(d + pd.Timedelta(weeks=h))
                            out[h] = (sgn * (self.p.iloc[b] / self.p.iloc[a] - 1), self.p.index[b]) if b < len(self.p) else None
                        res.append(out)
                    self.rows[g, lb, side] = (lit, res)

    def read(self, t, detail=False):
        """the gated read on Saturday t (BULLISH / BEARISH / None); with detail also the qualifying rows"""
        i = self.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
        if i < 300:
            return (None, []) if detail else None
        dirs, good = {}, []
        for g, follow in (("retail", -1), ("comm", 1)):
            lit_rows = [(lb, side) for lb in C.LB for side in ("hi", "lo") if self.rows[g, lb, side][0][i]]
            sides = {s for _, s in lit_rows}
            if not lit_rows or len(sides) > 1:
                continue
            ok = False
            for lb, side in lit_rows:
                lit, cases = self.rows[g, lb, side]
                j = i
                while j > 0 and lit[j - 1]:
                    j -= 1
                t0 = self.dates[i] - pd.DateOffset(years=C.HIST[lb])
                for h in HORIZONS:
                    r = [c[h][0] for c in cases if c["i"] < j and c["d"] >= t0 and c[h] and c[h][1] <= t]
                    if len(r) >= C.BAR_N and np.mean([x > 0 for x in r]) >= C.BAR_WIN / 100 and np.mean(r) > 0:
                        ok = True
                        good.append({"group": g, "lb": lb, "h": h, "n": len(r), "w": int(sum(x > 0 for x in r)),
                                     "avg": round(100 * float(np.mean(r)), 2)})
            if not ok:
                continue
            s = next(iter(sides))
            dirs[g] = "BULLISH" if follow * (1 if s == "hi" else -1) > 0 else "BEARISH"
        v = None if not dirs or len(set(dirs.values())) > 1 else next(iter(dirs.values()))
        return (v, good if v else []) if detail else v
