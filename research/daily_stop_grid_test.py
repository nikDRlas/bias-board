"""RESULT 2026-10-30 (21 markets, 538 verdicts; ratio = R/yr / max drawdown after 0.02 wk-ATR cost): best stop per
entry - canon daily: its zone stop, +0.96 R/verdict (t 5.3, both halves), 56.5 R/yr, DD -32, ratio 1.75 (>=0.25 wk
1.70); V4 daily: >=0.5 wk, +0.31, ratio 1.18 (own 0.59); three-tier B daily: >=0.25 wk, +0.38, ratio 1.22 (own 0.60);
prev-day close: >=0.5 wk, +0.42, ratio 0.96; weekly zones: own, +0.21, ratio 1.43 (wider changes nothing); verdict
+0.29, ratio 1.02. On daily, a stop floor helps the indicators with tiny zones (V4, three-tier), not the canon.
Same 10 markets as the 4h test (238 verdicts): canon daily +1.09 R/verdict, ratio 1.58 vs canon 4h +2.94 (ratio 0.73) /
>=0.25 wk +1.47 (0.74): 4h earns more R, daily far less drawdown per R; V4 and three-tier daily are weak on these 10.
Daily / weekly entries inside board verdicts with wider stops (2026-10-30) - the daily side of the 4h stop grid in
nested_bigbrother_test.py, so the timeframes compare on the same footing. Current verdict.json (macro gate off),
21 markets (no OHLC for DX, coffee, cattle), and the 10 markets that also have 4h data. Board direction.
Entries (each in the verdict's direction, re-enter after a stop, hold to the verdict exit):
  canon D      daily canon zones (body40, mult OFF, base 1-6), live next day, dead after 52 weeks, first touch
  V4 D         OTC V4 (otc_zones_v4), live leg-out + 2, wick through the distal before a touch = broken
  3T B D       three-tier loose zones (detect_zones_pine), first bar overlapping the zone
  prev-day     daily close beyond the previous day's high/low, entered at that close, stop beyond that day
  weekly       weekly canon zones (W-FRI), live the Monday after, dead after 104 weeks
  verdict      the verdict close, 0.75 wk-ATR stop (reference)
Stops: own (zone far edge / the break day), at least 0.25 and 0.5 weekly ATR, fixed 0.75 weekly ATR. A limit fill whose
own bar goes through the stop = -1R. Costs 0.02 weekly ATR per trade for R/yr, max drawdown and ratio."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic"); sys.path.insert(0, "/Users/Niklas/bias-board/bias")
from backtest.sd_fx_legout_atr import canon_meta
from backtest.sd_otc_challenger import otc_zones_v4
sys.path.insert(0, "/Users/Niklas/honestbt")
from honestbt.strategies.three_tier_sd import detect_zones_pine
import core as C
BB = "/Users/Niklas/bias-board"
AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}
TEN = ["6E", "6B", "6J", "6S", "6A", "6C", "GC", "SI", "ES", "NQ"]
V = pd.DataFrame(json.load(open(f"{BB}/data/research/verdict.json"))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
V["sg"] = np.where(V.v == "BULLISH", 1, -1)
YRS = 7.8


def first_touch(sg, prox, dist, start, stop_at, O, H, L, broken_by_wick=False):
    for i in range(start, min(len(O), stop_at)):
        if (L[i] <= prox) if sg > 0 else (H[i] >= prox):
            return i, (min(O[i], prox) if sg > 0 else max(O[i], prox))
        if broken_by_wick and ((L[i] < dist) if sg > 0 else (H[i] > dist)):
            return None
    return None


def entries(d, w, O, H, L, Cc, idx):
    E = {k: [] for k in ("canon D", "V4 D", "3T B D", "prev-day", "weekly")}
    for (side, cb, top, bot, lo, a) in canon_meta(d, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        x = first_touch(sg, prox, dist, cb + 1, cb + 1 + 260, O, H, L)
        if x:
            E["canon D"].append((x[0], sg, x[1], dist, "z"))
    for (cb, top, bot, isSup) in otc_zones_v4(*(d[c].to_numpy(float) for c in ("open", "high", "low", "close"))):
        sg = -1 if isSup else 1
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        x = first_touch(sg, prox, dist, cb + 2, cb + 2 + 260, O, H, L, broken_by_wick=True)
        if x:
            E["V4 D"].append((x[0], sg, x[1], dist, "z"))
    for z in detect_zones_pine(*(d[c].to_numpy(float) for c in ("open", "high", "low", "close"))):
        sg, cb, top, bot = z["side"], z["creation_bar"], z["top"], z["bottom"]
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        m = (L[cb + 1:cb + 261] <= top) & (H[cb + 1:cb + 261] >= bot)
        if m.any():
            i = cb + 1 + int(np.argmax(m))
            E["3T B D"].append((i, sg, min(O[i], prox) if sg > 0 else max(O[i], prox), dist, "z"))
    for i in range(1, len(Cc)):
        if Cc[i] > H[i - 1]:
            E["prev-day"].append((i, 1, Cc[i], L[i], "c"))
        if Cc[i] < L[i - 1]:
            E["prev-day"].append((i, -1, Cc[i], H[i], "c"))
    for (side, cb, top, bot, lo, a) in canon_meta(w, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        t0 = w.index[cb] + pd.Timedelta(days=3)
        s = idx.searchsorted(t0); e = idx.searchsorted(t0 + pd.Timedelta(weeks=104))
        x = first_touch(sg, prox, dist, s, e, O, H, L)
        if x:
            E["weekly"].append((x[0], sg, x[1], dist, "z"))
    return {k: sorted(v) for k, v in E.items()}


def run(events, a, b, sg, O, H, L, Cc, wa):
    res, i0 = [], a
    for (i, fill, stop, kind) in events:
        if i < i0 or i < a or i >= b:
            continue
        R = max(sg * (fill - stop), 0.10 * wa[i]); stop = fill - sg * R
        out = None
        if kind == "z" and ((L[i] <= stop) if sg > 0 else (H[i] >= stop)):
            out, j_end = -1.0, i
        else:
            for j in range(i + 1, b + 1):
                if (O[j] <= stop) if sg > 0 else (O[j] >= stop):
                    out, j_end = sg * (O[j] - fill) / R, j; break
                if (L[j] <= stop) if sg > 0 else (H[j] >= stop):
                    out, j_end = -1.0, j; break
        if out is None:
            j_end, out = b, sg * (Cc[b] - fill) / R
        res.append((out, 100 * out * R / fill, R / wa[i], i))
        i0 = j_end + 1
    return res


STOPS = (("own/zone", 0, False), ("zone, >=0.25 wk", 0.25, False), ("zone, >=0.5 wk", 0.5, False), ("fixed 0.75 wk", 0.75, True))
if __name__ == "__main__":
    rows = []
    for k, meta in C.M.items():
        if k in ("DX", "KC", "LE"):
            continue
        d = pd.read_csv(f"{BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]
        d = d[(d.index.dayofweek < 5) & (d.high > d.low) & (d.index >= "2012-01-01")]
        if meta[2]:
            d = pd.DataFrame({"open": 1 / d.open, "high": 1 / d.low, "low": 1 / d.high, "close": 1 / d.close}, index=d.index)
        w = d.resample("W-FRI").agg(AGG).dropna()
        tr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
        O, H, L, Cc, idx = d.open.to_numpy(), d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), d.index
        wa = tr.ewm(alpha=1 / 14, adjust=False).mean().reindex(idx, method="ffill").shift(1).bfill().to_numpy()
        E = entries(d, w, O, H, L, Cc, idx)
        for r in V[V.m == k].itertuples():
            a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
            if b >= len(idx) or b <= a or idx[a] != r.entry:
                continue
            sg = r.sg
            out = {("verdict", "fixed 0.75 wk"): run([(a, Cc[a], Cc[a] - sg * 0.75 * wa[a], "c")], a, b, sg, O, H, L, Cc, wa)}
            for nm, ev in E.items():
                own = [(i, f, st, kd) for (i, s_, f, st, kd) in ev if s_ == sg]
                for lab, kk, fixed in STOPS:
                    if fixed:
                        evs = [(i, f, f - sg * kk * wa[i], kd) for (i, f, st, kd) in own]
                    else:
                        evs = [(i, f, st if sg * (f - st) >= kk * wa[i] else f - sg * kk * wa[i], kd) for (i, f, st, kd) in own]
                    out[(nm, lab)] = run(evs, a, b, sg, O, H, L, Cc, wa)
            for (nm, lab), res in out.items():
                for x in (res or [None]):
                    rows.append({"k": k, "sector": meta[3], "t": r.t, "vid": r.Index, "set": nm, "stop": lab, "took": x is not None,
                                 "r": x[0] if x else 0.0, "pct": x[1] if x else 0.0, "stop_wk": x[2] if x else np.nan,
                                 "d": idx[x[3]] if x else pd.NaT})
        print(k, end=" ", flush=True)
    print()
    T = pd.DataFrame(rows)
    T.to_csv(f"{BB}/data/research/daily_stop_grid.csv.gz", index=False)


    def tstat(x):
        return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan


    def show(G, title):
        print(f"\n=== {title}: {G.vid.nunique()} verdicts ===")
        print(f"{'entry':10s} {'stop':16s} {'w/ent':>5s} {'stop':>5s} {'won':>4s} {'R/att':>6s} | {'R/verd':>6s} {'t':>5s} {'19-22':>6s} {'23-26':>6s} | "
              f"{'%/verd':>6s} | cost .02: {'R/yr':>6s} {'maxDD':>6s} {'ratio':>5s}")
        for (nm, lab), g in G.groupby(["set", "stop"], sort=False):
            g = g.assign(rc=g.r - np.where(g.took, 0.02 / g.stop_wk.clip(lower=0.1), 0.0))
            pv = g.groupby("vid").agg(r=("r", "sum"), pct=("pct", "sum"), n=("took", "sum"), t=("t", "first"), rc=("rc", "sum"))
            tk = g[g.took].sort_values("d"); e, l = pv[pv.t < "2023"], pv[pv.t >= "2023"]
            eq = tk.rc.groupby(tk.d).sum().cumsum(); dd = (eq - eq.cummax()).min()
            print(f"{nm:10s} {lab:16s} {100*(pv.n>0).mean():4.0f}% {tk.stop_wk.median():5.2f} {100*(tk.r>0).mean():4.0f} {tk.r.mean():+6.3f} | "
                  f"{pv.r.mean():+6.3f} {tstat(pv.r):+5.1f} {e.r.mean():+6.3f} {l.r.mean():+6.3f} | {pv.pct.mean():+6.2f} | "
                  f"{tk.rc.sum()/YRS:+15.1f} {dd:+6.1f} {tk.rc.sum()/YRS/abs(dd):5.2f}")


    show(T, "DAILY / WEEKLY, 21 markets")
    show(T[T.k.isin(TEN)], "DAILY / WEEKLY, the 10 markets with 4h data")
