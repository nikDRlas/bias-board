#!/usr/bin/env python3
"""'Move already done': does a running setup that has already made its usual move pay less from here on?

COT: every lit run (board rule, slow signals skipped) since 2003, checked on each weekly release while it runs.
  so far   = move from entry (first close after the first lit release) to that release's close, in the signal direction
  usual    = average end move of the market's earlier setups in that direction (held while lit + 1 week), known by then
  rest     = from that close to the setup's exit
Seasonal: every Saturday 2019-26 on which the board's driver window was already running.
  so far   = move from the window start this year;  usual = the window's average move over its 15 past years
  rest     = from the next close to the window end
Groups: done (so far >= usual), not yet, and against (so far in the wrong direction). Output: data/research/move_done.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402


def grp(so_far, usual):
    if usual is None or not np.isfinite(usual) or usual <= 0:
        return "no positive usual move"
    return "done" if so_far >= usual else "against" if so_far < 0 else "not yet"


def st(g):
    if len(g) < 3:
        return None
    r = g.rest
    return {"n": len(g), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "t": round(float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))), 2)}


if __name__ == "__main__":
    cot, sea = [], []
    for k in C.M:
        p, rd = C.load_px(k), C.CotReader(k)
        px = p.to_numpy(float)
        lit = C.lit_sides(rd, C.speed_series(k))
        D = rd.dates
        done_cases = []                                  # (exit date, side, end move) of finished setups
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
            j = i + 1
            while j < len(D) and lit[j] == v:          # every later release while the run is lit
                rj = D[j] + pd.Timedelta(days=3)
                c = p.index.searchsorted(rj)
                if c >= b:
                    break
                prior = [m for (e, s, m) in done_cases if s == v and e <= rj]
                usual = float(np.mean(prior)) if len(prior) >= 3 else None
                so = 100 * sg * (px[c] / px[a] - 1)
                cot.append({"m": k, "d": str(rj.date()), "wk": j - i, "so_far": so, "usual": usual,
                            "g": grp(so, usual), "rest": 100 * sg * (px[b] / px[c] - 1)})
                j += 1
            done_cases.append((ex, v, 100 * sg * (px[b] / px[a] - 1)))
        cal = SS.Calendar(p)
        for t in pd.date_range("2019-01-05", C.TODAY - pd.Timedelta(days=1), freq="W-SAT"):
            ws, status = cal.windows(t)
            if status != "driver":
                continue
            d = ws[0]
            r = cal.remaining(t, d)
            if not r or not r["started"] or r["so_far"] is None:
                continue
            sg = 1 if d["side"] == "BUY" else -1
            c, e = p.index.searchsorted(t), p.index.searchsorted(pd.Timestamp(d["end"]))
            if e >= len(p) or e <= c or p.index[e] > C.TODAY:
                continue
            usual = sg * d["avg"]
            so = sg * r["so_far"]
            sea.append({"m": k, "d": str(t.date()), "so_far": so, "usual": usual, "g": grp(so, usual),
                        "rest": 100 * sg * (px[e] / px[c] - 1), "start": str(d["start"])})
        print(k, flush=True)
    C_, S_ = pd.DataFrame(cot), pd.DataFrame(sea)
    # seasonal: one observation per market-window-year (first Saturday in each group) to avoid counting a window weekly
    S1 = S_.sort_values("d").groupby(["m", "start", "g"]).head(1)
    res = {"cot": {g: {"all": st(x), "2003-15": st(x[x.d < "2016"]), "2016-26": st(x[x.d >= "2016"])} for g, x in C_.groupby("g")},
           "seasonal_weekly": {g: st(x) for g, x in S_.groupby("g")},
           "seasonal_first": {g: {"all": st(x), "2019-22": st(x[x.d < "2023"]), "2023-26": st(x[x.d >= "2023"])} for g, x in S1.groupby("g")}}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "move_done.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
