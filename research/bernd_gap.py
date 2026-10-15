#!/usr/bin/env python3
"""Why do Bernd's COT tables look so much better than our tests?

A) Entry day: his track record measures from the report TUESDAY close; the data is only public on FRIDAY.
   Same cases (his rule: extreme reached after the opposite extreme), same lookbacks and history spans,
   4 and 8 weeks, entered Tuesday vs the first close after the Friday release.
B) Edge Finder: he shows the best row (>= 6 cases) out of up to 5 lookbacks x 2 groups x 5 horizons. How high does
   the best row get if every case were a coin flip? (simulation with his actual case counts)
C) Lit lookbacks: does 1, 2-3, 4-6 or 7-10 lit lookbacks (both groups together) change the result? 8 weeks from
   the release, one position at a time, since 2003 and since 2016.
Output: data/research/bernd_gap.json
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

rng = np.random.default_rng(1)


def his_cases(rd, g, lb, side):
    v = rd.P[g][lb]
    lit = (v >= C.HI) if side == "hi" else (v <= C.LO)
    opp = (v <= C.LO) if side == "hi" else (v >= C.HI)
    out, armed = [], True
    for i in range(len(v)):
        if lit[i] and not (i and lit[i - 1]):
            if armed:
                out.append(i)
                armed = False
        elif opp[i]:
            armed = True
    return out


def fwd(p, d, weeks):
    a = p.index.searchsorted(d)
    b = p.index.searchsorted(d + pd.Timedelta(weeks=weeks))
    return p.iloc[b] / p.iloc[a] - 1 if b < len(p) and a < len(p) else np.nan


if __name__ == "__main__":
    A = {"tue": {4: [], 8: []}, "fri": {4: [], 8: []}}
    rowsizes = []
    C3 = []
    for k in C.M:
        p, rd = C.load_px(k), C.CotReader(k)
        end = rd.dates[-1]
        for g, follow in (("retail", -1), ("comm", 1)):
            for lb in C.LB:
                for side in ("hi", "lo"):
                    sg = follow * (1 if side == "hi" else -1)
                    cs = [i for i in his_cases(rd, g, lb, side) if rd.dates[i] >= end - pd.DateOffset(years=C.HIST[lb])]
                    if cs:
                        rowsizes.append(len(cs))
                    for i in cs:
                        d = rd.dates[i]
                        for h in (4, 8):
                            for e, off in (("tue", 0), ("fri", 3)):
                                r = fwd(p, d + pd.Timedelta(days=off), h)
                                if np.isfinite(r):
                                    A[e][h].append(sg * r)
        # C) number of lit lookbacks behind the board's read
        lp = np.log(p)
        busy = pd.Timestamp("1900-01-01")
        for i in range(len(rd.dates)):
            v = rd.read_at(i)
            if v not in ("BULLISH", "BEARISH"):
                continue
            n_lit = 0
            for g, follow in (("retail", -1), ("comm", 1)):
                for lb in C.LB:
                    x = rd.P[g][lb][i]
                    if np.isfinite(x) and (x >= C.HI or x <= C.LO):
                        dv = "BULLISH" if follow * (1 if x >= C.HI else -1) > 0 else "BEARISH"
                        n_lit += dv == v
            rel = rd.dates[i] + pd.Timedelta(days=3)
            if rel < p.index[0] or rel <= busy:
                continue
            a, b = p.index.searchsorted(rel), p.index.searchsorted(rel + pd.Timedelta(weeks=8))
            if b >= len(p) or a < 61:
                continue
            sg = 1 if v == "BULLISH" else -1
            vol = lp.diff().iloc[a - 60:a].std() * np.sqrt(b - a)
            C3.append({"m": k, "d": str(rd.dates[i].date()), "lit": n_lit, "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1),
                       "z": float(sg * (lp.iloc[b] - lp.iloc[a]) / vol)})
            busy = p.index[b]
        print(k, flush=True)

    entry = {e: {h: {"n": len(v), "win": round(100 * float(np.mean(np.array(v) > 0)), 1),
                     "avg": round(100 * float(np.mean(v)), 2)} for h, v in hs.items()} for e, hs in A.items()}

    # B) best row out of 20 rows of coin flips with his case counts, 6-case floor, 60% bar
    sizes = np.array(rowsizes)
    best = []
    for _ in range(4000):
        n = rng.choice(sizes, 20)
        w = rng.binomial(n, 0.5)
        ok = (n >= 6) & (w / np.maximum(n, 1) >= 0.6)
        best.append((w / n)[ok].max() if ok.any() else np.nan)
    best = np.array(best)
    luck = {"share_with_a_qualifying_row": round(100 * float(np.isfinite(best).mean()), 1),
            "median_best_row": round(100 * float(np.nanmedian(best)), 1),
            "p90_best_row": round(100 * float(np.nanpercentile(best, 90)), 1),
            "median_cases_per_row": int(np.median(sizes))}

    def agg(rows):
        r, z = np.array([x["r"] for x in rows]), np.array([x["z"] for x in rows])
        z = z[np.isfinite(z)]
        return {"n": len(rows), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
                "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)} if len(rows) > 2 else None
    bucket = lambda n: "1 lit" if n <= 1 else "2-3 lit" if n <= 3 else "4-6 lit" if n <= 6 else "7-10 lit"
    lit = {per: {b: agg([x for x in C3 if bucket(x["lit"]) == b and (per == "2003-26" or x["d"] >= "2016")])
                 for b in ("1 lit", "2-3 lit", "4-6 lit", "7-10 lit")} for per in ("2003-26", "2016-26")}
    res = {"entry_day": entry, "edge_finder_luck": luck, "lit_lookbacks": lit}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "bernd_gap.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
