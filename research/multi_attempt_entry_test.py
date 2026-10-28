"""RESULT 2026-10-27: tight-stop re-entries on daily zones BEAT the one-shot verdict entry in R, both halves, all 8
years. Daily zone, stop beyond the distal edge (median 0.32 wk-ATR), hold to the verdict exit, re-enter after a stop:
1.93 attempts/verdict, 30% won, +0.408R per attempt, +0.790R per verdict (t 4.3; 19-22 +0.725, 23-26 +0.864) vs the
verdict entry +0.275R (t 3.6). In % it is +1.29 vs +1.02 per verdict (same move, less risk). Robustness: ALL of the
surplus is runners - median attempt -1R, top 10% of attempts = 189% of the R; capped at 5R it equals the verdict entry
(+0.25), capped at 3R negative -> only works if winners are held to the verdict exit. Positive every year 2019-26.
Costs: 0.02 wk-ATR per attempt +0.70, 0.05 +0.47 (verdict entry +0.21 at the same cost), 0.10 +0.08 (below). Stop
buffers: distal+0.1 wk +0.54, fixed 0.5 wk +0.49 - monotone, the tightest is best in R. Cap at 3 attempts = same.
Chandelier trail 1.0 wk-ATR KILLS every variant (-0.1 to +0.2R): do not trail, hold. PDH re-entries +0.49, zone|PDH
+0.66 - the close trigger dilutes the zone. Sectors: indices +1.97, agri +0.98, metals +0.72, FX +0.42 (in % FX flat
+0.11), energy +0.20 (< verdict +0.36). 4h zones (10 mkts): stop 0.12 wk-ATR, 4.6 attempts, 17% won, +2.25R/verdict
(both halves, +1.54 at 0.02 cost) vs +0.15 verdict; in % +0.95 vs +0.29 but 19-22 only +0.19% - huge R from tiny stops,
execution-sensitive. Entry-bar stop check (limit fill then same bar through the zone) IS applied.
V4 INDICATOR (user's shipping Pine, otc_zones_v4 port, 2026-10-28): same mechanics (live leg-out+2, wick through
distal = broken, first touch of body proximal, stop beyond distal) = WORSE than canon: daily +0.308R/verdict (t 1.9;
19-22 +0.19, 23-26 +0.45) vs +0.790; 1.07 attempts in 69% of verdicts (canon 1.93 / 92%), stop 0.24 wk-ATR, 22% won;
sectors: only metals better (+1.85 vs +0.72), energy -0.20 and FX -0.02 negative, agri +0.13, indices +0.40. 4h: V4
+1.72 vs +2.25, 19-22 % negative. Per-verdict corr with canon only +0.45 (different zones). Keep canon.
Several tight-stop attempts per board verdict (2026-10-27). The user enters only with TA (a daily / 4h demand or
supply zone, or a close beyond the previous day's extreme), never at the verdict itself, and re-enters after a stop.
Per verdict (current walk-forward verdict.json, entry day to exit day), in the verdict's direction, while flat:
  D zone   fresh daily OTC canon zone (body40, mult OFF, base 1-6; live next day, dead after 52 weeks): limit at the
           proximal edge, stop beyond the DISTAL edge (floor 0.10 weekly ATR)
  H4 zone  the same on 4h bars (LSE 4h; zone live from the next bar, dead after 13 weeks), stops resolved on 4h bars;
           only the 10 markets with 4h history back to 2019 (6E 6B 6J 6S 6A 6C GC SI ES NQ)
  PDH      daily close beyond the previous day's extreme, entered at that close, stop beyond that day
  D|PDH    daily zone or PDH, whichever comes first while flat
  H4|PDH   4h zone or PDH (daily close) on the 10 markets
Exit: the verdict exit close (hold), or a chandelier trail (1.0 weekly ATR from the best close since entry, checked on
closes, exit next open) - whichever first. Stop first when a bar touches stop and target region ambiguously (daily).
After a stop the next trigger re-enters; attempts capped at 'all' and at 3. No costs.
Control: ONE entry at the verdict close, stop 0.75 weekly ATR, hold (the board's own number: +0.275R).
Cost column: 0.02 weekly ATR per attempt round trip (about 2 ticks of spread+slippage on a 1%-week market), in R.
Scored per verdict: sum of R (each attempt risks 1R), attempts, sum of % (constant notional), and R per attempt.
Board direction (yen, franc, CAD inverted)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic"); sys.path.insert(0, "/Users/Niklas/bias-board/bias")
from backtest.sd_fx_legout_atr import canon_meta
from backtest.sd_otc_challenger import otc_zones_v4
import core as C
BB = "/Users/Niklas/bias-board"
H4 = "/Users/Niklas/supply_demand_intraday/data_cache/lse_4h"
H4_OK = ["6E", "6B", "6J", "6S", "6A", "6C", "GC", "SI", "ES", "NQ"]
V = pd.DataFrame(json.load(open(f"{BB}/data/research/verdict.json"))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
V["sg"] = np.where(V.v == "BULLISH", 1, -1)
TRAIL = 1.0


def inv(d):
    return pd.DataFrame({"open": 1 / d.open, "high": 1 / d.low, "low": 1 / d.high, "close": 1 / d.close}, index=d.index)


def zone_events(bars, live_lag, dead, O, H, L, idx):
    """(bar index of first touch, side, fill, stop level) for every fresh zone, touched on the resolution bars."""
    out = []
    for (side, cb, top, bot, lo, a) in canon_meta(bars, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        t0 = bars.index[cb] + live_lag; t1 = t0 + dead
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        for i in range(idx.searchsorted(t0), len(idx)):
            if idx[i] > t1:
                break
            if (L[i] <= prox) if sg > 0 else (H[i] >= prox):
                out.append((i, sg, min(O[i], prox) if sg > 0 else max(O[i], prox), dist))
                break
    return sorted(out)


def v4_events(bars, dead, O, H, L, idx):
    """OTC V4 (user's shipping Pine, 2026-08-02): zone live from leg-out bar + 2 (skipN = 1), broken by a WICK through
    the distal on any later bar (then no trade), first touch of the body proximal = limit fill, stop beyond the distal."""
    out = []
    bo, bh, bl, bc = (bars[c].to_numpy(float) for c in ("open", "high", "low", "close"))
    for (cb, top, bot, isSup) in otc_zones_v4(bo, bh, bl, bc):
        sg = -1 if isSup else 1
        t0 = bars.index[cb]; t1 = t0 + dead
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        for i in range(idx.searchsorted(t0, "right") + 1, len(idx)):
            if idx[i] > t1:
                break
            touched = (L[i] <= prox) if sg > 0 else (H[i] >= prox)
            if touched:
                out.append((i, sg, min(O[i], prox) if sg > 0 else max(O[i], prox), dist))
                break
            if (L[i] < dist) if sg > 0 else (H[i] > dist):       # wick through the distal before any touch: broken
                break
    return sorted(out)


def run(events, a, b, sg, O, H, L, Cc, watr_at, cap, trail):
    """Walk the verdict [a, b]: take events (i, fill, stop) in order while flat; hold to b or trail. Returns attempts."""
    res, i0, n = [], a, 0
    ev = [e for e in events if a <= e[0] < b]
    for (i, fill, stop, kind) in ev:
        if i < i0 or (cap and n >= cap):
            continue
        R = sg * (fill - stop)
        R = max(R, 0.10 * watr_at(i))
        stop = fill - sg * R
        best, out, j_end = fill, None, None
        if kind == "z" and ((L[i] <= stop) if sg > 0 else (H[i] >= stop)):   # limit fill, same bar through the stop
            out, j_end = -1.0, i
        for j in range(i + 1, b + 1 if out is None else i + 1):
            if trail:
                ts = best - sg * trail * watr_at(j)
                stop = max(stop, ts) if sg > 0 else min(stop, ts)
            if (O[j] <= stop) if sg > 0 else (O[j] >= stop):
                out, j_end = sg * (O[j] - fill) / R, j; break
            if (L[j] <= stop) if sg > 0 else (H[j] >= stop):
                out, j_end = -1.0, j; break
            best = max(best, Cc[j]) if sg > 0 else min(best, Cc[j])
        if out is None:
            j_end, out = b, sg * (Cc[b] - fill) / R
        res.append((out, 100 * out * R / fill, R, i, j_end))
        i0, n = j_end + 1, n + 1
    return res


rows = []
for k, meta in C.M.items():
    if k in ("DX", "KC", "LE"):
        continue
    d = pd.read_csv(f"{BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]
    d = d[(d.index.dayofweek < 5) & (d.high > d.low) & (d.index >= "2012-01-01")]
    if meta[2]:
        d = inv(d)
    w = d.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    wtr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
    watr = wtr.ewm(alpha=1 / 14, adjust=False).mean()
    O, H, L, Cc, idx = d.open.to_numpy(), d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), d.index
    wa_d = watr.reindex(idx, method="ffill").shift(1).bfill().to_numpy()     # last completed week
    dz = zone_events(d, pd.Timedelta(days=1), pd.Timedelta(weeks=52), O, H, L, idx)
    v4 = v4_events(d, pd.Timedelta(weeks=52), O, H, L, idx)
    pdh = [(i, 1, Cc[i], L[i]) for i in range(1, len(idx)) if Cc[i] > H[i - 1]] + \
          [(i, -1, Cc[i], H[i]) for i in range(1, len(idx)) if Cc[i] < L[i - 1]]
    pdh.sort()
    # 4h
    h4 = None
    if k in H4_OK:
        h = pd.read_csv(f"{H4}/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
        h = h[~h.index.duplicated()].sort_index(); h = h[(h.high > h.low) & (h.index >= "2016-01-01")]
        if meta[2]:
            h = inv(h)
        hw = h.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        htr = np.maximum(hw.high - hw.low, np.maximum(abs(hw.high - hw.close.shift()), abs(hw.low - hw.close.shift())))
        hwatr = htr.ewm(alpha=1 / 14, adjust=False).mean()
        hO, hH, hL, hC, hidx = h.open.to_numpy(), h.high.to_numpy(), h.low.to_numpy(), h.close.to_numpy(), h.index
        wa_h = hwatr.reindex(hidx, method="ffill").shift(1).bfill().to_numpy()
        hz = zone_events(h, pd.Timedelta(hours=4), pd.Timedelta(weeks=13), hO, hH, hL, hidx)
        hv4 = v4_events(h, pd.Timedelta(weeks=13), hO, hH, hL, hidx)
        # daily PDH closes mapped onto the 4h bars: the last 4h bar of that date, stop level from the daily bar
        hdates = hidx.normalize()
        last_bar = pd.Series(np.arange(len(hidx)), index=hdates).groupby(level=0).max()
        hpdh = []
        for (i, s, f, st) in pdh:
            dd = idx[i].normalize()
            if dd in last_bar.index:
                j = int(last_bar[dd]); hpdh.append((j, s, hC[j], st * (hC[j] / Cc[i])))   # scale the daily stop to the 4h feed
        hpdh.sort()
        h4 = (hO, hH, hL, hC, hidx, wa_h, hz, hpdh, hv4)

    for r in V[V.m == k].itertuples():
        a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
        if b >= len(idx) or b <= a or idx[a] != r.entry:
            continue
        sg = r.sg
        wd = lambda i: wa_d[i]
        base = run([(a, Cc[a], Cc[a] - sg * 0.75 * wa_d[a], "c")], a, b, sg, O, H, L, Cc, wd, 1, 0)
        sets = {"D zone": [(i, f, s, "z") for i, s_, f, s in dz if s_ == sg],
                "PDH": [(i, f, s, "c") for i, s_, f, s in pdh if s_ == sg]}
        sets["D|PDH"] = sorted(sets["D zone"] + sets["PDH"])
        sets["V4 zone"] = [(i, f, s, "z") for i, s_, f, s in v4 if s_ == sg]
        sets["V4|PDH"] = sorted(sets["V4 zone"] + sets["PDH"])
        sets["D zone +0.1wk"] = [(i, f, s - sg * 0.10 * wa_d[i], "z") for i, s_, f, s in dz if s_ == sg]
        sets["D zone 0.5wk"] = [(i, f, f - sg * 0.50 * wa_d[i], "z") for i, s_, f, s in dz if s_ == sg]
        for nm, ev in sets.items():
            for cap in (0, 3):
                for trail in (0, TRAIL):
                    for att in (run(ev, a, b, sg, O, H, L, Cc, wd, cap, trail) or [None]):
                        rows.append({"k": k, "sector": meta[3], "t": r.t, "vid": r.Index, "set": nm, "cap": cap, "trail": trail,
                                     "r": att[0] if att else 0.0, "pct": att[1] if att else 0.0,
                                     "stop_wk": att[2] / wa_d[att[3]] if att else np.nan, "took": att is not None, "tf": "D"})
        for att in base:
            rows.append({"k": k, "sector": meta[3], "t": r.t, "vid": r.Index, "set": "verdict", "cap": 1, "trail": 0,
                         "r": att[0], "pct": att[1], "stop_wk": 0.75, "took": True, "tf": "D"})
        if h4 is not None:
            hO, hH, hL, hC, hidx, wa_h, hz, hpdh, hv4 = h4
            ha, hb = hidx.searchsorted(r.entry), hidx.searchsorted(r.exit + pd.Timedelta(days=1)) - 1
            if hb >= len(hidx) or hb <= ha or hidx[hb] < r.entry:
                continue
            wh = lambda i: wa_h[i]
            hs = {"H4 zone": [(i, f, s, "z") for i, s_, f, s in hz if s_ == sg],
                  "PDH on 4h": [(i, f, s, "c") for i, s_, f, s in hpdh if s_ == sg]}
            hs["H4|PDH"] = sorted(hs["H4 zone"] + hs["PDH on 4h"])
            hs["H4 V4 zone"] = [(i, f, s, "z") for i, s_, f, s in hv4 if s_ == sg]
            hbase = run([(ha, hC[ha], hC[ha] - sg * 0.75 * wa_h[ha], "c")], ha, hb, sg, hO, hH, hL, hC, wh, 1, 0)
            for nm, ev in hs.items():
                for cap in (0, 3):
                    for trail in (0, TRAIL):
                        for att in (run(ev, ha, hb, sg, hO, hH, hL, hC, wh, cap, trail) or [None]):
                            rows.append({"k": k, "sector": meta[3], "t": r.t, "vid": r.Index, "set": nm, "cap": cap, "trail": trail,
                                         "r": att[0] if att else 0.0, "pct": att[1] if att else 0.0,
                                         "stop_wk": att[2] / wa_h[att[3]] if att else np.nan, "took": att is not None, "tf": "H4"})
            for att in hbase:
                rows.append({"k": k, "sector": meta[3], "t": r.t, "vid": r.Index, "set": "verdict (4h feed)", "cap": 1, "trail": 0,
                             "r": att[0], "pct": att[1], "stop_wk": 0.75, "took": True, "tf": "H4"})
    print(k, end=" ", flush=True)
T = pd.DataFrame(rows)
T.to_csv(f"{BB}/data/research/multi_attempt_entry.csv", index=False)
print()


def tstat(x):
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan


def show(G, title):
    print(f"\n=== {title} ===")
    print(f"{'entry':18s} {'cap':>3s} {'trail':>5s} | {'verd':>4s} {'att/v':>5s} {'stop':>5s} | per attempt: {'won':>5s} {'R':>6s} "
          f"| per VERDICT: {'sumR':>6s} {'t':>5s} {'19-22':>6s} {'23-26':>6s} {'%':>6s} {'19-22':>6s} {'23-26':>6s} | cost .02wk {'sumR':>6s}")
    for (nm, cap, trail), g in G.groupby(["set", "cap", "trail"], sort=False):
        g = g.assign(rc=g.r - np.where(g.took, 0.02 / g.stop_wk.clip(lower=0.1), 0.0))
        pv = g.groupby("vid").agg(r=("r", "sum"), pct=("pct", "sum"), n=("took", "sum"), t=("t", "first"), rc=("rc", "sum"))
        tk = g[g.took]
        e, l = pv[pv.t < "2023"], pv[pv.t >= "2023"]
        print(f"{nm:18s} {cap or 'all':>3} {trail:5.1f} | {len(pv):4d} {tk.groupby('vid').size().reindex(pv.index).fillna(0).mean():5.2f} "
              f"{tk.stop_wk.median():5.2f} | {100*(tk.r>0).mean():5.1f} {tk.r.mean():+6.3f} | {pv.r.mean():+6.3f} {tstat(pv.r):+5.1f} "
              f"{e.r.mean():+6.3f} {l.r.mean():+6.3f} {pv.pct.mean():+6.2f} {e.pct.mean():+6.2f} {l.pct.mean():+6.2f} | {pv.rc.mean():+6.3f} ({100*(tk.rc>0).mean():.0f}%)")


order = ["verdict", "D zone", "V4 zone", "D zone +0.1wk", "D zone 0.5wk", "PDH", "D|PDH", "V4|PDH", "verdict (4h feed)", "H4 zone", "H4 V4 zone", "PDH on 4h", "H4|PDH"]
T["set"] = pd.Categorical(T["set"], order)
T = T.sort_values(["set", "cap", "trail"])
show(T[T.tf == "D"], "DAILY feed, 21 markets")
show(T[T.tf == "H4"], "4h feed, 10 markets (6E 6B 6J 6S 6A 6C GC SI ES NQ)")
# robustness of the daily-zone result: R cap, top-10 share, yearly, costs
print("\n=== DAILY zone, hold, all attempts: robustness ===")
g = T[(T["set"] == "D zone") & (T.cap == 0) & (T.trail == 0)]
tk = g[g.took].copy()
for capR in (None, 10, 5, 3):
    r = tk.r.clip(upper=capR) if capR else tk.r
    pv = r.groupby(tk.vid).sum()
    print(f"  R capped at {capR or 'none':>4}: per attempt {r.mean():+.3f}  per verdict {pv.mean():+.3f}  t {tstat(pv):+.1f}")
srt = tk.r.sort_values(ascending=False)
print(f"  top 10 attempts = {100*srt.head(10).sum()/srt.sum():.0f}% of total R, top 10% of attempts = {100*srt.head(len(srt)//10).sum()/srt.sum():.0f}%; "
      f"median attempt {tk.r.median():+.2f}R, biggest {srt.iloc[0]:+.1f}R")
yr = tk.groupby(tk.t.dt.year).r.agg(["sum", "count"]); base = T[T["set"] == "verdict"]; by = base.groupby(base.t.dt.year).r.sum()
print("  year:      " + "  ".join(f"{y}" for y in yr.index))
print("  zone sumR: " + "  ".join(f"{v:+.0f}" for v in yr["sum"]))
print("  verdict R: " + "  ".join(f"{v:+.0f}" for v in by.reindex(yr.index)))
for cst in (0.02, 0.05, 0.10):
    rc = tk.r - cst / tk.stop_wk.clip(lower=0.1); pv = rc.groupby(tk.vid).sum()
    print(f"  cost {cst:.2f} wkATR per attempt: per attempt {rc.mean():+.3f}  per verdict {pv.mean():+.3f}  (verdict entry at same cost {base.r.mean() - cst/0.75:+.3f})")
sw = tk.stop_wk
print(f"  stop size: median {sw.median():.2f} wkATR, p25 {sw.quantile(.25):.2f}, p75 {sw.quantile(.75):.2f}; at the 0.10 floor: {100*(sw<=0.1001).mean():.0f}% of attempts")
for lo, hi in ((0, 0.2), (0.2, 0.4), (0.4, 9)):
    q = tk[(sw > lo) & (sw <= hi)]
    print(f"    stop {lo:.1f}-{hi:.1f} wkATR: n {len(q)}  won {100*(q.r>0).mean():.0f}%  avg {q.r.mean():+.3f}R  avg move {q.pct.mean():+.2f}%")
for sec, g in T[T.tf == "D"].groupby("sector"):
    show(g[((g.cap == 0) & (g.trail == 0) & g["set"].isin(["D zone", "V4 zone", "PDH"])) | (g["set"] == "verdict")], f"DAILY {sec}: hold, all attempts")
print("\n=== V4 vs canon, daily zone, hold, all attempts: per verdict ===")
pv = {nm: T[(T["set"] == nm) & (T.cap == 0) & (T.trail == 0)].groupby("vid").agg(r=("r", "sum"), n=("took", "sum")) for nm in ("D zone", "V4 zone")}
j = pv["D zone"].join(pv["V4 zone"], lsuffix="_c", rsuffix="_v")
print(f"  attempts: canon {j.n_c.sum():.0f}, V4 {j.n_v.sum():.0f}; verdicts with an entry: canon {(j.n_c>0).mean()*100:.0f}%, V4 {(j.n_v>0).mean()*100:.0f}%; "
      f"corr of per-verdict R {j.r_c.corr(j.r_v):+.2f}; V4 better in {100*(j.r_v>j.r_c).mean():.0f}% of verdicts, equal {100*(j.r_v==j.r_c).mean():.0f}%")
