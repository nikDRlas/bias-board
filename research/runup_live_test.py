#!/usr/bin/env python3
"""Run-up inside a COT setup, measured the way the LIVE board measures it (2026-11-07, user's crude-oil question; corrects
research/runup_done_test.py, which measured from the walk-forward entry with weekly checks - for 100% of these cases that
is a later close than the board's, up to 31 trading days later for re-entries).
Anchor = first close at/after the release of the first report of the setup's lit run (bias/verdict.py entry_close for COT).
Checked every trading day inside the walk-forward verdict (data/research/verdict.json), first event per verdict:
  END k   best close since the anchor >= k x the usual END move of the market's winning COT setups on that side (known
          then, >= 5) = the board's move-done yardstick (CL bullish: +13.0%)
  BEST k  the same against the winners' usual BEST run (CL bullish: +17.62%)
  gave    and price has given back at least half of that best since; hold = it has not
Outcome = rest of the verdict to its exit in normal weeks (daily vol over the year before the anchor x sqrt 5).
Control = rest from every 5th day of every COT verdict.
RESULT 2026-11-07 (any week +0.38, n479, +0.36 / +0.41):
  END 1.0 gave     +0.12 n64 52% won (2019-22 +0.39 / 2023-26 -0.12); metals & energy -0.23 n21 33% won  <- crude now
  BEST 0.5 gave    +0.27 n130 54% (+0.33 / +0.20)   (old note said +0.56 n94: the anchor mismatch)
  BEST 1.0 hold    +0.02 n123 50% (+0.08 / -0.04)   (old note -0.02 n102)
A stand-aside rule on END 1.0 gave would drop setups that still made +0.39 in 2019-22 -> fails a half; board note only."""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
V = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
V = V[V.basis.str.startswith("COT")]
D3 = pd.Timedelta(days=3)
CELLS = [("END", 1.0, "gave"), ("END", 1.0, "any"), ("BEST", 0.5, "gave"), ("BEST", 1.0, "hold"), ("BEST", 1.0, "any")]
RD, LIT, CASES, ev, ctl = {}, {}, {}, {}, []
for r in V.itertuples():
    k = r.m
    if k not in RD:
        RD[k] = C.CotReader(k); LIT[k] = C.lit_sides(RD[k], C.speed_series(k), skip_slow=True); CASES[k] = C.cot_cases(k)[0]
    rd, lit = RD[k], LIT[k]
    q = rd.dates.searchsorted(r.t - D3, "right") - 1
    while q >= 0 and lit[q] != r.v:
        q -= 1
    if q < 0:
        continue
    p = C.load_px(k); px = p.to_numpy(float)
    a0 = p.index.searchsorted(rd.dates[C.lit_start(lit, q)] + D3)
    a, b = p.index.searchsorted(r.entry), p.index.searchsorted(r.exit)
    if b >= len(px) or a0 < 253 or b - a < 3:
        continue
    sg = 1 if r.v == "BULLISH" else -1
    wk = 100 * float(np.diff(np.log(px[a0 - 252:a0])).std() * np.sqrt(5))
    won = [x for x in CASES[k] if x["side"] == r.v and x["exit"] <= r.entry and x["end"] > 0]
    if len(won) < 5:
        continue
    Y = {"END": float(np.mean([x["end"] for x in won])), "BEST": float(np.mean([x["mfe"] for x in won]))}
    path = sg * (px[a0:b + 1] / px[a0] - 1) * 100
    h = "2019-22" if r.t < pd.Timestamp("2023") else "2023-26"
    rest = lambda j: sg * (px[b] / px[j] - 1) * 100 / wk
    ctl.append({"h": h, "sec": r.sector, "rest": float(np.mean([rest(j) for j in range(a, b, 5)]))})
    for (y, kk, mode) in CELLS:
        for j in range(max(a, a0 + 1), b):
            best, net = path[:j - a0 + 1].max(), path[j - a0]
            if best >= kk * Y[y] and (mode == "any" or (mode == "gave") == (net <= best / 2)):
                ev.setdefault((y, kk, mode), []).append({"m": k, "sec": r.sector, "h": h, "rest": rest(j), "shift": a - a0})
                break


def st(x):
    v = np.asarray(x.rest, float)
    if len(v) < 3:
        return {"n": int(len(v))}
    return {"n": int(len(v)), "won": round(100 * float((v > 0).mean()), 1), "avg": round(float(v.mean()), 2),
            "t": round(float(v.mean() / v.std(ddof=1) * np.sqrt(len(v))), 2),
            "2019-22": round(float(x[x.h == "2019-22"].rest.mean()), 2), "2023-26": round(float(x[x.h == "2023-26"].rest.mean()), 2)}


Cn = pd.DataFrame(ctl)
out = {"control": st(Cn)}
print("control (any 5th day of a COT verdict):", out["control"])
for key, rows in ev.items():
    E = pd.DataFrame(rows)
    nm = f"{key[0]} {key[1]} {key[2]}"
    out[nm] = {"all": st(E), **{s: st(g) for s, g in E.groupby("sec")}, "anchor_later_share": round(100 * float((E["shift"] > 0).mean()))}
    print(f"{nm:14s}", out[nm]["all"], "| by sector:", {s: (v.get("avg"), v["n"]) for s, v in out[nm].items() if s not in ("all", "anchor_later_share")})
json.dump(out, open(os.path.join(HERE, "..", "data", "research", "runup_live.json"), "w"), indent=1)
