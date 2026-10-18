#!/usr/bin/env python3
"""COT at an extreme, then wait for 2-year yields to turn the signal's way before entering?

Board COT signals since 2003 (one per lit run, slow skipped, bearish index signals skipped; with and without the
COT minimum), exit held while lit + 1 week. Yield signal per market as in research/yields_filter_test.py (rise =
bullish for the market), 20-trading-day change. At the signal's entry:
  A  yields already the signal's way              -> enter at the signal (as now)
  B  yields against, then turn the signal's way while the signal is still lit (before its exit)
       B-start: enter at the signal anyway     B-turn: enter at the next close after the turn
  C  yields against and never turn before the exit
Output: data/research/cot_yield_trigger.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
from yields_filter_test import signal                  # noqa: E402


def st(r):
    r = pd.Series(r, dtype=float)
    if len(r) < 8:
        return None
    return {"n": len(r), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "t": round(float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))), 2)}


def run(use_min):
    C.COT_MIN_MOVE = 0.5 if use_min else -99
    out = {"A": [], "B-start": [], "B-turn": [], "C": []}
    dates = {"A": [], "B-start": [], "B-turn": [], "C": []}
    for k in C.M:
        sig = signal(k)
        if sig is None:
            continue
        ch = (sig - sig.shift(20)).dropna()
        p, rd = C.load_px(k), C.CotReader(k)
        px = p.to_numpy(float)
        lit = C.lit_sides(rd, C.speed_series(k))
        for i in range(len(rd.dates)):
            v = lit[i]
            if not v or (i and lit[i - 1] == v):
                continue
            rel = rd.dates[i] + pd.Timedelta(days=3)
            if use_min and not C.cot_big_enough(k, v, rel):
                continue
            ex = C.cot_exit(rd.dates, lit, i)
            if ex is None or rel < p.index[0] or rel < ch.index[0]:
                continue
            a, b = p.index.searchsorted(rel), p.index.searchsorted(ex)
            if b >= len(p) or b <= a:
                continue
            sg = 1 if v == "BULLISH" else -1
            res = lambda j: 100 * sg * (px[b] / px[j] - 1)
            c0 = ch[ch.index <= p.index[a]]
            if not len(c0):
                continue
            yr = str(rd.dates[i].year)
            if np.sign(c0.iloc[-1]) == sg:
                out["A"].append(res(a)); dates["A"].append(yr)
                continue
            path = ch[(ch.index > p.index[a]) & (ch.index < p.index[b])]
            turn = path[np.sign(path) == sg]
            if len(turn):
                j = p.index.searchsorted(turn.index[0]) + 1
                if j < b:
                    out["B-start"].append(res(a)); dates["B-start"].append(yr)
                    out["B-turn"].append(res(j)); dates["B-turn"].append(yr)
                    continue
            out["C"].append(res(a)); dates["C"].append(yr)
    C.COT_MIN_MOVE = 0.5
    rep = {}
    for g in out:
        r = pd.Series(out[g]); y = pd.Series(dates[g])
        rep[g] = {"all": st(r), "2003-15": st(r[y < "2016"]), "2016-26": st(r[y >= "2016"])}
    bs, bt = pd.Series(out["B-start"]), pd.Series(out["B-turn"])
    d = bt - bs
    rep["B: turn minus start (same setups)"] = {"diff": round(float(d.mean()), 2), "t": round(float(d.mean() / d.std(ddof=1) * np.sqrt(len(d))), 2) if len(d) > 2 else None}
    return rep


if __name__ == "__main__":
    res = {"board COT (with the 0.5 minimum)": run(True), "all COT signals": run(False)}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "cot_yield_trigger.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:4d} won {o['win']:4.1f}% avg {o['avg']:+.2f}% t{o['t']:+.1f}" if o else "-"
    for nm, rep in res.items():
        print(f"\n== {nm}")
        for g in ("A", "B-start", "B-turn", "C"):
            v = rep[g]; print(f"   {g:8s} {f(v['all'])} | 2003-15 {f(v['2003-15'])} | 2016-26 {f(v['2016-26'])}")
        print("   ", rep["B: turn minus start (same setups)"])
