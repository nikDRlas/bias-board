#!/usr/bin/env python3
"""The macro grid (research/macro_grid.py) on the other markets: currencies (own-country score and pair score =
own minus US per slot, clipped +-2; dollar index = US vs euro area) and the other commodities (crude, copper,
natural gas, platinum: the US score with inflation inverted, as the replica scores them). Rate window 20 days.
Holds 1, 2, 4, 6, 8, 12 weeks, every Saturday 2016 - Sep 2026. Output: data/research/macro_grid_other.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
import verdict as VD                                   # noqa: E402
import macro as MC                                     # noqa: E402
from macro_grid import st, HOLDS, END                  # noqa: E402
from macro_pair_test import slots, PAIRS               # noqa: E402

if __name__ == "__main__":
    cal = MC.load_calendar()
    days = pd.date_range("2015-06-01", END)
    S = {c: slots(cal, c, days) for c in ("USD", "EUR", "GBP", "JPY", "AUD", "CAD")}
    scores = {}
    for k, (own, quote) in PAIRS.items():
        scores[k] = {"own country": S[own].sum(axis=1) if k != "DX" else S["USD"].sum(axis=1),
                     "pair": (S[own] - S[quote]).clip(-2, 2).sum(axis=1)}
    for k in ("CL", "HG", "NG", "PL"):
        scores[k] = {"US score": MC.market_scores(cal, k, days)["total"]}
    group = lambda k: "Currencies" if k in PAIRS else "Other commodities"
    pts = []
    for k, sc in scores.items():
        p = C.load_px(k)
        lc = np.log(p.to_numpy(float))
        rd = C.CotReader(k)
        lit = C.lit_sides(rd, C.speed_series(k))
        cl = SS.Calendar(p)
        for t in pd.date_range("2016-01-02", END - pd.Timedelta(weeks=13), freq="W-SAT"):
            a = p.index.searchsorted(t)
            if a < 300:
                continue
            i = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
            v = lit[i] if i >= 0 else None
            cot = v if v and C.cot_big_enough(k, v, t) else None
            ws, status = cl.windows(t)
            seas = ("BULLISH" if ws[0]["side"] == "BUY" else "BEARISH") if status == "driver" else None
            vb, _, _ = VD.board_read(cot or "NEUTRAL", cl, t, rd)
            ms = {n: int(np.sign(s[s.index <= t].iloc[-1])) for n, s in sc.items()}
            dv = np.diff(lc[max(0, a - 253):a]).std()
            for h in HOLDS:
                b = p.index.searchsorted(t + pd.Timedelta(weeks=h))
                if b >= len(p):
                    continue
                L, lo = b - a, max(0, a - 2520)
                drift = float((lc[lo + L:a] - lc[lo:a - L]).mean())
                seg = lc[a:b + 1] - lc[a]
                for n, m in ms.items():
                    for tool, side in (("Macro alone", None), ("COT", cot), ("Calendar", seas), ("Board verdict", vb)):
                        if tool == "Macro alone":
                            sg, lab = m, "followed"
                        else:
                            sg = {"BULLISH": 1, "BEARISH": -1}.get(side, 0)
                            lab = "flat" if m == 0 else ("agrees" if m == sg else "against")
                        if not sg or lab == "flat":
                            continue
                        pts.append({"grp": f"{group(k)} · {n}", "tool": tool, "lab": lab, "h": h, "d": str(t.date()),
                                    "r": 100 * (np.exp(sg * seg[-1]) - 1), "base": 100 * (np.exp(sg * drift) - 1),
                                    "mae": float((sg * seg).min() / (dv * np.sqrt(L)))})
        print(k, flush=True)
    df = pd.DataFrame(pts)
    res = {}
    for (grp, tool, lab, h), g in df.groupby(["grp", "tool", "lab", "h"]):
        res.setdefault(grp, {}).setdefault(tool, {}).setdefault(lab, {})[f"{h}w"] = st(g, h)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "macro_grid_other.json"), "w"), indent=1)
    for grp, v in res.items():
        print(f"\n######## {grp}")
        for tool, w in v.items():
            for lab, cells in w.items():
                print(f"  {tool:13s} {lab:9s} " + " | ".join(f"{h}: {o['vs_drift']:+.2f} t{o['t']:+.1f} w{o['win']:.0f} mae{o['mae_z']:+.2f}" if o else f"{h}: -" for h, o in cells.items()))
