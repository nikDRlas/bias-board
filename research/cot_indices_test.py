#!/usr/bin/env python3
"""Does the board's COT signal have an edge on the US indices (ES, NQ, YM)?

Board signal (slow signals skipped), one trade per lit run, entry at the first close after the release, held while lit
+ 1 week (core.cot_exit). Each trade is compared with the index's own drift: the average return of holding the same
number of trading days in the same direction from every day of the prior 10 years (known at entry).
Output: data/research/cot_indices.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402


def st(g):
    if len(g) < 3:
        return None
    ex = g.r - g.base
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "t": round(float(g.r.mean() / g.r.std(ddof=1) * np.sqrt(len(g))), 2),
            "excess": round(float(ex.mean()), 2), "excess_t": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(g))), 2),
            "weeks": round(float(g.days.mean() / 5), 1)}


if __name__ == "__main__":
    rows = []
    for k in ("ES", "NQ", "YM"):
        p, rd = C.load_px(k), C.CotReader(k)
        lc = np.log(p.to_numpy(float))
        lit = C.lit_sides(rd, C.speed_series(k))
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
            L = b - a
            lo = max(0, a - 2520)
            base = 100 * (np.exp(sg * (lc[lo + L:a] - lc[lo:a - L])) - 1).mean()
            rows.append({"m": k, "d": str(rd.dates[i].date()), "side": v, "days": int(L),
                         "r": 100 * (np.exp(sg * (lc[b] - lc[a])) - 1), "base": float(base)})
    df = pd.DataFrame(rows)
    res = {}
    for nm, g in (("all", df), ("long", df[df.side == "BULLISH"]), ("short", df[df.side == "BEARISH"])):
        res[nm] = {"all": st(g), "2003-15": st(g[g.d < "2016"]), "2016-26": st(g[g.d >= "2016"]),
                   "by_market": {m: st(x) for m, x in g.groupby("m")}}
    json.dump({**res, "trades": rows}, open(os.path.join(HERE, "..", "data", "research", "cot_indices.json"), "w"), indent=1, default=float)
    f = lambda o: f"{o['win']:5.1f}% avg {o['avg']:+.2f}% t {o['t']:+.2f} | vs drift {o['excess']:+.2f}% t {o['excess_t']:+.2f} | {o['weeks']}wk n{o['n']}" if o else "-"
    for nm, v in res.items():
        print(f"{nm.upper():6s} all     {f(v['all'])}")
        print(f"{'':6s} 2003-15 {f(v['2003-15'])}")
        print(f"{'':6s} 2016-26 {f(v['2016-26'])}")
        for m, o in v["by_market"].items():
            print(f"{'':6s} {m:7s} {f(o)}")
