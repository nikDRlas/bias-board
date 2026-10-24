#!/usr/bin/env python3
"""Is there air left in a COT verdict once price has made its usual move? For every week of every COT-led verdict of the
walk-forward replay 2019-26 (data/research/verdict.json, board hold): the move since the signal's entry as a share of a
yardstick from that market's earlier finished setups on the same side (known by that week): END = average end move of the
winners, MFE = average best point along the way of the winners. Then what came next: +1 normal week before -1 (within 4
weeks; 50% = coin flip) and the 4-week move minus blind holding. Output: data/research/cot_air_left.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

BINS = [(-1e9, 0.5, "<50%"), (0.5, 1.0, "50-100%"), (1.0, 1.5, "100-150%"), (1.5, 1e9, ">=150%")]

if __name__ == "__main__":
    v = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
    v = v[v.basis.str.startswith("COT")].copy()
    for c in ("t", "entry", "exit"):
        v[c] = pd.to_datetime(v[c])
    px, base, rows = {}, {}, []
    for r in v.itertuples():
        cs, p = C.cot_cases(r.m)
        x = p.to_numpy(float)
        sg = 1 if r.v == "BULLISH" else -1
        q = x[p.index >= "2019-01-01"]
        base.setdefault(r.m, {s: float(np.mean(s * (q[20:] / q[:-20] - 1) * 100)) for s in (1, -1)})
        # the signal's own entry (first close after the release of its run's first report)
        run = [c for c in cs if c["side"] == r.v and c["start"] <= r.t and c["exit"] >= r.entry]
        start = run[-1]["start"] if run else r.t
        a0 = p.index.searchsorted(start + pd.Timedelta(days=3))
        for t0 in pd.date_range(r.entry, r.exit, freq="7D"):
            a = p.index.searchsorted(t0)
            if a + 20 >= len(p) or a < 260:
                continue
            prior = [c for c in cs if c["side"] == r.v and c["exit"] <= t0 and c["end"] > 0]
            if len(prior) < 5:
                continue
            so_far = 100 * sg * (x[a] / x[a0] - 1)
            wk = float(np.std(np.diff(np.log(x[a - 252:a]))) * 100 * np.sqrt(5))
            path = sg * (x[a:a + 21] / x[a] - 1) * 100
            up = np.argmax(path >= wk) if (path >= wk).any() else 99
            dn = np.argmax(path <= -wk) if (path <= -wk).any() else 99
            rows.append({"fx": r.sector == "Currencies", "t": t0, "first": np.nan if up == dn == 99 else float(up < dn),
                         "x4": path[20] - base[r.m][sg],
                         "END": so_far / np.mean([c["end"] for c in prior]), "MFE": so_far / np.mean([c["mfe"] for c in prior])})
    d = pd.DataFrame(rows)
    out = {}
    for fx, g in d.groupby("fx"):
        sec = "currencies" if fx else "other"
        for yard in ("END", "MFE"):
            for lo, hi, lab in BINS:
                h = g[(g[yard] >= lo) & (g[yard] < hi)]
                if len(h) < 10:
                    continue
                e = h.t < "2023"
                out[f"{sec} {yard} {lab}"] = {"weeks": len(h), "target_first": round(100 * float(h["first"].mean()), 1),
                    "tf_2019_22": round(100 * float(h.loc[e, "first"].mean()), 1), "tf_2023_26": round(100 * float(h.loc[~e, "first"].mean()), 1),
                    "excess4w": round(float(h.x4.mean()), 2), "ex_2019_22": round(float(h.loc[e, "x4"].mean()), 2),
                    "ex_2023_26": round(float(h.loc[~e, "x4"].mean()), 2)}
    json.dump(out, open(os.path.join(HERE, "..", "data", "research", "cot_air_left.json"), "w"), indent=1)
    for k, o in out.items():
        print(f"{k:28s} weeks {o['weeks']:4d} | +1 before -1 {o['target_first']:5.1f}% (19-22 {o['tf_2019_22']:4.0f}%, 23-26 {o['tf_2023_26']:4.0f}%) | 4w minus blind {o['excess4w']:+.2f}% ({o['ex_2019_22']:+.2f} / {o['ex_2023_26']:+.2f})")
