#!/usr/bin/env python3
"""Has the setup already made its move? Measured on the FULL range, wicks included (2026-11-07, user: "price did that move,
even if it didn't close"). One measure on both sides:
  swing = biggest rise from a low to a later high (shorts: high to a later low) on daily highs/lows, from the setup's
          start: COT = the release day of the first report of its lit run (the board's "since"), calendar = window start
  yardstick = median swing of the market's WINNING walk-forward verdicts that had ended before the check, start to exit
          (>= 5, else the event is not counted). Markets without high/low history (DX, KC, LE) use closes.
Event study on data/research/verdict.json 2019-26, checked every trading day inside the verdict, first event per verdict:
  >= k x yardstick (k 0.75 / 1.0 / 1.25), and 'gave' = the close has given back at least half of that swing since its top
Outcome = rest of the verdict from that close to its exit, in normal weeks. Control = rest from every 5th day.
Output: data/research/swing_hl.json (SWING_START=release: swing_hl_release.json)
RESULT 2026-11-07 (report-day start, cleaned highs/lows core.load_hl; any 5th day +0.38, n572, +0.36 / +0.41):
  >= 1.0 x winners' swing        +0.43 n106 64% won (2019-22 +0.55 / 2023-26 +0.37); metals & energy +0.03 n37
  >= 1.0 and gave back half      +0.48 n48 (+0.46 / +0.49)
  >= 1.0 and holding             +0.36 n100 (+0.36 / +0.36)
  >= 1.25 x                      +0.31 n67 (+0.75 / +0.11)
Reaching the winners' usual swing (wicks included) is NO sign a setup is done; the board shows it as information only.
Uncleaned feed gave the same picture (+0.38 n110); release-day start too (+0.34 n112)."""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
START = os.environ.get("SWING_START", "report")      # report = the report day (the board's "since"), release = its Friday release
hl, swing = C.load_hl, C.swing_path


V = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
D3 = pd.Timedelta(days=3)
RD, LIT, PX = {}, {}, {}
start = {}
for r in V.itertuples():
    k = r.m
    if k not in PX:
        PX[k] = (C.load_px(k), *hl(k))
    p = PX[k][0]
    if r.basis.startswith("COT"):
        if k not in RD:
            RD[k] = C.CotReader(k); LIT[k] = C.lit_sides(RD[k], C.speed_series(k), skip_slow=True)
        rd, lit = RD[k], LIT[k]
        q = rd.dates.searchsorted(r.t - D3, "right") - 1
        while q >= 0 and lit[q] != r.v:
            q -= 1
        start[r.Index] = p.index.searchsorted(rd.dates[C.lit_start(lit, q)] + (D3 if START == "release" else pd.Timedelta(0))) if q >= 0 else p.index.searchsorted(r.entry)
    else:
        start[r.Index] = p.index.searchsorted(r.entry)
# every verdict's full swing, start to exit (the yardstick pool)
full = {}
for r in V.itertuples():
    p, H, L = PX[r.m]; s0, b = start[r.Index], p.index.searchsorted(r.exit)
    if b < len(p) and b > s0:
        sg = 1 if r.v == "BULLISH" else -1
        full[r.Index] = float(swing(sg, H.to_numpy(float)[s0:b + 1], L.to_numpy(float)[s0:b + 1])[-1])
V["swing"] = pd.Series(full)
KS = (0.75, 1.0, 1.25)
ev, ctl = {}, []
for r in V.itertuples():
    p, H, L = PX[r.m]; px = p.to_numpy(float)
    s0, a, b = start[r.Index], p.index.searchsorted(r.entry), p.index.searchsorted(r.exit)
    if b >= len(px) or s0 < 253 or b - a < 3:
        continue
    sg = 1 if r.v == "BULLISH" else -1
    wk = 100 * float(np.diff(np.log(px[s0 - 252:s0])).std() * np.sqrt(5))
    win = V[(V.m == r.m) & (V.v == r.v) & (V.r > 0) & (V.exit < r.entry)].swing.dropna()
    h = "2019-22" if r.t < pd.Timestamp("2023") else "2023-26"
    rest = lambda j: sg * (px[b] / px[j] - 1) * 100 / wk
    ctl.append({"h": h, "sec": r.sector, "rest": float(np.mean([rest(j) for j in range(a, b, 5)]))})
    if len(win) < 5:
        continue
    Y = float(win.median())
    Hs, Ls = H.to_numpy(float)[s0:b + 1], L.to_numpy(float)[s0:b + 1]
    sw = swing(sg, Hs, Ls)
    top = np.maximum.accumulate(Hs) if sg > 0 else np.minimum.accumulate(Ls)
    for kk in KS:
        for mode in ("any", "gave", "hold"):
            for j in range(max(a, s0 + 1), b):
                i = j - s0
                if sw[i] < kk * Y:
                    continue
                # given back half of the swing: the close is below the middle of the swing (from its low to its top)
                lo_ = top[i] / (1 + sw[i] / 100) if sg > 0 else top[i] * (1 + sw[i] / 100)
                mid = (top[i] + lo_) / 2
                gave = px[j] <= mid if sg > 0 else px[j] >= mid
                if mode == "any" or (mode == "gave") == bool(gave):
                    ev.setdefault((kk, mode), []).append({"m": r.m, "sec": r.sector, "h": h, "rest": rest(j), "t": str(p.index[j].date())})
                    break


def st(x):
    v = np.asarray(x.rest, float)
    if len(v) < 3:
        return {"n": int(len(v))}
    return {"n": int(len(v)), "won": round(100 * float((v > 0).mean()), 1), "avg": round(float(v.mean()), 2),
            "t": round(float(v.mean() / v.std(ddof=1) * np.sqrt(len(v))), 2),
            "2019-22": round(float(x[x.h == "2019-22"].rest.mean()), 2), "2023-26": round(float(x[x.h == "2023-26"].rest.mean()), 2)}


Cn = pd.DataFrame(ctl)
out = {"control": st(Cn), **{f"control {s}": st(g) for s, g in Cn.groupby("sec")}}
print("control any 5th day:", out["control"])
print("   by sector:", {s: out[f"control {s}"]["avg"] for s in Cn.sec.unique()})
for (kk, mode), rows in sorted(ev.items()):
    E = pd.DataFrame(rows)
    out[f"{kk} {mode}"] = {"all": st(E), **{s: st(g) for s, g in E.groupby("sec")}}
    print(f">= {kk:.2f} x winners' swing, {mode:4s}: {out[f'{kk} {mode}']['all']}")
    print("      ", {s: (v.get("avg"), v["n"], v.get("2019-22"), v.get("2023-26")) for s, v in out[f"{kk} {mode}"].items() if s != "all"})
json.dump(out, open(os.path.join(HERE, "..", "data", "research", f"swing_hl{'' if START == 'report' else '_release'}.json"), "w"), indent=1)
