#!/usr/bin/env python3
"""SUPERSEDED 2026-11-07 by research/runup_live_test.py (this one measures from the walk-forward entry with weekly
checks, not from the board's own first close: the board note's +0.56 n94 became +0.27 n130 measured the board's way).
Run-up inside a running verdict (2026-11-04, user's natural-gas question): NG's COT setup since 8 Sep ran about +15%
on closes (+20% low to high) and gave it all back; the board's "move done" only looks at the move from the entry to
today, so it still shows the setup as fully open. Should a big run made DURING the setup count as done?

Event study on the walk-forward replay (data/research/verdict.json, 2019-26): every verdict is checked every 5 trading
days after its entry. Run-up = best close in the verdict's direction since the entry. The first check where the run-up
reaches k x the yardstick is the event; outcome = what the verdict still makes from that close to its exit (that is
what a later zone entry inside the verdict can still catch). Yardsticks, known at the time (market's own finished COT
setups on that side before the check, >= 5 of them; else the event is not counted):
  win_end   the usual END move of its winning COT setups (the yardstick of the board's move-done rule)
  win_mfe   the usual BEST move of its winning COT setups
  weeks     normal weeks of the market (daily vol over the year before the entry x sqrt 5)
"gave back": the same event, but only once price has also given back at least half of the run-up (the NG case).
Control: the rest-to-exit from every weekly check of every verdict (one average per verdict).
Output: data/research/runup_done.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

V = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
KS = {"win_end": (0.5, 0.75, 1.0, 1.5), "win_mfe": (0.5, 0.75, 1.0), "weeks": (1.0, 1.5, 2.0, 3.0)}


def yard(k, side, t, kind, wk):
    if kind == "weeks":
        return wk
    cs, _ = C.cot_cases(k)
    w = [x["end" if kind == "win_end" else "mfe"] for x in cs if x["side"] == side and x["exit"] <= t and x["end"] > 0]
    return float(np.mean(w)) if len(w) >= 5 else None


def stats(x):
    x = np.asarray(x, float)
    if len(x) < 3:
        return {"n": len(x)}
    return {"n": len(x), "win": round(100 * float((x > 0).mean()), 1), "avg": round(float(x.mean()), 2),
            "t": round(float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))), 2)}


ev = {}                         # (kind, k, gave) -> rows
ctl = []
for r in V.itertuples():
    p = C.load_px(r.m)
    px = p.to_numpy(float)
    a, b = p.index.searchsorted(r.entry), p.index.searchsorted(r.exit)
    if b >= len(px) or b - a < 6 or a < 253:
        continue
    sg = 1 if r.v == "BULLISH" else -1
    wk = 100 * float(np.diff(np.log(px[a - 252:a])).std() * np.sqrt(5))
    path = sg * (px[a:b + 1] / px[a] - 1) * 100
    checks = list(range(5, b - a, 5))
    half = "2019-22" if r.t < pd.Timestamp("2023-01-01") else "2023-26"
    cot_led = r.basis.startswith("COT")
    rests = []
    for kind, ks in KS.items():
        Y = yard(r.m, r.v, r.entry, kind, wk)
        if not Y or Y <= 0:
            continue
        for k in ks:
            for gave in (False, True):
                for j in checks:
                    run, net = path[:j + 1].max(), path[j]
                    if run >= k * Y and (not gave or net <= run / 2):
                        rest = 100 * (sg * (px[a + j + (b - a - j)] / px[a + j] - 1))
                        ev.setdefault((kind, k, gave), []).append({"m": r.m, "half": half, "cot": cot_led, "rest": rest,
                                                                    "rest_wk": rest / wk, "weeks_in": j / 5, "run": run, "net": net})
                        break
    for j in checks:
        rests.append(100 * sg * (px[b] / px[a + j] - 1) / wk)
    if rests:
        ctl.append({"half": half, "cot": cot_led, "rest_wk": float(np.mean(rests))})

C_ = pd.DataFrame(ctl)
out = {"control": {"all": stats(C_.rest_wk), "cot": stats(C_[C_.cot].rest_wk),
                   "2019-22": stats(C_[C_.half == "2019-22"].rest_wk), "2023-26": stats(C_[C_.half == "2023-26"].rest_wk)}}
print(f"control (rest to exit from any weekly check, in normal weeks): {out['control']}")
print(f"{'yardstick':8s} {'k':>4s} {'gave':5s} | {'n':>4s} {'won':>5s} {'rest%':>6s} {'rest wk':>7s} {'t':>5s} | 19-22 wk | 23-26 wk | COT-led wk  n")
for (kind, k, gave), rows in sorted(ev.items(), key=lambda x: (x[0][0], x[0][2], x[0][1])):
    E = pd.DataFrame(rows)
    s_all, s_pct = stats(E.rest_wk), stats(E.rest)
    e, l, c = E[E.half == "2019-22"], E[E.half == "2023-26"], E[E.cot]
    out[f"{kind}|{k}|{'gave' if gave else 'any'}"] = {"wk": s_all, "pct": s_pct, "2019-22": stats(e.rest_wk), "2023-26": stats(l.rest_wk),
                                                      "cot_led": stats(c.rest_wk), "weeks_in": round(float(E.weeks_in.median()), 1)}
    if s_all.get("avg") is None:
        continue
    print(f"{kind:8s} {k:4.2f} {'gave' if gave else 'any':5s} | {s_all['n']:4d} {s_pct['win']:5.1f} {s_pct['avg']:+6.2f} {s_all['avg']:+7.2f} {s_all['t']:+5.1f} | "
          f"{e.rest_wk.mean():+8.2f} | {l.rest_wk.mean():+8.2f} | {c.rest_wk.mean():+8.2f} {len(c):3d}")
json.dump(out, open(os.path.join(HERE, "..", "data", "research", "runup_done.json"), "w"), indent=1)
