"""RESULT 2026-10-30 (best stop by ratio = R/yr / max DD after 0.02 wk-ATR cost): canon weekly own zone stop +0.21
R/verdict, 57% of verdicts, ratio 1.43 (wider stops change nothing); V4 weekly own +0.14, only 22% of verdicts, ratio
0.89, 23-26 just +0.05; three-tier B weekly own +0.04, 11% of verdicts, ratio 0.36; prev-week close >=0.5 wk +0.13,
ratio 0.44. Nested weekly->4h (10 markets, own 0.75 ATR4h stop) +1.01 R/verdict (t 2.7; 19-22 +0.29 / 23-26 +1.85),
37% of verdicts, ratio 0.60 - better than its Daily->4h preset (+0.52, ratio 0.17) and positive in both halves.
On the 10 markets: canon weekly ratio 0.99, V4 / three-tier / prev-week weekly about zero.
Weekly-timeframe entries inside board verdicts with the stop grid (2026-10-30), same footing as
daily_stop_grid_test.py (daily-resolved, 21 markets) and nested_bigbrother_test.py (4h-resolved, 10 markets).
  canon W      weekly canon zones (W-FRI, body40, mult OFF, base 1-6), live the Monday after, dead after 104 weeks
  V4 W         OTC V4 on weekly bars, live from the second week after the leg-out, wick through the distal = broken
  3T B W       three-tier loose zones on weekly bars, live the week after, first daily bar overlapping the zone
  prev-week    weekly close beyond the previous week's high/low, entered at that Friday close, stop beyond that week
  Nested W->4h the user's Nested indicator, weekly->4h preset: weekly canon zones arm, 4h canon zones with the p3
               liquidity sweep are the entries, own stop 0.75 x ATR14(4h); 10 markets on the LSE 4h feed
Stops: own, at least 0.25 / 0.5 weekly ATR, fixed 0.75 weekly ATR; re-enter after a stop, hold to the verdict exit;
ratio = R per year / max drawdown after 0.02 wk-ATR cost per trade."""
import sys, os, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import daily_stop_grid_test as DG                     # noqa: E402
import nested_bigbrother_test as NB                   # noqa: E402
from backtest.sd_fx_legout_atr import canon_meta      # noqa: E402
from backtest.sd_otc_challenger import otc_zones_v4   # noqa: E402
from honestbt.strategies.three_tier_sd import detect_zones_pine  # noqa: E402
import core as C                                      # noqa: E402
BB, AGG, V, STOPS, TEN = DG.BB, DG.AGG, DG.V, DG.STOPS, DG.TEN


def weekly_entries(d, w, O, H, L, Cc, idx):
    E = {k: [] for k in ("canon W", "V4 W", "3T B W", "prev-week")}
    day_of = lambda t: idx.searchsorted(t)                       # first daily bar on/after t
    for (side, cb, top, bot, lo, a) in canon_meta(w, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        t0 = w.index[cb] + pd.Timedelta(days=3)
        x = DG.first_touch(sg, prox, dist, day_of(t0), day_of(t0 + pd.Timedelta(weeks=104)), O, H, L)
        if x:
            E["canon W"].append((x[0], sg, x[1], dist, "z"))
    for (cb, top, bot, isSup) in otc_zones_v4(*(w[c].to_numpy(float) for c in ("open", "high", "low", "close"))):
        sg = -1 if isSup else 1
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        t0 = w.index[cb] + pd.Timedelta(days=3)
        # skipN = 1: a test counts from the second week after the leg-out; the wick break counts from the next week
        s_brk, s_tst = day_of(t0), day_of(t0 + pd.Timedelta(weeks=1))
        e = day_of(t0 + pd.Timedelta(weeks=104))
        broke = ((L[s_brk:s_tst] < dist) if sg > 0 else (H[s_brk:s_tst] > dist)).any()
        if broke:
            continue
        x = DG.first_touch(sg, prox, dist, s_tst, e, O, H, L, broken_by_wick=True)
        if x:
            E["V4 W"].append((x[0], sg, x[1], dist, "z"))
    for z in detect_zones_pine(*(w[c].to_numpy(float) for c in ("open", "high", "low", "close"))):
        sg, cb, top, bot = z["side"], z["creation_bar"], z["top"], z["bottom"]
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        t0 = w.index[cb] + pd.Timedelta(days=3)
        s, e = day_of(t0), day_of(t0 + pd.Timedelta(weeks=104))
        m = (L[s:e] <= top) & (H[s:e] >= bot)
        if m.any():
            i = s + int(np.argmax(m))
            E["3T B W"].append((i, sg, min(O[i], prox) if sg > 0 else max(O[i], prox), dist, "z"))
    wc, wh, wl = w.close.to_numpy(), w.high.to_numpy(), w.low.to_numpy()
    for j in range(1, len(w)):
        i = idx.searchsorted(w.index[j] + pd.Timedelta(days=1)) - 1          # last daily bar of that week
        if i < 0:
            continue
        if wc[j] > wh[j - 1]:
            E["prev-week"].append((i, 1, Cc[i], wl[j], "c"))
        if wc[j] < wl[j - 1]:
            E["prev-week"].append((i, -1, Cc[i], wh[j], "c"))
    return {k: sorted(v) for k, v in E.items()}


def grid(E, V_k, idx, O, H, L, Cc, wa, k, meta, h4=False, rows=None):
    for r in V_k.itertuples():
        if h4:
            a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit + pd.Timedelta(days=1)) - 1
            if b >= len(idx) or b <= a or idx[a] < r.entry:
                continue
        else:
            a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
            if b >= len(idx) or b <= a or idx[a] != r.entry:
                continue
        sg = r.sg
        for nm, ev in E.items():
            own = [(i, f, st, kd) for (i, s_, f, st, kd) in ev if s_ == sg]
            for lab, kk, fixed in STOPS:
                if fixed:
                    evs = [(i, f, f - sg * kk * wa[i], kd) for (i, f, st, kd) in own]
                else:
                    evs = [(i, f, st if sg * (f - st) >= kk * wa[i] else f - sg * kk * wa[i], kd) for (i, f, st, kd) in own]
                for x in (DG.run(evs, a, b, sg, O, H, L, Cc, wa) or [None]):
                    rows.append({"k": k, "sector": meta[3], "t": r.t, "vid": r.Index, "set": nm, "stop": lab, "took": x is not None,
                                 "r": x[0] if x else 0.0, "pct": x[1] if x else 0.0, "stop_wk": x[2] if x else np.nan,
                                 "d": idx[x[3]] if x else pd.NaT})


if __name__ == "__main__":
    rows = []
    for k, meta in C.M.items():
        if k in ("DX", "KC", "LE"):
            continue
        d = pd.read_csv(f"{BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]
        d = d[(d.index.dayofweek < 5) & (d.high > d.low) & (d.index >= "2012-01-01")]
        if meta[2]:
            d = NB.inv(d)
        w = d.resample("W-FRI").agg(AGG).dropna()
        tr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
        O, H, L, Cc, idx = d.open.to_numpy(), d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), d.index
        wa = tr.ewm(alpha=1 / 14, adjust=False).mean().reindex(idx, method="ffill").shift(1).bfill().to_numpy()
        grid(weekly_entries(d, w, O, H, L, Cc, idx), V[V.m == k], idx, O, H, L, Cc, wa, k, meta, rows=rows)
        if k in TEN:                                       # Nested weekly->4h on the 4h feed
            hb = pd.read_csv(f"{NB.H4}/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
            hb = hb[~hb.index.duplicated()].sort_index(); hb = hb[(hb.high > hb.low) & (hb.index >= "2016-01-01") & (hb.index.dayofweek < 5)]
            if meta[2]:
                hb = NB.inv(hb)
            hO, hH, hL, hC, hidx = hb.open.to_numpy(), hb.high.to_numpy(), hb.low.to_numpy(), hb.close.to_numpy(), hb.index
            hw = hb.resample("W-FRI").agg(AGG).dropna()
            reg = hidx.searchsorted(hw.index + pd.Timedelta(days=1))     # first 4h bar after the week
            htr = np.maximum(hw.high - hw.low, np.maximum(abs(hw.high - hw.close.shift()), abs(hw.low - hw.close.shift())))
            hwa = htr.ewm(alpha=1 / 14, adjust=False).mean().reindex(hidx, method="ffill").shift(1).bfill().to_numpy()
            fills = NB.nested_entries(hb, hw, reg, hO, hH, hL, hC, NB.wilder(hH, hL, hC))
            E = {"Nested W->4h": [(i, sg, f, st, "z") for (i, sg, f, st, prox, dist) in fills]}
            grid(E, V[V.m == k], hidx, hO, hH, hL, hC, hwa, k, meta, h4=True, rows=rows)
        print(k, end=" ", flush=True)
    print()
    T = pd.DataFrame(rows)
    T.to_csv(f"{BB}/data/research/weekly_stop_grid.csv.gz", index=False)

    def show(G, title):
        print(f"\n=== {title}: {G.vid.nunique()} verdicts ===")
        print(f"{'entry':13s} {'stop':16s} {'w/ent':>5s} {'stop':>5s} {'won':>4s} {'R/att':>6s} | {'R/verd':>6s} {'t':>5s} {'19-22':>6s} {'23-26':>6s} | "
              f"{'%/verd':>6s} | cost .02: {'R/yr':>6s} {'maxDD':>6s} {'ratio':>5s}")
        for (nm, lab), g in G.groupby(["set", "stop"], sort=False):
            g = g.assign(rc=g.r - np.where(g.took, 0.02 / g.stop_wk.clip(lower=0.1), 0.0))
            pv = g.groupby("vid").agg(r=("r", "sum"), pct=("pct", "sum"), n=("took", "sum"), t=("t", "first"), rc=("rc", "sum"))
            tk = g[g.took].sort_values("d"); e, l = pv[pv.t < "2023"], pv[pv.t >= "2023"]
            eq = tk.rc.groupby(tk.d).sum().cumsum(); dd = (eq - eq.cummax()).min() if len(eq) else np.nan
            print(f"{nm:13s} {lab:16s} {100*(pv.n>0).mean():4.0f}% {tk.stop_wk.median():5.2f} {100*(tk.r>0).mean():4.0f} {tk.r.mean():+6.3f} | "
                  f"{pv.r.mean():+6.3f} {DG.tstat(pv.r) if hasattr(DG, 'tstat') else 0:+5.1f} {e.r.mean():+6.3f} {l.r.mean():+6.3f} | {pv.pct.mean():+6.2f} | "
                  f"{tk.rc.sum()/DG.YRS:+15.1f} {dd:+6.1f} {tk.rc.sum()/DG.YRS/abs(dd):5.2f}")

    DG.tstat = lambda x: x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan
    show(T[T.set != "Nested W->4h"], "WEEKLY entries, 21 markets (daily-resolved)")
    show(T[(T.set != "Nested W->4h") & T.k.isin(TEN)], "WEEKLY entries, the 10 markets with 4h data")
    show(T[T.set == "Nested W->4h"], "Nested weekly->4h, 10 markets (4h-resolved)")
