#!/usr/bin/env python3
"""COT: enter when the commercials' extreme STARTS (the board) or when it ENDS (they leave it, after >= 2 weeks)?

Episodes = runs of weekly reports with the commercials at an extreme on >= 2 of 5 lookbacks, same side (the board's
commercial condition; whether retail / funds were opposite at the start is recorded). Direction = follow the
commercials. A: entry at the first close after the release of the episode's first report. B: entry at the first close
after the release of the first report where they are no longer at the extreme (episodes of >= 2 weeks). Fixed holds
4, 8, 13 weeks; vs the market's drift. All markets since 2003, currencies separately. Bearish index episodes skipped.
Output: data/research/cot_release_entry.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402


def st(g):
    if len(g) < 10:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "vs_drift": round(float(g.ex.mean()), 2), "t": round(float(g.ex.mean() / g.ex.std(ddof=1) * np.sqrt(len(g))), 2),
            "2003-15": round(float(g[g.d < "2016"].ex.mean()), 2), "2016-26": round(float(g[g.d >= "2016"].ex.mean()), 2)}


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, rd = C.load_px(k), C.CotReader(k)
        lc = np.log(p.to_numpy(float))
        comm = [rd.side("comm", i) for i in range(len(rd.dates))]
        i = 0
        while i < len(comm):
            c = comm[i]
            if not c or (i and comm[i - 1] == c):
                i += 1
                continue
            j = i
            while j + 1 < len(comm) and comm[j + 1] == c:
                j += 1
            sg = 1 if c == "hi" else -1
            if not (k in C.LONG_ONLY and sg < 0):
                opp = "lo" if c == "hi" else "hi"
                specs = rd.side("retail", i) == opp or rd.side("fund", i) == opp
                for entry, rep in (("A start", i), ("B end", j + 1)):
                    if entry == "B end" and (j - i + 1 < 2 or rep >= len(rd.dates)):
                        continue
                    rel = rd.dates[rep] + pd.Timedelta(days=3)
                    a = p.index.searchsorted(rel)
                    if a < 300 or rel < p.index[0]:
                        continue
                    for h in (4, 8, 13):
                        b = p.index.searchsorted(rel + pd.Timedelta(weeks=h))
                        if b >= len(p):
                            continue
                        L, lo = b - a, max(0, a - 2520)
                        dr = float((lc[lo + L:a] - lc[lo:a - L]).mean())
                        r = 100 * (np.exp(sg * (lc[b] - lc[a])) - 1)
                        rows.append({"entry": entry, "h": h, "fx": C.M[k][3] == "FX", "specs": specs, "d": str(rd.dates[i].date()),
                                     "weeks": j - i + 1, "r": r, "ex": r - 100 * (np.exp(sg * dr) - 1)})
            i = j + 1
    df = pd.DataFrame(rows)
    res = {}
    for scope, g0 in (("all markets", df), ("currencies", df[df.fx]), ("other markets", df[~df.fx]),
                      ("all, specs opposite at start", df[df.specs])):
        res[scope] = {f"{e} · {h}w": st(g0[(g0.entry == e) & (g0.h == h)]) for e in ("A start", "B end") for h in (4, 8, 13)}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "cot_release_entry.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:4d} won {o['win']:4.1f}% avg {o['avg']:+.2f}% vs drift {o['vs_drift']:+.2f}% (t {o['t']:+.1f}) | 03-15 {o['2003-15']:+.2f} 16-26 {o['2016-26']:+.2f}" if o else "-"
    for scope, v in res.items():
        print(f"\n== {scope}")
        for k2, o in v.items():
            print(f"   {k2:12s} {f(o)}")
