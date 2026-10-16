#!/usr/bin/env python3
"""COT holding period: 2, 4, 6, 8 or 12 weeks?

The board's COT signal (commercials at an extreme with retail or funds opposite, funds not on the commercials' side,
slow signals skipped). For each holding period a separate sequential pass per market (one position at a time),
entry at the first close after the Friday release, since 2003. Output: data/research/cot_horizon.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
from verdict_test import speed_series, speed_of       # noqa: E402

HOLDS = (2, 4, 6, 8, 12)
SECTOR = lambda k: {"FX": "Currencies", "Indices": "Indices", "Agriculture": "Agriculture"}.get(C.M[k][3], "Metals & energy")

if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, rd, sp = C.load_px(k), C.CotReader(k), speed_series(k)
        lp = np.log(p)
        sig = [(i, v) for i in range(len(rd.dates)) for v in [rd.read_at(i)]
               if v in ("BULLISH", "BEARISH") and speed_of(sp, i, v) != "slow"]
        for h in HOLDS:
            busy = pd.Timestamp("1900-01-01")
            for i, v in sig:
                rel = rd.dates[i] + pd.Timedelta(days=3)
                if rel < p.index[0] or rel <= busy:
                    continue
                a, b = p.index.searchsorted(rel), p.index.searchsorted(rel + pd.Timedelta(weeks=h))
                if b >= len(p) or a < 61:
                    continue
                sg = 1 if v == "BULLISH" else -1
                vol = lp.diff().iloc[a - 60:a].std() * np.sqrt(b - a)
                rows.append({"h": h, "m": k, "sector": SECTOR(k), "d": str(rd.dates[i].date()),
                             "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1), "z": float(sg * (lp.iloc[b] - lp.iloc[a]) / vol)})
                busy = p.index[b]
    df = pd.DataFrame(rows)

    def st(g, h):
        z = g.z[np.isfinite(g.z)]
        return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
                "per_week": round(float(g.r.mean()) / h, 3), "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)} if len(g) > 2 else None
    res = {}
    for h in HOLDS:
        g = df[df.h == h]
        res[h] = {"all": st(g, h), "2003-15": st(g[g.d < "2016"], h), "2016-26": st(g[g.d >= "2016"], h),
                  "by_sector": {s: st(gg, h) for s, gg in g.groupby("sector")}}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "cot_horizon.json"), "w"), indent=1)
    for h, v in res.items():
        f = lambda o: f"{o['win']}% avg {o['avg']:+.2f}% ({o['per_week']:+.3f}%/wk) t {o['t']:+.2f} n{o['n']}" if o else "-"
        print(f"{h:2d}w  all {f(v['all'])} | 2003-15 {f(v['2003-15'])} | 2016-26 {f(v['2016-26'])}")
        print("     ", {s: (o['win'], o['avg'], o['t']) for s, o in v['by_sector'].items() if o})
