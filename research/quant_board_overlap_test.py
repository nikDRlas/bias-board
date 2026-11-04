#!/usr/bin/env python3
"""Quant strategies x the board's own verdict (2026-11-04): when a quant play (bias/events.py) runs on a market where the
board has a verdict, does the verdict change what the quant play earns?

Every quant occurrence 2019-26 (entry and exit at the close, as on the Quant page) is classed by the board's verdict on
that market at the quant entry, from the walk-forward replay (data/research/verdict.json, only what was known then):
  agrees    a board verdict in the quant play's direction was running
  against   a board verdict the other way was running
  none      no board verdict running (stand aside)
Output: data/research/quant_board_overlap.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import events as EV                                    # noqa: E402

V = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
for c in ("entry", "exit"):
    V[c] = pd.to_datetime(V[c])
END = V.exit.max()


def stats(r):
    r = np.asarray(r, float)
    if not len(r):
        return None
    return {"n": len(r), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "t": round(float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))), 2) if len(r) > 2 and r.std() > 0 else None}


rows = []
for kind, ks in EV.MARKETS.items():
    sg = 1 if EV.SIDE.get(kind, "BUY") == "BUY" else -1
    for k in ks:
        p = C.load_px(k)
        v = V[V.m == k]
        for a, b in EV.occurrences(p, kind, END):
            if a < pd.Timestamp("2019-01-07") or b > END or a not in p.index or b not in p.index:
                continue
            run = v[(v.entry <= a) & (v.exit > a)]
            if len(run):
                cls = "agrees" if (1 if run.iloc[-1].v == "BULLISH" else -1) == sg else "against"
            else:
                cls = "none"
            rows.append({"kind": kind, "m": k, "t": a, "cls": cls, "basis": run.iloc[-1].basis if len(run) else None,
                         "r": 100 * sg * (p.loc[b] / p.loc[a] - 1)})
T = pd.DataFrame(rows)
T["h"] = np.where(T.t < "2023", "2019-22", "2023-26")

out = {}
for kind, g in T.groupby("kind", sort=False):
    out[kind] = {cls: {"all": stats(x.r), **{h: stats(y.r) for h, y in x.groupby("h")}} for cls, x in g.groupby("cls")}
out["pooled"] = {cls: {"all": stats(x.r), **{h: stats(y.r) for h, y in x.groupby("h")}} for cls, x in T.groupby("cls")}
json.dump(out, open(os.path.join(HERE, "..", "data", "research", "quant_board_overlap.json"), "w"), indent=1)

for kind, d in out.items():
    print(f"\n{kind}")
    for cls in ("agrees", "none", "against"):
        if cls in d:
            x = d[cls]
            f = lambda s: f"n{s['n']:3d} {s['win']:5.1f}% {s['avg']:+6.2f}% t{s['t']}" if s else "-"
            print(f"  {cls:8s} {f(x['all']):32s} | 19-22 {f(x.get('2019-22')):30s} | 23-26 {f(x.get('2023-26'))}")

# drift control: the same number of trading days at the average daily move of that market on ALL days of the same class
# (board long running / no board verdict), 2019-26 -> does the quant window beat just being in the market then?
ctl = []
for k in sorted(T.m.unique()):
    p = C.load_px(k)
    p = p[(p.index >= "2019-01-07") & (p.index <= END)]
    dr = np.log(p).diff().dropna()
    v = V[V.m == k]
    lab = pd.Series("none", index=dr.index)
    for r in v.itertuples():
        lab[(dr.index > r.entry) & (dr.index <= r.exit)] = "BULLISH" if r.v == "BULLISH" else "BEARISH"
    for r in T[T.m == k].itertuples():
        sg = 1 if EV.SIDE.get(r.kind, "BUY") == "BUY" else -1
        a = dr.index.searchsorted(r.t, "right")
        occ = [o for o in EV.occurrences(C.load_px(k), r.kind, END) if o[0] == r.t][0]
        n = int(dr.index.searchsorted(occ[1], "right") - a)
        cls_lab = {"agrees": "BULLISH" if sg > 0 else "BEARISH", "against": "BEARISH" if sg > 0 else "BULLISH", "none": "none"}[r.cls]
        mu = dr[lab == cls_lab].mean()
        ctl.append({**r._asdict(), "excess": r.r - 100 * sg * (np.exp(mu * n) - 1)})
X = pd.DataFrame(ctl)
print("\nexcess over the same days' drift in that class (quant minus average move of the class x days)")
for kind, g in list(X.groupby("kind", sort=False)) + [("pooled", X)]:
    for cls, x in g.groupby("cls"):
        e, l = x[x.h == "2019-22"].excess, x[x.h == "2023-26"].excess
        print(f"  {kind:12s} {cls:8s} n{len(x):3d} excess {x.excess.mean():+6.2f}% t{x.excess.mean()/x.excess.std(ddof=1)*np.sqrt(len(x)) if len(x)>2 else float('nan'):5.2f}"
              f" | 19-22 {e.mean():+6.2f} | 23-26 {l.mean():+6.2f}")
out["excess"] = {f"{kind}|{cls}": stats(x.excess) for kind, g in list(X.groupby("kind", sort=False)) + [("pooled", X)] for cls, x in g.groupby("cls")}
json.dump(out, open(os.path.join(HERE, "..", "data", "research", "quant_board_overlap.json"), "w"), indent=1)
