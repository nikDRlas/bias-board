#!/usr/bin/env python3
"""2-year yields alone against the board's verdicts.

Signal per market (fixed before testing): currencies = change of (own 2-year yield - US 2-year), up = bullish the
currency; dollar index = change of (US 2-year - German 2-year); US indices, crude, copper, natural gas, platinum =
change of the US 2-year, up = bearish; gold and silver the same (up = bearish). Change over 20 trading days (the
replica's rate cell; 60 as a check). Readings: direction (sign of the change) and extreme (change at or above the
80th / at or below the 20th percentile of its own values over the previous 3 years).
Board verdicts from the walk-forward test (current rules), 2019 to 10 Sep 2026 (where the yield table ends).
Output: data/research/yields_filter.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

Y = pd.read_csv(os.path.join(HERE, "..", "data", "macro", "yields_2y_lse.csv"))
Y = {s: pd.Series(g.close.values, index=pd.to_datetime(g.date)).astype(float).groupby(level=0).last().sort_index() for s, g in Y.groupby("symbol")}
OWN = {"6E": "DE2Y", "6B": "UK2Y", "6J": "JP2Y", "6S": "CH2Y", "6A": "AU2Y", "6C": "CA2Y", "6N": "NZ2Y"}


def signal(k):
    """daily series whose rise is bullish for market k"""
    us = Y["US2Y"]
    if k in OWN:
        s = Y[OWN[k]] - us
    elif k == "DX":
        s = us - Y["DE2Y"]
    elif k in ("ES", "NQ", "YM", "CL", "NG", "HG", "PL", "GC", "SI"):
        s = -us
    else:
        return None
    return s.dropna()


def st(g):
    if len(g) < 8:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "end": round(float(g.r.mean()), 2),
            "t": round(float(g.r.mean() / g.r.std(ddof=1) * np.sqrt(len(g))), 2), "mae_z": round(float(g.mae_z.mean()), 2),
            "2019-22": round(float(g[g.t < "2023"].r.mean()), 2) if (g.t < "2023").sum() else None,
            "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2) if (g.t >= "2023").sum() else None}


if __name__ == "__main__":
    T = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
    end = Y["US2Y"].index.max()
    T = T[T.m.map(lambda k: signal(k) is not None) & (pd.to_datetime(T.t) <= end)].copy()
    rows = []
    sig = {k: signal(k) for k in T.m.unique()}
    for _, r in T.iterrows():
        p = C.load_px(r.m)
        a, b = p.index.searchsorted(pd.Timestamp(r.entry)), p.index.searchsorted(pd.Timestamp(r.exit))
        sg = 1 if r.v == "BULLISH" else -1
        seg = 100 * sg * (p.iloc[a:b + 1].to_numpy() / p.iloc[a] - 1)
        vol = 100 * np.diff(np.log(p.iloc[max(0, a - 253):a].to_numpy())).std() * np.sqrt(max(1, b - a))
        o = {**r.to_dict(), "mae_z": float(seg.min() / vol)}
        s = sig[r.m]
        s = s[s.index <= pd.Timestamp(r.t)]
        for n in (20, 60):
            ch = (s - s.shift(n)).dropna()
            if len(ch) < 300:
                o[f"dir{n}"] = o[f"ext{n}"] = "no data"
                continue
            now = ch.iloc[-1]
            o[f"dir{n}"] = "flat" if now == 0 else ("agrees" if np.sign(now) == sg else "against")
            hist = ch[ch.index > ch.index[-1] - pd.DateOffset(years=3)]
            pc = 100 * float((hist.iloc[:-1] < now).mean())
            side = 1 if pc >= 80 else -1 if pc <= 20 else 0
            o[f"ext{n}"] = "not extreme" if side == 0 else ("extreme, agrees" if side == sg else "extreme, against")
        rows.append(o)
    df = pd.DataFrame(rows)
    res = {"all": st(df)}
    for col in ("dir20", "ext20", "dir60", "ext60"):
        res[col] = {k: st(g) for k, g in df.groupby(col)}
        res[col + " by sector"] = {f"{s} · {k}": st(g) for (s, k), g in df.groupby(["sector", col])}
    for col, a, b in (("dir20", "agrees", "against"), ("ext20", "extreme, agrees", "extreme, against"), ("dir60", "agrees", "against"), ("ext60", "extreme, agrees", "extreme, against")):
        x, y = df[df[col] == a].r, df[df[col] == b].r
        res[col + " diff"] = {"agrees_minus_against": round(float(x.mean() - y.mean()), 2), "t": round(float((x.mean() - y.mean()) / np.sqrt(x.var() / len(x) + y.var() / len(y))), 2)}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "yields_filter.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:3d} won {o['win']:4.1f}% end {o['end']:+.2f}% t{o['t']:+.1f} MAE(z) {o['mae_z']:+.2f} | 19-22 {o['2019-22']:+.2f} 23-26 {o['2023-26']:+.2f}" if o else "-"
    print("all", f(res["all"]))
    for col in ("dir20", "ext20", "dir60", "ext60"):
        print(f"\n{col}  ({res[col + ' diff']})")
        for k, o in res[col].items():
            print(f"   {k:17s} {f(o)}")
        if col in ("dir20", "ext20"):
            for k, o in res[col + " by sector"].items():
                if o: print(f"      {k:34s} {f(o)}")
