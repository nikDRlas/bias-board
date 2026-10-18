#!/usr/bin/env python3
"""COT 'move done': which yardstick of the usual move tells when a running setup has nothing left?

Every COT setup since 2003 (board signal, slow skipped, COT minimum not applied so all signals count), checked on
each weekly release while it runs. 'So far' = move from entry to that release, in the signal's direction. Yardsticks
from the market's earlier setups in the same direction, finished by then (at least 5):
  avg_all      average end move of all earlier setups (the board's current measure)
  avg_winners  average end move of the earlier setups that ended in the signal's direction
  median_mfe   median of their best point along the way
Rest = from that release to the setup's exit. Grouped by share of the yardstick already made.
Output: data/research/cot_done_yardstick.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

BINS = [(-1e9, 0, "against so far"), (0, .5, "0-50%"), (.5, 1, "50-100%"), (1, 1.5, "100-150%"), (1.5, 1e9, "150%+")]


def st(g):
    if len(g) < 10:
        return None
    return {"n": len(g), "win": round(100 * float((g.rest > 0).mean()), 1), "avg": round(float(g.rest.mean()), 2),
            "t": round(float(g.rest.mean() / g.rest.std(ddof=1) * np.sqrt(len(g))), 2),
            "2003-15": round(float(g[g.d < "2016"].rest.mean()), 2) if (g.d < "2016").sum() else None,
            "2016-26": round(float(g[g.d >= "2016"].rest.mean()), 2) if (g.d >= "2016").sum() else None}


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, rd = C.load_px(k), C.CotReader(k)
        px = p.to_numpy(float)
        lit = C.lit_sides(rd, C.speed_series(k))
        D = rd.dates
        done = []
        for i in range(len(D)):
            v = lit[i]
            if not v or (i and lit[i - 1] == v):
                continue
            ex = C.cot_exit(D, lit, i)
            rel = D[i] + pd.Timedelta(days=3)
            if ex is None or rel < p.index[0]:
                continue
            a, b = p.index.searchsorted(rel), p.index.searchsorted(ex)
            if b >= len(p) or b <= a:
                continue
            sg = 1 if v == "BULLISH" else -1
            seg = 100 * sg * (px[a:b + 1] / px[a] - 1)
            j = i + 1
            while j < len(D) and lit[j] == v:
                c = p.index.searchsorted(D[j] + pd.Timedelta(days=3))
                if c >= b:
                    break
                prior = [x for x in done if x["side"] == v and x["exit"] <= D[j]]
                if len(prior) >= 5:
                    ends = np.array([x["end"] for x in prior])
                    ys = {"avg_all": ends.mean(), "avg_winners": ends[ends > 0].mean() if (ends > 0).any() else np.nan,
                          "median_mfe": float(np.median([x["mfe"] for x in prior]))}
                    so = 100 * sg * (px[c] / px[a] - 1)
                    rows.append({"m": k, "d": str(D[j].date()), "so_far": so, "rest": 100 * sg * (px[b] / px[c] - 1),
                                 **{f"share_{n}": (so / y if y and y > 0 else np.nan) for n, y in ys.items()}})
                j += 1
            done.append({"side": v, "exit": p.index[b], "end": float(seg[-1]), "mfe": float(seg.max())})
        print(k, flush=True)
    df = pd.DataFrame(rows)
    res = {}
    for n in ("avg_all", "avg_winners", "median_mfe"):
        col = f"share_{n}"
        x = df[df[col].notna()]
        res[n] = {lab: st(x[(x[col] > lo) & (x[col] <= hi)]) for lo, hi, lab in BINS}
        res[n]["share of checks past 100%"] = round(100 * float((x[col] >= 1).mean()), 1)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "cot_done_yardstick.json"), "w"), indent=1)
    f = lambda o: f"{o['win']:4.1f}% {o['avg']:+.2f}% t{o['t']:+.1f} (03-15 {o['2003-15']:+.2f} / 16-26 {o['2016-26']:+.2f}) n{o['n']}" if o else "-"
    for n, v in res.items():
        print(f"\n{n}: {v['share of checks past 100%']}% of weekly checks are past 100%")
        for lab in [b[2] for b in BINS]:
            print(f"   {lab:15s} rest: {f(v[lab])}")
