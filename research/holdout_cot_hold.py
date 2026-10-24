#!/usr/bin/env python3
"""HOLDOUT check of the 8-week COT hold (chosen on 2019-26) on 2006-2018, which played no part in choosing it.
Per market, one position at a time: every board COT signal (slow skipped, COT minimum / Bernd gate as on the board, US
indices long-only), entry at the first close after its release. Compare (a) hold while lit + 1 week vs (b) the board's
hold (outside currencies at least 8 weeks unless COT flips), and (c) late entries: weekly entry points after (a)'s exit up
to week 8: +1 normal week before -1 within 4 weeks, and 4-week move minus blind holding (same side, same market, same
period, i.e. the in-period drift, as for the 2019-26 numbers). Output: data/research/holdout_cot_hold.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import bernd                                           # noqa: E402

PERIODS = {"holdout 2006-18": ("2006-01-01", "2018-12-31"), "chosen on 2019-26": ("2019-01-01", "2026-12-31")}


def stats(g, col):
    if len(g) < 5:
        return None
    return {"n": len(g), "win": round(100 * float((g[col] > 0).mean()), 1), "avg": round(float(g[col].mean()), 2)}


if __name__ == "__main__":
    rows, late = [], []
    for k in C.M:
        if k == "DX":
            continue
        p = C.load_px(k); x = p.to_numpy(float)
        rd = C.CotReader(k); lit = C.lit_sides(rd, C.speed_series(k))
        fx = C.M[k][3] == "FX"
        gate = bernd.Gate(k) if fx else None
        busy = pd.Timestamp("1900-01-01")
        for i in range(len(lit)):
            v = lit[i]
            if not v or (i and lit[i - 1] == v):
                continue
            rel = rd.dates[i] + pd.Timedelta(days=3)
            if rel <= busy or rel < pd.Timestamp("2005-06-01"):
                continue
            ok = (gate.read(rel) == v) if fx else C.cot_big_enough(k, v, rel)
            if not ok:
                continue
            a = p.index.searchsorted(rel)
            ex_a = C.cot_exit(rd.dates, lit, i)
            C.COT_MIN_WEEKS = 8                        # the rule under test
            ex_b = C.cot_exit(rd.dates, lit, i, k=k)
            C.COT_MIN_WEEKS = 0
            if ex_a is None or ex_b is None or a < 260:
                continue
            ia, ib = p.index.searchsorted(ex_a), p.index.searchsorted(ex_b)
            if ib >= len(p) or ia >= len(p):
                continue
            sg = 1 if v == "BULLISH" else -1
            def mv(b): return 100 * sg * (x[b] / x[a] - 1)
            per = next(v2 for v2 in PERIODS.values() if v2[0] <= str(rel.date()) <= v2[1]) if str(rel.date()) >= "2006-01-01" else None
            if per is None:
                continue
            qq = x[(p.index >= per[0]) & (p.index <= per[1])]

            def blind(L, q=qq):
                return float(np.mean(sg * (q[L:] / q[:-L] - 1) * 100)) if 0 < L < len(q) else 0.0
            rows.append({"k": k, "fx": fx, "t": rel, "short": mv(ia) - blind(ia - a), "long": mv(ib) - blind(ib - a),
                         "w_short": (ia - a) / 5, "w_long": (ib - a) / 5})
            busy = p.index[max(ia, ib)]
            # late entries: after the short hold's exit up to 8 weeks after entry
            e8 = rel + pd.Timedelta(weeks=8)
            for t0 in pd.date_range(ex_a, e8, freq="7D"):
                b0 = p.index.searchsorted(t0)
                if b0 + 20 >= len(p) or t0 >= e8:
                    continue
                wk = float(np.std(np.diff(np.log(x[b0 - 252:b0]))) * 100 * np.sqrt(5))
                path = sg * (x[b0:b0 + 21] / x[b0] - 1) * 100
                up = np.argmax(path >= wk) if (path >= wk).any() else 99
                dn = np.argmax(path <= -wk) if (path <= -wk).any() else 99
                late.append({"fx": fx, "t": t0, "first": np.nan if up == dn == 99 else float(up < dn),
                             "x4": path[20] - blind(20)})
    d, L = pd.DataFrame(rows), pd.DataFrame(late)
    out = {}
    for per, (a0, b0) in PERIODS.items():
        for fx in (False, True):
            g = d[(d.fx == fx) & (d.t >= a0) & (d.t <= b0)]
            h = L[(L.fx == fx) & (L.t >= a0) & (L.t <= b0)]
            key = f"{per} | {'currencies' if fx else 'outside currencies'}"
            out[key] = {"signals": len(g),
                        "lit+1 minus blind": round(float(g.short.mean()), 2), "8w hold minus blind": round(float(g.long.mean()), 2),
                        "lit+1 per week": round(float(g.short.sum() / g.w_short.sum()), 3), "8w per week": round(float(g.long.sum() / g.w_long.sum()), 3),
                        "late entries": len(h), "late target_first": round(100 * float(h["first"].mean()), 1),
                        "late 4w minus blind": round(float(h.x4.mean()), 2)}
    json.dump(out, open(os.path.join(HERE, "..", "data", "research", "holdout_cot_hold.json"), "w"), indent=1)
    for k2, o in out.items():
        print(f"{k2:52s} signals {o['signals']:3d} | minus blind: lit+1 {o['lit+1 minus blind']:+.2f}%  8w {o['8w hold minus blind']:+.2f}% "
              f"| per week {o['lit+1 per week']:+.3f} vs {o['8w per week']:+.3f} | late entries {o['late entries']:4d}: +1 before -1 {o['late target_first']:.1f}%, 4w {o['late 4w minus blind']:+.2f}%")
