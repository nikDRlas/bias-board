#!/usr/bin/env python3
"""Grid for the macro work on the US-driven markets (ES NQ YM GC SI), 2016 - Sep 2026, every Saturday.
  hold        1, 2, 4, 6, 8, 12 weeks from the next close
  rate window 10, 20, 40 trading days for the 2-year-yield cell (20 = the replica's)
Rows: macro on its own (followed), and COT / calendar / board verdict split by macro agreeing or against.
Per cell: n, won, mean vs drift, t (divided by sqrt(hold in weeks) for the overlap of weekly starts), MAE (worst
point along the hold in units of a normal move over that length), both halves. Output: data/research/macro_grid.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
import verdict as VD                                   # noqa: E402
import macro as MC                                     # noqa: E402

END = pd.Timestamp("2026-09-10")
HOLDS = (1, 2, 4, 6, 8, 12)
RATES = (10, 20, 40)
MK = ("ES", "NQ", "YM", "GC", "SI")


def st(g, h):
    if len(g) < 15:
        return None
    ex = g.r - g.base
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "vs_drift": round(float(ex.mean()), 2),
            "t": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(g)) / np.sqrt(h)), 2),
            "mae_z": round(float(g.mae.mean()), 2),
            "2016-20": round(float(ex[g.d < "2021"].mean()), 2), "2021-26": round(float(ex[g.d >= "2021"].mean()), 2)}


if __name__ == "__main__":
    cal = MC.load_calendar()
    days = pd.date_range("2015-06-01", END)
    mac = {}
    for rw in RATES:
        MC.RATE_DAYS = rw
        mac[rw] = {k: MC.market_scores(cal, k, days)["total"] for k in MK}
    pts = []
    for k in MK:
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
            ms = {rw: int(np.sign(mac[rw][k][mac[rw][k].index <= t].iloc[-1])) for rw in RATES}
            dv = np.diff(lc[max(0, a - 253):a]).std()
            for h in HOLDS:
                b = p.index.searchsorted(t + pd.Timedelta(weeks=h))
                if b >= len(p):
                    continue
                L, lo = b - a, max(0, a - 2520)
                drift = float((lc[lo + L:a] - lc[lo:a - L]).mean())
                seg = lc[a:b + 1] - lc[a]
                for tool, side in (("Macro alone", None), ("COT", cot), ("Calendar", seas), ("Board verdict", vb)):
                    for rw in RATES:
                        m = ms[rw]
                        if tool == "Macro alone":
                            sg, lab = m, "followed"
                        else:
                            sg = {"BULLISH": 1, "BEARISH": -1}.get(side, 0)
                            lab = "flat" if m == 0 else ("agrees" if m == sg else "against")
                        if not sg or lab == "flat":
                            continue
                        pts.append({"tool": tool, "lab": lab, "h": h, "rw": rw, "m": k, "d": str(t.date()),
                                    "r": 100 * (np.exp(sg * seg[-1]) - 1), "base": 100 * (np.exp(sg * drift) - 1),
                                    "mae": float((sg * seg).min() / (dv * np.sqrt(L)))})
        print(k, flush=True)
    df = pd.DataFrame(pts)
    res = {}
    for (tool, lab, h, rw), g in df.groupby(["tool", "lab", "h", "rw"]):
        res.setdefault(tool, {}).setdefault(lab, {}).setdefault(f"rate {rw}d", {})[f"{h}w"] = st(g, h)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "macro_grid.json"), "w"), indent=1)
    for tool, v in res.items():
        print(f"\n=== {tool}")
        for lab, w in v.items():
            for rk, cells in w.items():
                print(f"  {lab:9s} {rk:9s} " + " | ".join(f"{h}: {o['vs_drift']:+.2f} t{o['t']:+.1f} w{o['win']:.0f} mae{o['mae_z']:+.2f}" if o else f"{h}: -" for h, o in cells.items()))
