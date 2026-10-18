#!/usr/bin/env python3
"""COT-led verdicts: does the size of the market's own COT record predict the result?

For every COT-led verdict of the walk-forward test (research/verdict_test.py trades: 'COT only' and 'COT + calendar'),
the market's earlier COT setups in the same direction (one per lit run, held while lit + 1 week, finished before the
verdict's Saturday) give:
  usual move   their average end move, in units of the market's normal daily move at the verdict (past-year volatility)
  usual MAE    their average worst move along the way, same units
Verdicts are grouped by these; at least 5 earlier setups needed. Output: data/research/cot_record_size.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402


def cases(k, p):
    rd = C.CotReader(k)
    lit = C.lit_sides(rd, C.speed_series(k))
    px = p.to_numpy(float)
    out = []
    for i in range(len(rd.dates)):
        v = lit[i]
        if not v or (i and lit[i - 1] == v):
            continue
        ex = C.cot_exit(rd.dates, lit, i)
        rel = rd.dates[i] + pd.Timedelta(days=3)
        if ex is None or rel < p.index[0]:
            continue
        a, b = p.index.searchsorted(rel), p.index.searchsorted(ex)
        if b >= len(p) or b <= a:
            continue
        sg = 1 if v == "BULLISH" else -1
        seg = sg * (px[a:b + 1] / px[a] - 1)
        out.append({"side": v, "exit": p.index[b], "end": 100 * seg[-1], "mae": 100 * seg.min()})
    return out


def st(g):
    if len(g) < 5:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "t": round(float(g.r.mean() / g.r.std(ddof=1) * np.sqrt(len(g))), 2),
            "2019-22": round(float(g[g.t < "2023"].r.mean()), 2) if (g.t < "2023").sum() else None,
            "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2) if (g.t >= "2023").sum() else None}


if __name__ == "__main__":
    T = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
    T = T[T.basis.isin(["COT only", "COT + calendar"])].copy()
    rows = []
    for k, g in T.groupby("m"):
        p = C.load_px(k)
        lr = np.diff(np.log(p.to_numpy(float)))
        cs = cases(k, p)
        for _, r in g.iterrows():
            t = pd.Timestamp(r.t)
            prior = [c for c in cs if c["side"] == r.v and c["exit"] <= t]
            ti = p.index.searchsorted(t)
            vol = 100 * lr[max(0, ti - 253):ti - 1].std()
            rows.append({**r.to_dict(), "n_prior": len(prior),
                         "usual": float(np.mean([c["end"] for c in prior])) / vol if len(prior) >= 5 else None,
                         "usual_pct": float(np.mean([c["end"] for c in prior])) if len(prior) >= 5 else None,
                         "mae": float(np.mean([c["mae"] for c in prior])) / vol if len(prior) >= 5 else None})
    df = pd.DataFrame(rows)
    res = {"all COT-led": st(df), "fewer than 5 earlier setups": st(df[df.usual.isna()])}
    d = df[df.usual.notna()]
    res["by usual move (normal days)"] = {lab: st(d[(d.usual > lo) & (d.usual <= hi)]) for lab, lo, hi in
                                         (("<= 0 (record loses)", -99, 0), ("0 to 0.5", 0, .5), ("0.5 to 1", .5, 1),
                                          ("1 to 2", 1, 2), ("> 2", 2, 99))}
    res["cut: usual move >= x normal days"] = {str(x): {"keep": round(100 * float((d.usual >= x).mean()), 1), **(st(d[d.usual >= x]) or {})}
                                              for x in (-99, 0, 0.5, 1, 1.5, 2)}
    res["by usual MAE (normal days)"] = {lab: st(d[(d.mae > lo) & (d.mae <= hi)]) for lab, lo, hi in
                                        (("worse than -3", -99, -3), ("-3 to -2", -3, -2), ("-2 to -1", -2, -1), ("better than -1", -1, 0.01))}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "cot_record_size.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
