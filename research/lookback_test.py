#!/usr/bin/env python3
"""Does each market have its own best COT lookback?

Single-lookback read for lookback L: retail at an L-extreme is faded, commercials at an L-extreme are followed;
if both are lit they must agree, otherwise no side. Every market x L: one position at a time, 8 weeks from the
first close after the Friday release, since prices start (2003).

1) in-sample: best L per market over the whole history
2) selection check: at the start of each year from 2010, pick each market's best L from the years before only
   (highest t, at least 15 past trades), trade that L during the year; compare with the board's fixed read
   (>= 2 lit lookbacks) and with all five lookbacks averaged.
Output: data/research/lookback.json
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

LBS = list(C.LB)


def read_single(rd, i, lb):
    dirs = {}
    for g, follow in (("retail", -1), ("comm", 1)):
        v = rd.P[g][lb][i]
        if np.isfinite(v) and (v >= C.HI or v <= C.LO):
            dirs[g] = "BULLISH" if follow * (1 if v >= C.HI else -1) > 0 else "BEARISH"
    if not dirs or len(set(dirs.values())) > 1:
        return None
    return next(iter(dirs.values()))


def trades(k, p, rd, reader_fn):
    lp = np.log(p)
    out, busy = [], pd.Timestamp("1900-01-01")
    for i in range(len(rd.dates)):
        v = reader_fn(i)
        if v not in ("BULLISH", "BEARISH"):
            continue
        rel = rd.dates[i] + pd.Timedelta(days=3)
        if rel < p.index[0] or rel <= busy:
            continue
        a, b = p.index.searchsorted(rel), p.index.searchsorted(rel + pd.Timedelta(weeks=8))
        if b >= len(p) or a < 61:
            continue
        sg = 1 if v == "BULLISH" else -1
        vol = lp.diff().iloc[a - 60:a].std() * np.sqrt(b - a)
        out.append({"m": k, "d": rd.dates[i], "exit": p.index[b], "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1),
                    "z": float(sg * (lp.iloc[b] - lp.iloc[a]) / vol)})
        busy = p.index[b]
    return out


def agg(rows):
    if len(rows) < 3:
        return None
    r, z = np.array([x["r"] for x in rows]), np.array([x["z"] for x in rows])
    return {"n": len(rows), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)}


if __name__ == "__main__":
    per, sel, fixed, avg5, insample = {}, [], [], [], {}
    for k in C.M:
        p, rd = C.load_px(k), C.CotReader(k)
        T = {lb: trades(k, p, rd, lambda i, lb=lb: read_single(rd, i, lb)) for lb in LBS}
        B = trades(k, p, rd, lambda i: rd.read_at(i))
        per[k] = {lb: agg(T[lb]) for lb in LBS}
        per[k]["board"] = agg(B)
        best = max((lb for lb in LBS if per[k][lb]), key=lambda lb: per[k][lb]["t"])
        insample[k] = best
        for y in range(2010, C.TODAY.year + 1):
            y0, y1 = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 1}-01-01")
            past = {lb: [x for x in T[lb] if x["exit"] < y0] for lb in LBS}
            ok = {lb: agg(v) for lb, v in past.items() if len(v) >= 15}
            if not ok:
                continue
            pick = max(ok, key=lambda lb: ok[lb]["t"])
            sel += [dict(x, y=y, pick=pick) for x in T[pick] if y0 <= x["d"] < y1]
            fixed += [dict(x, y=y) for x in B if y0 <= x["d"] < y1]
            for lb in LBS:
                avg5 += [dict(x, y=y, lb=lb) for x in T[lb] if y0 <= x["d"] < y1]
        print(k, "best in-sample:", best, per[k][best], "| board:", per[k]["board"], flush=True)
    picks = pd.Series([x["pick"] for x in sel]).value_counts().to_dict()
    res = {"per_market": per, "best_in_sample": insample,
           "selection_2010_26": {"picked_per_asset": agg(sel), "board_fixed": agg(fixed), "all_five_lookbacks": agg(avg5),
                                 "how_often_each_lookback_was_picked": picks}}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "lookback.json"), "w"), indent=1, default=str)
    print(json.dumps(res["selection_2010_26"], indent=1))
