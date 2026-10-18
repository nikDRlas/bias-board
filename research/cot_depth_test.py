#!/usr/bin/env python3
"""Does COT get better the deeper the extreme? (a) board signals grouped by how deep the commercials sat in their
extreme at the start; (b) all signals rebuilt with the extreme bar at 80 (board), 85, 90 or 95.

Board signal (commercials at an extreme on >= 2 of 5 lookbacks, retail or funds opposite, funds not on their side,
slow signals skipped, bearish index signals skipped), one trade per lit run, entry at the first close after the
release, held while lit + 1 week. Depth = the commercials' most extreme percentile over the lookbacks on the start
report (for a short extreme 100 - percentile). Results in % in the signal's direction, and against the market's own
drift (same length, same direction, prior 10 years). Output: data/research/cot_depth.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402


def setups(k, p, lc):
    rd = C.CotReader(k)
    lit = C.lit_sides(rd, C.speed_series(k))
    out = []
    for i in range(len(rd.dates)):
        v = lit[i]
        if not v or (i and lit[i - 1] == v):
            continue
        ex = C.cot_exit(rd.dates, lit, i)
        rel = rd.dates[i] + pd.Timedelta(days=3)
        if ex is None or rel < p.index[0]:
            continue
        a, b = p.index.searchsorted(rel), p.index.searchsorted(ex)
        if b >= len(p) or b <= a or a < 300:
            continue
        sg = 1 if v == "BULLISH" else -1
        pc = [rd.P["comm"][lb][i] for lb in C.LB]
        ext = [x if sg > 0 else 100 - x for x in pc if np.isfinite(x)]
        L = b - a
        lo = max(0, a - 2520)
        base = 100 * (np.exp(sg * (lc[lo + L:a] - lc[lo:a - L])) - 1).mean()
        out.append({"m": k, "sector": C.M[k][3], "d": str(rd.dates[i].date()), "depth": max(ext),
                    "n_lit": int(sum(e >= C.HI for e in ext)), "days": int(L),
                    "r": 100 * (np.exp(sg * (lc[b] - lc[a])) - 1), "base": float(base)})
    return out


def st(g):
    if len(g) < 8:
        return None
    ex = g.r - g.base
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "vs_drift": round(float(ex.mean()), 2), "vs_drift_t": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(g))), 2),
            "per_week": round(float(g.r.sum() / (g.days.sum() / 5)), 3),
            "2003-15": round(float(g[g.d < "2016"].r.mean()), 2) if (g.d < "2016").sum() else None,
            "2016-26": round(float(g[g.d >= "2016"].r.mean()), 2) if (g.d >= "2016").sum() else None}


if __name__ == "__main__":
    px = {k: C.load_px(k) for k in C.M}
    res = {}
    for bar in (80, 85, 90, 95):
        C.HI, C.LO = float(bar), float(100 - bar)
        rows = []
        for k in C.M:
            p = px[k]
            rows += setups(k, p, np.log(p.to_numpy(float)))
        df = pd.DataFrame(rows)
        res[f"bar {bar}"] = {"all": st(df), "by_sector": {s: st(g) for s, g in df.groupby("sector")}}
        if bar == 80:
            res["depth at start (bar 80)"] = {lab: st(df[(df.depth >= lo) & (df.depth < hi)]) for lab, lo, hi in
                                              (("80-85", 80, 85), ("85-90", 85, 90), ("90-95", 90, 95), ("95-100", 95, 101))}
            res["lookbacks lit at start (bar 80)"] = {str(n): st(df[df.n_lit == n]) for n in (2, 3, 4, 5)}
        print(bar, len(df), flush=True)
    C.HI, C.LO = 80.0, 20.0
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "cot_depth.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:4d} won {o['win']:4.1f}% avg {o['avg']:+.2f}% vs drift {o['vs_drift']:+.2f}% (t {o['vs_drift_t']:+.1f}) per wk {o['per_week']:+.3f}% | 03-15 {o['2003-15']:+.2f} 16-26 {o['2016-26']:+.2f}" if o else "-"
    for key in ("depth at start (bar 80)", "lookbacks lit at start (bar 80)"):
        print(f"\n{key}")
        for lab, o in res[key].items():
            print(f"   {lab:7s} {f(o)}")
    print("\nextreme bar")
    for bar in (80, 85, 90, 95):
        print(f"   {bar}  {f(res[f'bar {bar}']['all'])}")
