#!/usr/bin/env python3
"""COT exits: hold until positioning returns from its extreme, or back to normal (the middle).

Signals as on the board (commercials at an extreme on >= 2 of 5 lookbacks with retail or funds at the opposite extreme,
funds not on the commercials' side, slow signals skipped), one trade per lit run, entry at the first close after the
release. The opposing group(s) = those at the opposite extreme on the entry report. Exit at the first close after the
release of the first report that shows:
  A comm leaves     commercials lit on < 2 of 5 lookbacks (same side)
  B specs leave     none of the opposing groups still at the opposite extreme (>= 2 of 5)
  C first of A/B
  D comm normal     commercials' average percentile over the 5 lookbacks back through 50
  E specs normal    every opposing group's average percentile back through 50
  F first of D/E
  lit+1w            the board now: signal dark, out one week after the last lit report
  fixed 8w          the board before
Results in % (t on % returns, one case per setup), per week held, by halves and asset class.
Output: data/research/cot_exit_normal.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

SECTOR = lambda k: {"FX": "Currencies", "Indices": "Indices", "Agriculture": "Agriculture"}.get(C.M[k][3], "Metals & energy")
MAX_WEEKS = 52                                          # safety cap: never hold longer than a year


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, rd = C.load_px(k), C.CotReader(k)
        lit = C.lit_sides(rd, C.speed_series(k))
        D = rd.dates
        n = len(D)
        avg = {g: np.nanmean(np.vstack([rd.P[g][lb] for lb in C.LB]), axis=0) for g in ("comm", "retail", "fund")}
        rel = lambda i: D[i] + pd.Timedelta(days=3)
        starts = [i for i in range(n) if lit[i] and (i == 0 or lit[i - 1] != lit[i])]
        for name in ("A comm leaves", "B specs leave", "C first of A/B", "D comm normal", "E specs normal",
                     "F first of D/E", "lit+1w", "fixed 8w"):
            busy = pd.Timestamp("1900-01-01")
            for i in starts:
                v = lit[i]
                if rel(i) < p.index[0] or rel(i) <= busy:
                    continue
                c = rd.side("comm", i)
                opp = "lo" if c == "hi" else "hi"
                specs = [g for g in ("retail", "fund") if rd.side(g, i) == opp]
                up = c == "hi"                              # commercials long extreme
                def comm_left(j): return rd.side("comm", j) != c
                def specs_left(j): return all(rd.side(g, j) != opp for g in specs)
                def comm_norm(j): return (avg["comm"][j] < 50) if up else (avg["comm"][j] > 50)
                def specs_norm(j): return all((avg[g][j] > 50) if up else (avg[g][j] < 50) for g in specs)
                test = {"A comm leaves": comm_left, "B specs leave": specs_left,
                        "C first of A/B": lambda j: comm_left(j) or specs_left(j),
                        "D comm normal": comm_norm, "E specs normal": specs_norm,
                        "F first of D/E": lambda j: comm_norm(j) or specs_norm(j)}.get(name)
                if name == "lit+1w":
                    ex = C.cot_exit(D, lit, i)
                elif name == "fixed 8w":
                    ex = rel(i) + pd.Timedelta(weeks=8)
                else:
                    ex = None
                    for j in range(i + 1, min(n, i + MAX_WEEKS + 1)):
                        if test(j):
                            ex = rel(j)
                            break
                    if ex is None and i + MAX_WEEKS < n:
                        ex = rel(i + MAX_WEEKS)
                if ex is None:
                    continue
                a, b = p.index.searchsorted(rel(i)), p.index.searchsorted(ex)
                if b >= len(p) or b <= a:
                    continue
                sg = 1 if v == "BULLISH" else -1
                rows.append({"var": name, "m": k, "sector": SECTOR(k), "d": str(D[i].date()), "days": int(b - a),
                             "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1)})
                busy = p.index[b]
    df = pd.DataFrame(rows)

    def st(g):
        if len(g) < 3:
            return None
        r = g.r
        return {"n": len(g), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
                "weeks": round(float(g.days.mean() / 5), 1), "per_week": round(float(r.sum() / (g.days.sum() / 5)), 3),
                "t": round(float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))), 2),
                "avg_win": round(float(r[r > 0].mean()), 2), "avg_loss": round(float(r[r < 0].mean()), 2)}
    res = {}
    for name, g in df.groupby("var", sort=False):
        res[name] = {"all": st(g), "2003-15": st(g[g.d < "2016"]), "2016-21": st(g[(g.d >= "2016") & (g.d < "2022")]),
                     "2022-26": st(g[g.d >= "2022"]), "by_sector": {s: st(gg) for s, gg in g.groupby("sector")}}
    json.dump({**res, "trades": rows}, open(os.path.join(HERE, "..", "data", "research", "cot_exit_normal.json"), "w"), indent=1)
    f = lambda o: f"{o['win']:4.1f}% avg {o['avg']:+.2f}% ({o['avg_win']:+.1f}/{o['avg_loss']:+.1f}) {o['weeks']:4.1f}wk {o['per_week']:+.3f}%/wk t {o['t']:+.2f} n{o['n']}" if o else "-"
    g2 = lambda o: f"{o['per_week']:+.3f}%/wk t {o['t']:+.2f}" if o else "-"
    for name, v in res.items():
        print(f"{name:15s} {f(v['all'])}")
        print(f"{'':15s} 03-15 {g2(v['2003-15'])} | 16-21 {g2(v['2016-21'])} | 22-26 {g2(v['2022-26'])} | " +
              " ".join(f"{s[:4]} {o['per_week']:+.3f}" for s, o in v['by_sector'].items() if o))
