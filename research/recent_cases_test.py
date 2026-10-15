#!/usr/bin/env python3
"""Does a good recent record ("5 of 6 times it worked") predict the next COT signal in that market?

COT signals with the board's rule (commercials vs retail or funds, slow signals skipped), one position per market at a
time, 8 weeks from the first close after the Friday release, since 2003. For each signal: of that market's previous 6
signals (any direction, and same direction) whose result was already known, how many won? Group the NEXT signal's result
by that count. Output: data/research/recent_cases.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
from verdict_test import speed_series, speed_of       # noqa: E402

if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, rd, sp = C.load_px(k), C.CotReader(k), speed_series(k)
        lp = np.log(p)
        busy, hist = pd.Timestamp("1900-01-01"), []
        for i in range(len(rd.dates)):
            v = rd.read_at(i)
            if v not in ("BULLISH", "BEARISH") or speed_of(sp, i, v) == "slow":
                continue
            rel = rd.dates[i] + pd.Timedelta(days=3)
            if rel < p.index[0] or rel <= busy:
                continue
            a, b = p.index.searchsorted(rel), p.index.searchsorted(rel + pd.Timedelta(weeks=8))
            if b >= len(p) or a < 61:
                continue
            sg = 1 if v == "BULLISH" else -1
            r = 100 * sg * float(p.iloc[b] / p.iloc[a] - 1)
            known = [h for h in hist if h["exit"] <= rel]
            any6 = [h["win"] for h in known[-6:]]
            same6 = [h["win"] for h in [h for h in known if h["v"] == v][-6:]]
            rows.append({"m": k, "d": str(rd.dates[i].date()), "r": r, "win": r > 0,
                         "any6": sum(any6) if len(any6) == 6 else None, "same6": sum(same6) if len(same6) == 6 else None})
            hist.append({"exit": p.index[b], "v": v, "win": r > 0})
            busy = p.index[b]
    df = pd.DataFrame(rows)
    bucket = lambda x: None if pd.isna(x) else ("5-6 of 6" if x >= 5 else "3-4 of 6" if x >= 3 else "0-2 of 6")
    res = {}
    for col in ("any6", "same6"):
        g = df.assign(b=df[col].map(bucket)).dropna(subset=["b"])
        res[col] = {per: {b: {"n": len(x), "won": round(100 * float(x.win.mean()), 1), "avg": round(float(x.r.mean()), 2)}
                          for b, x in (g if per == "all" else g[(g.d >= "2016") == (per == "2016-26")]).groupby("b")}
                    for per in ("all", "2003-15", "2016-26")}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "recent_cases.json"), "w"), indent=1)
    for col, v in res.items():
        print(col)
        for per, bs in v.items(): print("  ", per, {b: (o["n"], o["won"], o["avg"]) for b, o in bs.items()})
