#!/usr/bin/env python3
"""COT: hold while the signal is lit, one trade per setup.

A setup = a run of released weekly reports with the board's COT signal on the same side (rule as on the board, slow
signals skipped). Entry at the first close after the first lit report's release. Exit variants:
  lit+Nw   exit N weeks after the release of the LAST lit report (N = 0, 1, 2, 4); an opposite signal ends it too
  fixed Nw exit N weeks after entry, setups starting while a trade is open are skipped (the earlier test, without re-entries)
One position per market. Each trade is one independent case, so the t is honest. Output: data/research/cot_lit_hold.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
from verdict_test import speed_series, speed_of       # noqa: E402

SECTOR = lambda k: {"FX": "Currencies", "Indices": "Indices", "Agriculture": "Agriculture"}.get(C.M[k][3], "Metals & energy")
VARIANTS = [("lit+0w", "lit", 0), ("lit+1w", "lit", 1), ("lit+2w", "lit", 2), ("lit+4w", "lit", 4),
            ("fixed 2w", "fixed", 2), ("fixed 4w", "fixed", 4), ("fixed 8w", "fixed", 8)]


def setups(rd, sp):
    lit = [v if v in ("BULLISH", "BEARISH") and speed_of(sp, i, v) != "slow" else None
           for i, v in ((i, rd.read_at(i)) for i in range(len(rd.dates)))]
    out, i = [], 0
    while i < len(lit):
        if lit[i]:
            j = i
            while j + 1 < len(lit) and lit[j + 1] == lit[i]:
                j += 1
            out.append((i, j, lit[i]))
            i = j + 1
        else:
            i += 1
    return out


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, rd, sp = C.load_px(k), C.CotReader(k), speed_series(k)
        lp = np.log(p)
        S = setups(rd, sp)
        for name, kind, n in VARIANTS:
            busy = pd.Timestamp("1900-01-01")
            for i, j, v in S:
                rel = rd.dates[i] + pd.Timedelta(days=3)
                if rel < p.index[0] or rel <= busy:
                    continue
                if kind == "lit":
                    end = rd.dates[j] + pd.Timedelta(days=3) + pd.Timedelta(weeks=n)
                    if j + 1 < len(rd.dates):            # an opposite signal at the next report closes it on release
                        nxt = rd.dates[j + 1] + pd.Timedelta(days=3)
                        if any(x for x in [rd.read_at(j + 1)] if x in ("BULLISH", "BEARISH") and x != v and speed_of(sp, j + 1, x) != "slow"):
                            end = min(end, nxt)
                        end = max(end, nxt) if n == 0 else end   # lit+0w: out when the dark report is released
                else:
                    end = rel + pd.Timedelta(weeks=n)
                a, b = p.index.searchsorted(rel), p.index.searchsorted(end)
                if b >= len(p) or a < 61 or b <= a:
                    continue
                sg = 1 if v == "BULLISH" else -1
                vol = lp.diff().iloc[a - 60:a].std() * np.sqrt(b - a)
                rows.append({"var": name, "m": k, "sector": SECTOR(k), "d": str(rd.dates[i].date()), "days": int(b - a),
                             "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1), "z": float(sg * (lp.iloc[b] - lp.iloc[a]) / vol)})
                busy = p.index[b]
    df = pd.DataFrame(rows)

    def st(g):
        if len(g) < 3:
            return None
        wk = g.days.sum() / 5
        return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
                "weeks": round(float(g.days.mean() / 5), 1), "per_week": round(float(g.r.sum() / wk), 3),
                "t": round(float(g.z.mean() / g.z.std(ddof=1) * np.sqrt(len(g))), 2)}
    res = {}
    for name, _, _ in VARIANTS:
        g = df[df["var"] == name]
        res[name] = {"all": st(g), "2003-15": st(g[g.d < "2016"]), "2016-21": st(g[(g.d >= "2016") & (g.d < "2022")]),
                     "2022-26": st(g[g.d >= "2022"]), "by_sector": {s: st(gg) for s, gg in g.groupby("sector")}}
    json.dump({**res, "trades": rows}, open(os.path.join(HERE, "..", "data", "research", "cot_lit_hold.json"), "w"), indent=1)
    f = lambda o: f"{o['win']:4.1f}% avg {o['avg']:+.2f}% {o['weeks']:4.1f}wk {o['per_week']:+.3f}%/wk t {o['t']:+.2f} n{o['n']}" if o else "-"
    for name, v in res.items():
        print(f"{name:9s} all {f(v['all'])}\n          03-15 {f(v['2003-15'])} | 16-21 {f(v['2016-21'])} | 22-26 {f(v['2022-26'])}")
        print("          ", {s: (o['win'], o['per_week'], o['t']) for s, o in v['by_sector'].items() if o})
