#!/usr/bin/env python3
"""How to hold a COT verdict when entering with technicals: stop 1 normal week against the entry (one week's usual
move: daily volatility over the past year x sqrt 5), target 1-4 normal weeks; if neither is hit, exit with the verdict
(one week after the COT signal goes dark). All COT-led verdicts of the walk-forward replay 2019-26
(data/research/verdict.json), entered at the verdict's entry. Also how far the winners ran (best point along the way).
Output: data/research/cot_hold.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

if __name__ == "__main__":
    v = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
    v = v[v.basis.str.startswith("COT")].copy()
    for c in ("t", "entry", "exit"):
        v[c] = pd.to_datetime(v[c])
    px, rows = {}, []
    for r in v.itertuples():
        p = px.setdefault(r.m, C.load_px(r.m))
        x = p.to_numpy(float)
        a, b = p.index.searchsorted(r.entry), p.index.searchsorted(r.exit)
        if b >= len(p) or b <= a:
            continue
        sg = 1 if r.v == "BULLISH" else -1
        path = sg * (x[a:b + 1] / x[a] - 1) * 100
        wk = float(np.std(np.diff(np.log(x[max(0, a - 252):a]))) * 100 * np.sqrt(5))
        row = {"fx": r.sector == "Currencies", "t": r.t, "end": path[-1], "mfe": path.max(), "mfe_wk": path.max() / wk,
               "weeks": (b - a) / 5}
        dn = np.argmax(path <= -wk) if (path <= -wk).any() else 10 ** 9
        for tg in (1, 2, 3, 4):
            up = np.argmax(path >= tg * wk) if (path >= tg * wk).any() else 10 ** 9
            row[f"R{tg}"] = tg if up < dn else -1.0 if dn < up else path[-1] / wk
            row[f"hit{tg}"] = bool(up < dn)
        rows.append(row)
    d = pd.DataFrame(rows)
    out = {}
    for fx, g in d.groupby("fx"):
        w, e = g[g.end > 0], g.t < "2023"
        out["currencies" if fx else "other"] = {
            "n": len(g), "hold_weeks": round(float(g.weeks.median()), 1),
            "winners": {"n": len(w), "mfe": round(float(w.mfe.mean()), 2), "mfe_weeks": round(float(w.mfe_wk.mean()), 2)},
            "targets": {str(tg): {"hit": round(100 * float(g[f"hit{tg}"].mean()), 1), "R": round(float(g[f"R{tg}"].mean()), 2),
                                  "2019-22": round(float(g.loc[e, f"R{tg}"].mean()), 2), "2023-26": round(float(g.loc[~e, f"R{tg}"].mean()), 2)}
                        for tg in (1, 2, 3, 4)}}
    json.dump(out, open(os.path.join(HERE, "..", "data", "research", "cot_hold.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
