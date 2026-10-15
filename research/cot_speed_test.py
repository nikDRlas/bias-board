#!/usr/bin/env python3
"""Is a COT extreme reached FAST a stronger signal than one the commercials crept into?

Signals: the board's COT read (commercials at an extreme with retail or funds opposite), one position per market at a
time, 8 weeks from the first close after the Friday release, since 2003. For each signal two speed measures:
  move4w   change in the commercials' net position over the 4 weeks before the signal, in the direction of the
           extreme, divided by the typical size of a 4-week change (its standard deviation over the prior 3 years)
  weeks    weeks since the commercials' 1-year percentile was last on the other side of 50 (fewer = faster)
Signals are split into thirds (fast / medium / slow) for each measure.
Output: data/research/cot_speed.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, rd = C.load_px(k), C.CotReader(k)
        x = C.load_cot(k)
        net = x["comm"].to_numpy(float)
        d4 = pd.Series(net).diff(4)
        sd4 = d4.rolling(156, min_periods=52).std().shift(1).to_numpy()
        d4 = d4.to_numpy()
        p1 = rd.P["comm"]["1 yr"]
        lp = np.log(p)
        busy = pd.Timestamp("1900-01-01")
        for i in range(len(rd.dates)):
            v = rd.read_at(i)
            if v not in ("BULLISH", "BEARISH"):
                continue
            rel = rd.dates[i] + pd.Timedelta(days=3)
            if rel < p.index[0] or rel <= busy:
                continue
            a, b = p.index.searchsorted(rel), p.index.searchsorted(rel + pd.Timedelta(weeks=8))
            if b >= len(p) or a < 61:
                continue
            sg = 1 if v == "BULLISH" else -1           # commercials' side: long extreme -> bullish
            mv = sg * d4[i] / sd4[i] if np.isfinite(sd4[i]) and sd4[i] > 0 else np.nan
            j = i
            while j > 0 and np.isfinite(p1[j]) and (p1[j] - 50) * sg > 0:
                j -= 1
            weeks = i - j
            vol = lp.diff().iloc[a - 60:a].std() * np.sqrt(b - a)
            rows.append({"m": k, "d": str(rd.dates[i].date()), "move4w": float(mv), "weeks": int(weeks),
                         "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1), "z": float(sg * (lp.iloc[b] - lp.iloc[a]) / vol)})
            busy = p.index[b]
        print(k, flush=True)
    df = pd.DataFrame(rows)

    def agg(g):
        z = g.z[np.isfinite(g.z)]
        return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
                "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)}
    res = {}
    for col, fast_high in (("move4w", True), ("weeks", False)):
        d = df[np.isfinite(df[col])].copy()
        q = d[col].rank(pct=True)
        d["bucket"] = np.where(q > 2 / 3, "high", np.where(q > 1 / 3, "mid", "low"))
        lab = {"high": "fast", "low": "slow"} if fast_high else {"high": "slow", "low": "fast"}
        lab["mid"] = "medium"
        d["speed"] = d.bucket.map(lab)
        res[col] = {per: {s: agg(g) for s, g in (d if per == "2003-26" else d[d.d >= "2016"]).groupby("speed")}
                    for per in ("2003-26", "2016-26")}
        res[col]["cutoffs"] = [round(float(d[col].quantile(1 / 3)), 2), round(float(d[col].quantile(2 / 3)), 2)]
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "cot_speed.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
