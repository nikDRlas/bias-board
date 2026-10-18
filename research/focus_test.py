#!/usr/bin/env python3
"""Pick 1-3 focus setups a week: does ranking by a setup's own record pick better trades?

Every Saturday 2019-2026, every market's verdict is rebuilt with only data known that day (shared rule bias/verdict.py,
slow COT signals skipped, turning calendars in sequence). Each verdict gets its setup's OWN record, as the board shows it:
  calendar verdicts      the window's past years (COT + calendar: only years COT agreed; calendar over COT: years it was against)
  COT only               the market's past COT setups in that direction (one per lit run), held while lit + 1 week, results known by that day
From those cases: hit rate, average end move, average best move along the way (MFE), average worst move (MAE), all in
units of the market's normal volatility over the holding period. Each week the top 3 by each score are compared with all
verdicts. Outcomes: from the next close, calendar verdicts to the window end, COT-led verdicts while the signal stays lit + 1 week.
Output: data/research/focus.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
import verdict as VD                                   # noqa: E402
from conflict_test import ret                          # noqa: E402
from verdict_test import speed_series, speed_of       # noqa: E402

MIN_CASES = 3


def path_stats(lc, a, b, sg):
    seg = sg * (lc[a:b + 1] - lc[a])
    return seg[-1], seg.max(), seg.min()


def cot_cases(p, lc, rd, lit):
    out = []
    for i in range(len(rd.dates)):
        v = lit[i]
        if v is None or (i > 0 and lit[i - 1] == v):
            continue                                   # one case per lit run, from its first report
        ex = C.cot_exit(rd.dates, lit, i)
        if ex is None:
            continue
        rel = rd.dates[i] + pd.Timedelta(days=3)
        a, b = p.index.searchsorted(rel), p.index.searchsorted(ex)
        if b >= len(p) or a < 1:
            continue
        e, mf, ma = path_stats(lc, a, b, 1 if v == "BULLISH" else -1)
        out.append({"d": rd.dates[i], "exit": p.index[b], "v": v, "end": e, "mfe": mf, "mae": ma, "len": b - a})
    return out


if __name__ == "__main__":
    end = C.TODAY - pd.Timedelta(days=1)
    rows = []
    for k in C.M:
        p = C.load_px(k)
        lc = np.log(p.to_numpy(float))
        dlc = np.diff(lc, prepend=lc[0])
        cal, rd, sp = SS.Calendar(p), C.CotReader(k), speed_series(k)
        lit = C.lit_sides(rd, sp)
        CC = cot_cases(p, lc, rd, lit)
        for t in pd.date_range("2019-01-05", end, freq="W-SAT"):
            cot = rd.read(t)
            i_rep = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
            if cot in VD.SIDES and speed_of(sp, i_rep, cot) == "slow":
                cot = "NEUTRAL"
            if cot in VD.SIDES and not C.cot_big_enough(k, cot, t):
                cot = "NEUTRAL"
            v, basis, (ws, status) = VD.board_read(cot, cal, t, rd)
            d = ws[0] if status == "driver" else None
            past = cal.past(t.year, d, rd) if d else None
            if v not in VD.SIDES:
                continue
            ti = p.index.searchsorted(t)
            sig = dlc[max(1, ti - 252):ti].std()
            # the setup's own cases
            if basis == "COT only":
                cs = [c for c in CC if c["v"] == v and c["exit"] <= t]
                cases = [(c["end"], c["mfe"], c["mae"], C.COT_REF_DAYS) for c in cs]   # fixed scale: the length depends on the outcome
            else:
                rel = {"COT + calendar": "agree", "Calendar over COT": "against"}.get(basis)
                sg = 1 if d["side"] == "BUY" else -1
                cases = []
                for y, info in zip(range(t.year - d.get("ny", 15), t.year), past["years"]):
                    if rel and info["rel"] != rel:
                        continue
                    a = cal.first[y][0] + d["s"]
                    e, mf, ma = path_stats(lc, a, a + d["len"], sg)
                    cases.append((e, mf, ma, d["len"]))
            if len(cases) < MIN_CASES:
                continue
            arr = np.array(cases)
            norm = sig * np.sqrt(np.maximum(arr[:, 3], 1))
            score = {"hit": float((arr[:, 0] > 0).mean()), "end": float((arr[:, 0] / norm).mean()),
                     "mfe": float((arr[:, 1] / norm).mean()), "mae": float((arr[:, 2] / norm).mean()), "n": len(arr)}
            score["combo"] = score["hit"] + score["end"]
            # outcome from this Saturday
            if VD.horizon(basis) == "window":
                x = ret(p, max(t, pd.Timestamp(d["start"])), pd.Timestamp(d["end"]), v)
            else:
                ex = C.cot_exit(rd.dates, lit, i_rep) if 0 <= i_rep and lit[i_rep] == cot else None
                x = ret(p, t + pd.Timedelta(days=1), ex, v, C.COT_REF_DAYS) if ex is not None else None
            if not x or pd.Timestamp(x["exit"]) > end:
                continue
            rows.append({"m": k, "t": str(t.date()), "basis": basis, **score, **x})
        print(k, sum(r["m"] == k for r in rows), flush=True)
    df = pd.DataFrame(rows)

    def st(g):
        z = g.z[np.isfinite(g.z)]
        return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
                "avg_z": round(float(z.mean()), 3)} if len(g) else None
    rankers = {"hit rate": ("hit", False), "end move": ("end", False), "best move (MFE)": ("mfe", False),
               "smallest drawdown (MAE)": ("mae", False), "hit rate + end move": ("combo", False)}
    res = {"all verdicts": {per: st(g) for per, g in (("all", df), ("2019-22", df[df.t < "2023"]), ("2023-26", df[df.t >= "2023"]))}}
    for name, (col, asc) in rankers.items():
        for pool_name, pool in (("", df), (" · COT + calendar first", df)):
            picks = []
            for t, g in pool.groupby("t"):
                if pool_name:
                    g = g.assign(pri=(g.basis == "COT + calendar").astype(int)).sort_values(["pri", col], ascending=[False, asc])
                else:
                    g = g.sort_values(col, ascending=asc)
                picks.append(g.head(3))
            P = pd.concat(picks)
            res[name + pool_name] = {per: st(g) for per, g in (("all", P), ("2019-22", P[P.t < "2023"]), ("2023-26", P[P.t >= "2023"]))}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "focus.json"), "w"), indent=1)
    for name, v in res.items():
        print(f"{name:45s} " + " | ".join(f"{per} {o['win']}% avg {o['avg']:+.2f}% z {o['avg_z']:+.3f} n{o['n']}" for per, o in v.items() if o))
