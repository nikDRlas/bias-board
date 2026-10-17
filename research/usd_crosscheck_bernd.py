#!/usr/bin/env python3
"""Currencies against the dollar, counted the way Bernd counts (in-sample, no walk-forward).

Cases: his rule. For each currency, group (commercials followed, retail faded) and lookback (6 mo .. multi-yr), a case is
the week the group reaches an extreme (>= 80 / <= 20) after it was last at the opposite extreme. Result: from the close
of the report Tuesday to the close 4 / 8 / 13 weeks later, in the direction of the signal. All cases since prices start
(2003), and separately only within his history spans (5/5/8/12/15 years back from today).
Each case is labelled by the dollar index on the same report:
  same group + same lookback   DX at the opposite extreme to the currency's group (confirms), same extreme (clashes), none
  board read                   DX's own COT read (>= 2 of 5 lookbacks) opposite / same / none
Output: data/research/usd_crosscheck_bernd.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

FX = [k for k in C.M if C.M[k][3] == "FX" and k != "DX"]
H = (4, 8, 13)


def fwd(p, d, h):
    i, j = p.index.searchsorted(d), p.index.searchsorted(d + pd.Timedelta(weeks=h))
    return float(p.iloc[j] / p.iloc[i] - 1) if j < len(p) and i < len(p) else np.nan


def onsets(P):
    v = P.to_numpy()
    out = []
    for side in ("hi", "lo"):
        lit = v >= C.HI if side == "hi" else v <= C.LO
        opp = v <= C.LO if side == "hi" else v >= C.HI
        armed = True
        for i in range(len(v)):
            if lit[i] and not (i and lit[i - 1]):
                if armed:
                    out.append((i, side))
                    armed = False
            elif opp[i]:
                armed = True
    return out


if __name__ == "__main__":
    dx = C.load_cot("DX")
    dxP = {g: {lb: C.pctile(dx[g], L) for lb, L in C.LB.items()} for g in ("comm", "retail")}
    dxr = C.CotReader("DX")
    rows = []
    for k in FX:
        p, x = C.load_px(k), C.load_cot(k)
        for g, follow in (("comm", 1), ("retail", -1)):
            for lb, L in C.LB.items():
                P = C.pctile(x[g], L)
                for i, side in onsets(P):
                    d = x.index[i]
                    if d < p.index[0]:
                        continue
                    sg = follow * (1 if side == "hi" else -1)          # +1 = currency bullish (USD bearish)
                    # DX same group, same lookback, same Tuesday
                    j = dx.index.searchsorted(d, "right") - 1
                    dv = float(dxP[g][lb].iloc[j]) if j >= 0 else np.nan
                    dside = "hi" if dv >= C.HI else "lo" if dv <= C.LO else None
                    dsg = follow * (1 if dside == "hi" else -1) if dside else 0   # +1 = USD bullish
                    lab_same = "DX none" if not dsg else ("confirms" if dsg == -sg else "clashes")
                    rd = dxr.read_at(j) if j >= 0 else "NEUTRAL"
                    rsg = 1 if rd == "BULLISH" else -1 if rd == "BEARISH" else 0
                    lab_read = "DX none" if not rsg else ("confirms" if rsg == -sg else "clashes")
                    rec = {"m": k, "g": g, "lb": lb, "d": str(d.date()), "same": lab_same, "read": lab_read,
                           "in_span": d >= C.TODAY - pd.DateOffset(years=C.HIST[lb])}
                    for h in H:
                        rec[f"r{h}"] = 100 * sg * fwd(p, d, h)
                    rows.append(rec)
    df = pd.DataFrame(rows)

    def st(g, h):
        r = g[f"r{h}"].dropna()
        return {"n": len(r), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2)} if len(r) >= 3 else None
    res = {}
    for scope, D in (("since 2003", df), ("Bernd history spans", df[df.in_span])):
        res[scope] = {}
        for lab in ("same", "read"):
            res[scope][lab] = {c: {f"{h}w": st(g, h) for h in H} for c, g in D.groupby(lab)}
            res[scope][lab + "_by_group"] = {f"{gr} · {c}": {f"{h}w": st(g, h) for h in H} for (gr, c), g in D.groupby(["g", lab])}
            res[scope][lab + "_by_market"] = {f"{m} · {c}": st(g, 8) for (m, c), g in D.groupby(["m", lab])}
        res[scope]["all"] = {f"{h}w": st(D, h) for h in H}
    json.dump({**res, "cases": rows}, open(os.path.join(HERE, "..", "data", "research", "usd_crosscheck_bernd.json"), "w"), indent=1, default=str)
    f = lambda o: f"{o['win']:5.1f}% {o['avg']:+.2f}% n{o['n']:4d}" if o else "-"
    for scope, v in res.items():
        print(f"\n=== {scope} · all cases: " + " | ".join(f"{h} {f(o)}" for h, o in v["all"].items()))
        for lab, nm in (("same", "DX same group + lookback"), ("read", "DX board COT read")):
            print(f"  {nm}")
            for c, o in v[lab].items():
                print(f"    {c:9s} " + " | ".join(f"{h} {f(x)}" for h, x in o.items()))
            for c, o in v[lab + "_by_group"].items():
                print(f"      {c:22s} " + " | ".join(f"{h} {f(x)}" for h, x in o.items()))
        print("  by market, 8w, DX same group+lookback:")
        print("   ", "  ".join(f"{c}: {o['win']}%/{o['avg']:+.2f}/n{o['n']}" for c, o in v["same_by_market"].items() if o))
