#!/usr/bin/env python3
"""Each tool as a pure direction, on one footing: the 17 markets with macro and yield data, every 4th Saturday
2016 - Sep 2026 (non-overlapping), 4-week hold from the next close, in the tool's direction. Only data known that
Saturday. Against the market's own drift (same length, same direction, prior 10 years).
  COT        the board's COT signal (slow skipped, bearish index skipped, COT minimum 0.5)
  Calendar   the seasonal driver window (any size)
  Macro      sign of the EdgeFinder-replica macro_score (and of our LSE rebuild)
  Macro ext  macro at its 3-year 80/20 extreme, followed / faded
  Yields     20-day move of the 2-year yield signal, followed / faded
  Board      the board's verdict
Output: data/research/tools_direction.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
import verdict as VD                                   # noqa: E402
import macro as MC                                     # noqa: E402
from yields_filter_test import signal as ysignal       # noqa: E402
from macro_filter_test import MAP as RMAP, SRC         # noqa: E402

END = pd.Timestamp("2026-09-10")


def st(g):
    if len(g) < 10:
        return None
    ex = g.r - g.base
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "vs_drift": round(float(ex.mean()), 2), "t": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(g))), 2),
            "2016-20": round(float(ex[g.d < "2021"].mean()), 2), "2021-26": round(float(ex[g.d >= "2021"].mean()), 2)}


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
        rmac = rep[rep.symbol == RMAP[k]].set_index("date").macro_score
        omac = MC.market_scores(cal, k, days)["total"] if k in MC.MARKET else None
        ys = ysignal(k)
        ych = (ys - ys.shift(20)).dropna()
        for t in pd.date_range("2016-01-02", END - pd.Timedelta(weeks=5), freq="4W-SAT"):
            a = p.index.searchsorted(t)
            b = p.index.searchsorted(t + pd.Timedelta(weeks=4))
            if b >= len(p) or a < 300:
                continue
            L = b - a
            lo = max(0, a - 2520)
            move = lc[b] - lc[a]
            drift = float((lc[lo + L:a] - lc[lo:a - L]).mean())
            def add(tool, sg):
                if sg:
                    rows.append({"tool": tool, "m": k, "d": str(t.date()), "r": 100 * (np.exp(sg * move) - 1),
                                 "base": 100 * (np.exp(sg * drift) - 1)})
            i = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
            v = lit[i] if i >= 0 else None
            cot = v if v and C.cot_big_enough(k, v, t) else None
            add("COT", {"BULLISH": 1, "BEARISH": -1}.get(cot, 0))
            ws, status = cl.windows(t)
            seas = ("BULLISH" if ws[0]["side"] == "BUY" else "BEARISH") if status == "driver" else None
            add("Calendar", {"BULLISH": 1, "BEARISH": -1}.get(seas, 0))
            vb, basis, _ = VD.board_read(cot or "NEUTRAL", cl, t, rd)
            add("Board verdict", {"BULLISH": 1, "BEARISH": -1}.get(vb, 0))
            h = rmac[rmac.index <= t]
            if len(h) > 400:
                add("Macro (replica), followed", int(np.sign(h.iloc[-1])))
                hh = h[h.index > t - pd.DateOffset(years=3)]
                pc = 100 * float((hh.iloc[:-1] < hh.iloc[-1]).mean())
                ext = 1 if pc >= 80 else -1 if pc <= 20 else 0
                add("Macro extreme (replica), followed", ext)
                add("Macro extreme (replica), faded", -ext)
            if omac is not None:
                o = omac[omac.index <= t]
                add("Macro (LSE rebuild), followed", int(np.sign(o.iloc[-1])))
            yc = ych[ych.index <= t]
            if len(yc) > 300:
                add("Yields 20d, followed", int(np.sign(yc.iloc[-1])))
                add("Yields 20d, faded", -int(np.sign(yc.iloc[-1])))
        print(k, flush=True)
    df = pd.DataFrame(rows)
    res = {tool: {"all": st(g), **{s: st(g[g.m.map(lambda k: C.M[k][3]) == s]) for s in ("FX", "Indices", "Metals", "Energy")}}
           for tool, g in df.groupby("tool")}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "tools_direction.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:4d} won {o['win']:4.1f}% avg {o['avg']:+.2f}% vs drift {o['vs_drift']:+.2f}% (t {o['t']:+.1f}) | 16-20 {o['2016-20']:+.2f} 21-26 {o['2021-26']:+.2f}" if o else "-"
    for tool in sorted(res, key=lambda x: -(res[x]["all"] or {"t": -9})["t"]):
        print(f"{tool:36s} {f(res[tool]['all'])}")
        print(f"{'':36s} " + " | ".join(f"{s} {o['vs_drift']:+.2f} (t {o['t']:+.1f})" for s, o in res[tool].items() if s != "all" and o))
