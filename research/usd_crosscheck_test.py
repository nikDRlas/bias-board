#!/usr/bin/env python3
"""Currencies against the dollar: does the Dollar Index's own bias matter for a currency verdict?

Every currency future is quoted in USD, so long CHF = short USD. For every currency verdict of the walk-forward test
(research/verdict_test.py trades, data known on that Saturday) the Dollar Index's verdict on the same Saturday is
rebuilt the same way (no position limit for DX, it is only read) and the trade is labelled:
  confirms   DX points the other way (currency bullish while DX bearish): both say the same about the dollar
  clashes    DX points the same way (both bullish): they contradict each other
  DX none    DX has no bias
Also split by engine: the DX COT read alone and the DX seasonal driver alone.
Output: data/research/usd_crosscheck.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
import verdict as VD                                   # noqa: E402

FX = [k for k in C.M if C.M[k][3] == "FX" and k != "DX"]


def dx_weekly():
    p, rd = C.load_px("DX"), C.CotReader("DX")
    cal, sp = SS.Calendar(p), C.speed_series("DX")
    lit = C.lit_sides(rd, sp)
    out = {}
    for t in pd.date_range("2019-01-05", C.TODAY, freq="W-SAT"):
        ws, status = cal.windows(t)
        seas = ("BULLISH" if ws[0]["side"] == "BUY" else "BEARISH") if status == "driver" else None
        i = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
        cot = lit[i] or "NEUTRAL"
        ag = cal.past(t.year, ws[0], rd)["summary"]["against"] if seas and cot in VD.SIDES and cot != seas else None
        v, basis = VD.decide(cot, seas, ag)
        out[str(t.date())] = {"verdict": v if v in VD.SIDES else None, "cot": lit[i], "seas": seas}
    return out


def lab(cur, dx):
    if dx is None:
        return "DX none"
    return "clashes" if dx == cur else "confirms"


def st(g):
    if len(g) < 3:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "t": round(float(g.r.mean() / g.r.std(ddof=1) * np.sqrt(len(g))), 2)}


if __name__ == "__main__":
    DX = dx_weekly()
    T = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
    T = T[T.m.isin(FX)].copy()
    for col in ("verdict", "cot", "seas"):
        T["dx_" + col] = [lab(v, DX.get(t, {}).get(col)) for t, v in zip(T.t, T.v)]
    res = {}
    for col in ("dx_verdict", "dx_cot", "dx_seas"):
        res[col] = {}
        for key, g in T.groupby(col):
            res[col][key] = {"all": st(g), "2019-22": st(g[g.t < "2023"]), "2023-26": st(g[g.t >= "2023"]),
                             "by_basis": {b: st(gg) for b, gg in g.groupby("basis")},
                             "by_market": {m: st(gg) for m, gg in g.groupby("m")}}
    res["all"] = st(T)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "usd_crosscheck.json"), "w"), indent=1)
    f = lambda o: f"{o['win']:5.1f}% avg {o['avg']:+.2f}% t {o['t']:+.2f} n{o['n']:3d}" if o else "-"
    print("all currency verdicts", f(res["all"]))
    for col, nm in (("dx_verdict", "DX board verdict"), ("dx_cot", "DX COT read"), ("dx_seas", "DX seasonal")):
        print(f"\n{nm}")
        for key, v in res[col].items():
            print(f"  {key:9s} {f(v['all'])} | 19-22 {f(v['2019-22'])} | 23-26 {f(v['2023-26'])}")
            print("            ", {b: (o["win"], o["avg"], o["n"]) for b, o in v["by_basis"].items() if o})
            print("            ", {m: (o["win"], o["avg"], o["n"]) for m, o in v["by_market"].items() if o})
