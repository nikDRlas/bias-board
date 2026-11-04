"""Currency pairs from the board's currency verdicts: one currency bullish and another bearish = one cross in the
direction of both (e.g. GBP bullish + CHF bearish = long GBP/CHF). The same two board trades in one position, with the
US dollar cancelled out. Pairs with the dollar are left out (they are the board's own currency trades).
Tested (run this file): every such pair in the walk-forward replay 2019-26 (data/research/verdict.json), entered when
the second verdict starts, held while both last; against the board's own currency trades vs USD.
Output: data/research/fx_cross_pairs.json"""
import json, os
import numpy as np, pandas as pd

import core as C

CUR = {"6E": "EUR", "6B": "GBP", "6A": "AUD", "6N": "NZD", "6C": "CAD", "6S": "CHF", "6J": "JPY"}
ORDER = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]          # market convention: base comes first
OUT = os.path.join(C.ROOT, "data", "research", "fx_cross_pairs.json")


def name(bull, bear):
    """market name and side of the cross for a bullish and a bearish currency"""
    a, b = CUR[bull], CUR[bear]
    return (f"{a}/{b}", "Long") if ORDER.index(a) < ORDER.index(b) else (f"{b}/{a}", "Short")


def current(res):
    """this week's pairs from the board's verdicts (res = {market: {verdict, basis, ...}})"""
    bull = [k for k in CUR if res.get(k, {}).get("verdict") == "BULLISH"]
    bear = [k for k in CUR if res.get(k, {}).get("verdict") == "BEARISH"]
    out = []
    for u in bull:
        for d in bear:
            nm, side = name(u, d)
            out.append({"pair": nm, "side": side, "bull": {"k": u, "cur": CUR[u], "basis": res[u]["basis"]},
                        "bear": {"k": d, "cur": CUR[d], "basis": res[d]["basis"]}})
    return out


def _agg(g):
    if len(g) < 3:
        return None
    per = g.groupby(g.t.dt.to_period("M")).r.mean()
    return {"n": len(g), "months": len(per), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "t": round(float(per.mean() / per.std(ddof=1) * np.sqrt(len(per))), 1),
            "2019-22": round(float(g[g.t < "2023"].r.mean()), 2), "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2)}


def by_pair(g):
    """one cross's own record in the replay: its pair trades (either side), won, average, halves"""
    r = g.r.to_numpy(float)
    half = lambda x: round(float(x.r.mean()), 2) if len(x) else None
    return {"n": len(r), "w": int((r > 0).sum()), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "2019-22": half(g[g.t < "2023"]), "2023-26": half(g[g.t >= "2023"]),
            "trades": [{"entry": x.entry, "exit": x.exit, "side": x.side, "r": round(float(x.r), 2)} for x in g.itertuples()]}


def test(verdict_file):
    v = pd.DataFrame(json.load(open(verdict_file))["trades"])
    v = v[v.m.isin(list(CUR) + ["DX"])].copy()
    for c in ("entry", "exit"):
        v[c] = pd.to_datetime(v[c])
    v["t"] = v["entry"]
    v["sg"] = np.where(v.v == "BULLISH", 1, -1)
    px = pd.DataFrame({k: C.load_px(k) for k in CUR}).dropna()
    rows = []
    for r in v[v.m != "DX"].itertuples():
        for k in CUR:
            if k == r.m:
                continue
            o = v[(v.m == k) & (v.entry <= r.entry) & (v.exit > r.entry)]   # partner already running when r starts
            if not len(o) or o.iloc[-1].sg != -r.sg:
                continue
            t1 = min(r.exit, o.iloc[-1].exit)
            i, j = px.index.searchsorted(r.entry), px.index.searchsorted(t1)
            if j >= len(px) or j <= i:
                continue
            x = (px[r.m] / px[k]).to_numpy()
            nm, side = name(r.m if r.sg > 0 else k, k if r.sg > 0 else r.m)
            rows.append({"t": r.entry, "r": 100 * r.sg * (x[j] / x[i] - 1), "pair": nm, "side": side,
                         "entry": str(px.index[i].date()), "exit": str(px.index[j].date())})
    # both verdicts starting on the same day would find each other as the partner: one pair trade, counted once
    pairs = pd.DataFrame(rows).drop_duplicates(["pair", "entry"]).sort_values("t").reset_index(drop=True)
    own = v.rename(columns={"entry": "t0"}).assign(t=lambda d: d.t0)[["t", "r"]]
    out = {"pairs": _agg(pairs), "vs_usd": _agg(own), "first": str(v.t.min())[:4], "last": str(v.exit.max())[:4],
           "by_pair": {nm: by_pair(g) for nm, g in pairs.groupby("pair")}}
    json.dump(out, open(OUT, "w"), indent=1)
    return out


if __name__ == "__main__":
    print(json.dumps(test(os.path.join(C.ROOT, "data", "research", "verdict.json")), indent=1))
