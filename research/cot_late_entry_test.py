#!/usr/bin/env python3
"""Are COT verdicts still worth entering after the COT signal has gone dark? For every COT-led verdict of the walk-forward
replay 2019-26 (data/research/verdict.json): weekly entry points (a) EARLY = while the board shows the bias today
(verdict entry -> its exit, one week after the signal goes dark) and (b) LATE = after that exit up to 8 weeks after the
verdict's entry (what an 8-week hold would add). From each entry point: target-first (+1 normal week before -1 normal
week, within 4 weeks; 50% = coin flip), the 2- and 4-week move for the verdict's side, and the same move minus blind
holding (every same-side, same-length hold of that market 2019-26). Output: data/research/cot_late_entry.json"""
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
    px, base, rows = {}, {}, []
    for r in v.itertuples():
        p = px.setdefault(r.m, C.load_px(r.m))
        x = p.to_numpy(float)
        sg = 1 if r.v == "BULLISH" else -1
        q = x[p.index >= "2019-01-01"]
        for L in (10, 20):
            base.setdefault((r.m, L), {s: float(np.mean(s * (q[L:] / q[:-L] - 1) * 100)) for s in (1, -1)})
        e8 = r.entry + pd.Timedelta(weeks=8)
        for t0 in pd.date_range(r.entry, max(r.exit, e8), freq="7D"):
            phase = "early" if t0 < r.exit else ("late" if t0 < e8 else None)
            if phase is None:
                continue
            a = p.index.searchsorted(t0)
            if a + 20 >= len(p) or a < 260:
                continue
            wk = float(np.std(np.diff(np.log(x[a - 252:a]))) * 100 * np.sqrt(5))
            path = sg * (x[a:a + 21] / x[a] - 1) * 100
            up = np.argmax(path >= wk) if (path >= wk).any() else 99
            dn = np.argmax(path <= -wk) if (path <= -wk).any() else 99
            rows.append({"m": r.m, "fx": r.sector == "Currencies", "t": t0, "phase": phase, "first": np.nan if up == dn == 99 else float(up < dn),
                         "m2": path[10], "m4": path[20], "x2": path[10] - base[(r.m, 10)][sg], "x4": path[20] - base[(r.m, 20)][sg]})
    d = pd.DataFrame(rows)
    out = {}
    for fx, g in d.groupby("fx"):
        for ph, h in g.groupby("phase"):
            e = h.t < "2023"
            per = h.groupby(h.t.dt.to_period("M")).x4.mean()
            out[f"{'currencies' if fx else 'other'} {ph}"] = {
                "entries": len(h), "target_first": round(100 * float(h["first"].mean()), 1),
                "tf_2019_22": round(100 * float(h.loc[e, "first"].mean()), 1), "tf_2023_26": round(100 * float(h.loc[~e, "first"].mean()), 1),
                "move2w": round(float(h.m2.mean()), 2), "move4w": round(float(h.m4.mean()), 2),
                "excess2w": round(float(h.x2.mean()), 2), "excess4w": round(float(h.x4.mean()), 2),
                "ex4_2019_22": round(float(h.loc[e, "x4"].mean()), 2), "ex4_2023_26": round(float(h.loc[~e, "x4"].mean()), 2),
                "t_excess4w_month": round(float(per.mean() / per.std(ddof=1) * np.sqrt(len(per))), 1)}
    json.dump(out, open(os.path.join(HERE, "..", "data", "research", "cot_late_entry.json"), "w"), indent=1)
    for k, o in out.items():
        print(f"{k:18s} entries {o['entries']:4d} | +1wk before -1wk {o['target_first']:5.1f}% (19-22 {o['tf_2019_22']:.0f}%, 23-26 {o['tf_2023_26']:.0f}%) | "
              f"4w move {o['move4w']:+.2f}% minus blind {o['excess4w']:+.2f}% (19-22 {o['ex4_2019_22']:+.2f}, 23-26 {o['ex4_2023_26']:+.2f}) t {o['t_excess4w_month']:+.1f} | 2w minus blind {o['excess2w']:+.2f}%")
