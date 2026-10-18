#!/usr/bin/env python3
"""Currencies: the macro score as a PAIR (own country minus US, EdgeFinder pair rule) instead of the own country alone.

Pair score = sum over the indicator slots (14 + the rate cell) of clip(own cell - US cell, -2, +2) (missing = 0).
Markets: 6E 6B 6J 6A 6C (own vs US); DX = US vs euro area. CHF / NZD: no calendar history on LSE.
On the footing of research/tools_direction_compare.py (every 4th Saturday 2016 - Sep 2026, 4-week hold, vs drift):
(a) as a direction on its own, own-country score vs pair score; (b) COT / calendar / board verdict split by whether
the pair score agreed. Output: data/research/macro_pair.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
import verdict as VD                                   # noqa: E402
import macro as MC                                     # noqa: E402

END = pd.Timestamp("2026-09-10")
PAIRS = {"6E": ("EUR", "USD"), "6B": ("GBP", "USD"), "6J": ("JPY", "USD"), "6A": ("AUD", "USD"), "6C": ("CAD", "USD"), "DX": ("USD", "EUR")}


def slots(cal, cur, days):
    """per indicator slot: the country's cell (0 where it has none), plus the rate cell"""
    ev = MC.EVENTS.get(cur, {})
    out = {}
    for g, inds in MC.GROUPS.items():
        for ind in inds:
            e = ev.get(ind)
            out[ind] = MC.cell_series(cal, MC.REGION[cur], e, days, ind in MC.INVERT) if e else pd.Series(0.0, index=days)
    out["Rate"] = MC.rate_cell(cur, days)
    return pd.DataFrame(out)


def st(g):
    if len(g) < 10:
        return None
    ex = g.r - g.base
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "vs_drift": round(float(ex.mean()), 2),
            "t": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(g))), 2),
            "2016-20": round(float(ex[g.d < "2021"].mean()), 2) if (g.d < "2021").sum() else None,
            "2021-26": round(float(ex[g.d >= "2021"].mean()), 2) if (g.d >= "2021").sum() else None}


if __name__ == "__main__":
    cal = MC.load_calendar()
    days = pd.date_range("2015-06-01", END)
    S = {c: slots(cal, c, days) for c in ("USD", "EUR", "GBP", "JPY", "AUD", "CAD")}
    rows = []
    for k, (own, quote) in PAIRS.items():
        pair = (S[own] - S[quote]).clip(-2, 2).sum(axis=1)
        single = S[own].sum(axis=1)
        p = C.load_px(k)
        lc = np.log(p.to_numpy(float))
        rd = C.CotReader(k)
        lit = C.lit_sides(rd, C.speed_series(k))
        cl = SS.Calendar(p)
        for t in pd.date_range("2016-01-02", END - pd.Timedelta(weeks=5), freq="4W-SAT"):
            a, b = p.index.searchsorted(t), p.index.searchsorted(t + pd.Timedelta(weeks=4))
            if b >= len(p) or a < 300:
                continue
            L, lo = b - a, max(0, a - 2520)
            move, drift = lc[b] - lc[a], float((lc[lo + L:a] - lc[lo:a - L]).mean())
            mp = int(np.sign(pair[pair.index <= t].iloc[-1]))
            ms = int(np.sign(single[single.index <= t].iloc[-1]))
            def add(tool, sg, lab=None):
                if sg:
                    rows.append({"tool": tool, "m": k, "d": str(t.date()), "r": 100 * (np.exp(sg * move) - 1),
                                 "base": 100 * (np.exp(sg * drift) - 1), "lab": lab})
            add("Macro pair, followed", mp)
            add("Macro own country, followed", ms)
            i = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
            v = lit[i] if i >= 0 else None
            cot = v if v and C.cot_big_enough(k, v, t) else None
            ws, status = cl.windows(t)
            seas = ("BULLISH" if ws[0]["side"] == "BUY" else "BEARISH") if status == "driver" else None
            vb, _, _ = VD.board_read(cot or "NEUTRAL", cl, t, rd)
            for tool, side in (("COT", cot), ("Calendar", seas), ("Board verdict", vb)):
                sg = {"BULLISH": 1, "BEARISH": -1}.get(side, 0)
                add(tool, sg, "pair flat" if mp == 0 else ("pair agrees" if mp == sg else "pair against"))
        print(k, flush=True)
    df = pd.DataFrame(rows)
    df["lab"] = df["lab"].fillna("all")
    res = {t: {k: st(x) for k, x in g.groupby("lab")} for t, g in df.groupby("tool")}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "macro_pair.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:4d} won {o['win']:4.1f}% vs drift {o['vs_drift']:+.2f}% (t {o['t']:+.1f}) | 16-20 {o['2016-20']:+.2f} 21-26 {o['2021-26']:+.2f}" if o else "-"
    for tool, v in res.items():
        print(f"\n{tool}")
        for k, o in v.items():
            print(f"   {k:14s} {f(o)}")
