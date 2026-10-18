#!/usr/bin/env python3
"""COT and calendar (and the board verdict) split by whether the macro score agreed with them, on the footing of
research/tools_direction_compare.py (17 markets, every 4th Saturday 2016 - Sep 2026, 4-week hold, vs drift).
Macro = sign of the LSE rebuild's total score (bias/macro.py); the replica's as a check.
Output: data/research/tools_macro_align.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
import verdict as VD                                   # noqa: E402
import macro as MC                                     # noqa: E402
from macro_filter_test import MAP as RMAP, SRC         # noqa: E402

END = pd.Timestamp("2026-09-10")
US_DRIVEN = {"ES", "NQ", "YM", "GC", "SI"}


def st(g):
    if len(g) < 10:
        return None
    ex = g.r - g.base
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "vs_drift": round(float(ex.mean()), 2), "t": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(g))), 2),
            "2016-20": round(float(ex[g.d < "2021"].mean()), 2) if (g.d < "2021").sum() else None,
            "2021-26": round(float(ex[g.d >= "2021"].mean()), 2) if (g.d >= "2021").sum() else None}


if __name__ == "__main__":
    rep = pd.read_csv(SRC, parse_dates=["date"])
    cal = MC.load_calendar()
    days = pd.date_range("2015-06-01", END)
    rows = []
    for k in RMAP:
        p = C.load_px(k)
        lc = np.log(p.to_numpy(float))
        rd = C.CotReader(k)
        lit = C.lit_sides(rd, C.speed_series(k))
        cl = SS.Calendar(p)
        om = MC.market_scores(cal, k, days)["total"]
        rm = rep[rep.symbol == RMAP[k]].set_index("date").macro_score
        for t in pd.date_range("2016-01-02", END - pd.Timedelta(weeks=5), freq="4W-SAT"):
            a, b = p.index.searchsorted(t), p.index.searchsorted(t + pd.Timedelta(weeks=4))
            if b >= len(p) or a < 300:
                continue
            L, lo = b - a, max(0, a - 2520)
            move, drift = lc[b] - lc[a], float((lc[lo + L:a] - lc[lo:a - L]).mean())
            mo = int(np.sign(om[om.index <= t].iloc[-1]))
            hr = rm[rm.index <= t]
            mr = int(np.sign(hr.iloc[-1])) if len(hr) else 0
            lab = lambda m, sg: "macro flat" if m == 0 else ("macro agrees" if m == sg else "macro against")
            def add(tool, sg):
                if sg:
                    rows.append({"tool": tool, "m": k, "d": str(t.date()), "r": 100 * (np.exp(sg * move) - 1),
                                 "base": 100 * (np.exp(sg * drift) - 1), "lse": lab(mo, sg), "rep": lab(mr, sg),
                                 "us": k in US_DRIVEN})
            i = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
            v = lit[i] if i >= 0 else None
            cot = v if v and C.cot_big_enough(k, v, t) else None
            add("COT", {"BULLISH": 1, "BEARISH": -1}.get(cot, 0))
            ws, status = cl.windows(t)
            seas = ("BULLISH" if ws[0]["side"] == "BUY" else "BEARISH") if status == "driver" else None
            add("Calendar", {"BULLISH": 1, "BEARISH": -1}.get(seas, 0))
            vb, _, _ = VD.board_read(cot or "NEUTRAL", cl, t, rd)
            add("Board verdict", {"BULLISH": 1, "BEARISH": -1}.get(vb, 0))
        print(k, flush=True)
    df = pd.DataFrame(rows)
    res = {}
    for tool, g in df.groupby("tool"):
        res[tool] = {"all markets": {k: st(x) for k, x in g.groupby("lse")},
                     "US indices + gold/silver": {k: st(x) for k, x in g[g.us].groupby("lse")},
                     "other markets": {k: st(x) for k, x in g[~g.us].groupby("lse")},
                     "replica, all markets": {k: st(x) for k, x in g.groupby("rep")}}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "tools_macro_align.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:4d} won {o['win']:4.1f}% vs drift {o['vs_drift']:+.2f}% (t {o['t']:+.1f}) | 16-20 {o['2016-20']:+.2f} 21-26 {o['2021-26']:+.2f}" if o else "-"
    for tool, v in res.items():
        print(f"\n=== {tool}")
        for scope, d in v.items():
            print(f"  {scope}")
            for k, o in d.items():
                print(f"     {k:14s} {f(o)}")
