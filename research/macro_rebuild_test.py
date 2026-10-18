#!/usr/bin/env python3
"""The macro-extreme test on OUR rebuild (bias/macro.py, LSE calendar) instead of the replica file.

Board verdicts (research/verdict_test.py, current rules) from 2019 to the latest finished verdict, on the markets the
calendar covers back to 2015 (CHF and NZD only from 2026, left out). Extreme = the market's total macro score at or
above the 80th / at or below the 20th percentile of its own daily values over the previous 3 years. Groups: extreme
agreeing with the verdict, extreme against it, not extreme. Also: agreement with the replica's macro_score where both
exist. Output: data/research/macro_rebuild.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import macro as MC                                     # noqa: E402

MARKETS = [k for k in MC.MARKET if k not in ("6S", "6N")]


def st(g):
    if len(g) < 8:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "end": round(float(g.r.mean()), 2),
            "t": round(float(g.r.mean() / g.r.std(ddof=1) * np.sqrt(len(g))), 2), "mae_z": round(float(g.mae_z.mean()), 2),
            "2019-22": round(float(g[g.t < "2023"].r.mean()), 2) if (g.t < "2023").sum() else None,
            "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2) if (g.t >= "2023").sum() else None}


if __name__ == "__main__":
    cal = MC.load_calendar()
    days = pd.date_range("2015-06-01", C.TODAY)
    scores = {k: MC.market_scores(cal, k, days)["total"] for k in MARKETS}
    T = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
    T = T[T.m.isin(MARKETS)].copy()
    rows = []
    for _, r in T.iterrows():
        p = C.load_px(r.m)
        a, b = p.index.searchsorted(pd.Timestamp(r.entry)), p.index.searchsorted(pd.Timestamp(r.exit))
        sg = 1 if r.v == "BULLISH" else -1
        seg = 100 * sg * (p.iloc[a:b + 1].to_numpy() / p.iloc[a] - 1)
        vol = 100 * np.diff(np.log(p.iloc[max(0, a - 253):a].to_numpy())).std() * np.sqrt(max(1, b - a))
        t = pd.Timestamp(r.t)
        hist = scores[r.m][(scores[r.m].index <= t) & (scores[r.m].index > t - pd.DateOffset(years=3))]
        pc = 100 * float((hist.iloc[:-1] < hist.iloc[-1]).mean())
        side = 1 if pc >= 80 else -1 if pc <= 20 else 0
        lab = "not extreme" if side == 0 else ("extreme, agrees" if side == sg else "extreme, against")
        rows.append({**r.to_dict(), "mae_z": float(seg.min() / vol), "lab": lab})
    df = pd.DataFrame(rows)
    res = {"all": st(df), "by": {k: st(g) for k, g in df.groupby("lab")},
           "by_sector": {f"{s} · {k}": st(g) for (s, k), g in df.groupby(["sector", "lab"])},
           "until_replica_end": {k: st(g) for k, g in df[df.t <= "2026-09-16"].groupby("lab")}}
    a, b = df[df.lab == "extreme, against"].r, df[df.lab == "extreme, agrees"].r
    res["against_minus_agrees"] = {"diff": round(float(a.mean() - b.mean()), 2), "t": round(float((a.mean() - b.mean()) / np.sqrt(a.var() / len(a) + b.var() / len(b))), 2)}
    # agreement with the replica's total macro score
    rep = pd.read_csv(os.path.expanduser("~/Downloads/scores_taeglich_gesamt_und_macro.csv"), parse_dates=["date"])
    MAPR = {"6E": "EURO", "6B": "GB-POUND", "6J": "JP-YEN", "6A": "AU-DOLLAR", "6C": "CA-DOLLAR", "DX": "US-DOLLAR", "ES": "SPX500",
            "NQ": "NASDAQ", "YM": "DOW", "CL": "USOIL", "NG": "NATGAS", "HG": "COPPER", "PL": "PLATINUM", "GC": "GOLD", "SI": "SILVER"}
    agree = {}
    for k, sym in MAPR.items():
        x = rep[rep.symbol == sym].set_index("date").macro_score.reindex(days)
        m = x.notna() & (x.index >= "2016-01-01")
        agree[k] = {"corr": round(float(np.corrcoef(scores[k][m], x[m])[0, 1]), 2), "same_sign": round(float((np.sign(scores[k][m]) == np.sign(x[m])).mean()), 2)}
    res["vs_replica"] = agree
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "macro_rebuild.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:3d} won {o['win']:4.1f}% end {o['end']:+.2f}% t{o['t']:+.1f} MAE(z) {o['mae_z']:+.2f} | 19-22 {o['2019-22']:+.2f} 23-26 {o['2023-26']:+.2f}" if o else "-"
    print("vs replica:", agree)
    print("\nall", f(res["all"]))
    for k, o in res["by"].items():
        print(f"  {k:17s} {f(o)}")
    print("  against - agrees:", res["against_minus_agrees"])
    print("\nonly up to the replica's end (16 Sep 2026):")
    for k, o in res["until_replica_end"].items():
        print(f"  {k:17s} {f(o)}")
    print("\nby sector:")
    for k, o in res["by_sector"].items():
        print(f"  {k:34s} {f(o)}")
