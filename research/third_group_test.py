#!/usr/bin/env python3
"""When commercials are at an extreme and one speculator group is opposite, does the THIRD group matter?

Board signals (commercials at an extreme on >= 2 of 5 lookbacks, retail or funds at the opposite extreme, slow signals
skipped), split by what each speculator group does: opposite / neutral / same side as the commercials. Each case is a
separate sequential pass per market (one position at a time), 8 weeks from the first close after the Friday release,
since 2003. Output: data/research/third_group.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
from verdict_test import speed_series, speed_of       # noqa: E402

CASES = {"A both opposite": ("opp", "opp"), "B funds opposite, retail neutral": ("neutral", "opp"),
         "C funds opposite, retail SAME side": ("same", "opp"), "D retail opposite, funds neutral": ("opp", "neutral"),
         "E retail opposite, funds SAME side": ("opp", "same")}


def state(rd, g, i, comm_side):
    s = rd.side(g, i)
    return "neutral" if s is None else ("same" if s == comm_side else "opp")


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, rd, sp = C.load_px(k), C.CotReader(k), speed_series(k)
        lp = np.log(p)
        for case, (want_r, want_f) in CASES.items():
            busy = pd.Timestamp("1900-01-01")
            for i in range(len(rd.dates)):
                cs = rd.side("comm", i)
                if not cs:
                    continue
                if (state(rd, "retail", i, cs), state(rd, "fund", i, cs)) != (want_r, want_f):
                    continue
                v = "BULLISH" if cs == "hi" else "BEARISH"
                if speed_of(sp, i, v) == "slow":
                    continue
                rel = rd.dates[i] + pd.Timedelta(days=3)
                if rel < p.index[0] or rel <= busy:
                    continue
                a, b = p.index.searchsorted(rel), p.index.searchsorted(rel + pd.Timedelta(weeks=8))
                if b >= len(p) or a < 61:
                    continue
                sg = 1 if v == "BULLISH" else -1
                vol = lp.diff().iloc[a - 60:a].std() * np.sqrt(b - a)
                rows.append({"case": case, "m": k, "d": str(rd.dates[i].date()), "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1),
                             "z": float(sg * (lp.iloc[b] - lp.iloc[a]) / vol)})
                busy = p.index[b]
        print(k, flush=True)
    df = pd.DataFrame(rows)

    def st(g):
        if len(g) < 3:
            return None
        z = g.z[np.isfinite(g.z)]
        return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
                "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)}
    res = {c: {"all": st(g), "2003-15": st(g[g.d < "2016"]), "2016-26": st(g[g.d >= "2016"])} for c, g in df.groupby("case")}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "third_group.json"), "w"), indent=1)
    for c, v in res.items():
        print(f"{c:40s} " + " | ".join(f"{per} {o['win']}% avg {o['avg']:+.2f}% t {o['t']:+.2f} n{o['n']}" if o else f"{per} -" for per, o in v.items()))
