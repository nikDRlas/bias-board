"""RESULT 2026-10-28 (1R per trade, cost 0.02 wk-ATR per trade): DAILY re +41.8 R/yr, maxDD -32.9, ratio 1.27, 30%
won, longest losing run 15, top 5% of trades = 155% of the R; WEEKLY re (weekly zones, re-entry) +12.2 R/yr, maxDD -7.5,
ratio 1.64, 48% won, longest run 6, top 5% = 92%, 8/8 years, both halves (+11.5 / +13.0 R/yr), but only 55% of verdicts
and 41 trades/yr; WEEKLY one-shot +9.3 / -13.1; VERDICT +16.1 / -19.1. At 0.05 cost weekly re 0.98 vs daily 0.50; at no
cost daily 2.03 vs 1.94. Monthly corr daily-weekly 0.34; half/half +27.0 R/yr, DD -16.8, ratio 1.61.
Equity comparison of the entry rules inside board verdicts (2026-10-28), 21 markets, 1R per trade, costs in weekly
ATR per trade (round trip), 2019-26 verdicts (verdict.json). All hold to the verdict exit.
  VERDICT   enter at the verdict close, stop 0.75 wk-ATR, one shot
  WEEKLY    first touch of a fresh weekly canon zone (W-FRI, live Monday after, dead 104 wks), limit at the proximal,
            stop beyond the distal (floor 0.10 wk-ATR), one shot
  WEEKLY re weekly zones with re-entry after a stop (next fresh weekly zone)
  DAILY re  daily canon zones, re-entry after a stop (multi_attempt_entry_test rule)
Same-bar: a limit fill whose own bar goes through the stop = -1R."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic"); sys.path.insert(0, "/Users/Niklas/bias-board/bias")
from backtest.sd_fx_legout_atr import canon_meta
import core as C
BB = "/Users/Niklas/bias-board"
AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}
V = pd.DataFrame(json.load(open(f"{BB}/data/research/verdict.json"))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
V["sg"] = np.where(V.v == "BULLISH", 1, -1)


def zones(bars, lag, dead, O, H, L, idx):
    out = []
    for (side, cb, top, bot, lo, a) in canon_meta(bars, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        t0 = bars.index[cb] + lag; t1 = t0 + dead
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        for i in range(idx.searchsorted(t0), len(idx)):
            if idx[i] > t1:
                break
            if (L[i] <= prox) if sg > 0 else (H[i] >= prox):
                out.append((i, sg, min(O[i], prox) if sg > 0 else max(O[i], prox), dist, "z"))
                break
    return sorted(out)


def run(ev, a, b, sg, O, H, L, Cc, wa, cap):
    res, i0 = [], a
    for (i, fill, stop, kind) in ev:
        if i < i0 or i < a or i >= b or (cap and len(res) >= cap):
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
        res.append((out, R / wa[i], i))
        i0 = j_end + 1
    return res


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
    wz = zones(w, pd.Timedelta(days=3), pd.Timedelta(weeks=104), O, H, L, idx)
    dz = zones(d, pd.Timedelta(days=1), pd.Timedelta(weeks=52), O, H, L, idx)
    for r in V[V.m == k].itertuples():
        a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
        if b >= len(idx) or b <= a or idx[a] != r.entry:
            continue
        sg = r.sg
        sets = {"VERDICT": run([(a, Cc[a], Cc[a] - sg * 0.75 * wa[a], "c")], a, b, sg, O, H, L, Cc, wa, 1),
                "WEEKLY": run([e[:1] + e[2:] for e in wz if e[1] == sg], a, b, sg, O, H, L, Cc, wa, 1),
                "WEEKLY re": run([e[:1] + e[2:] for e in wz if e[1] == sg], a, b, sg, O, H, L, Cc, wa, 0),
                "DAILY re": run([e[:1] + e[2:] for e in dz if e[1] == sg], a, b, sg, O, H, L, Cc, wa, 0)}
        for nm, res in sets.items():
            for x in res:
                rows.append({"k": k, "sector": meta[3], "set": nm, "vid": r.Index, "t": r.t, "d": idx[x[2]], "r": x[0], "stop_wk": x[1]})
T = pd.DataFrame(rows)
T.to_csv(f"{BB}/data/research/entry_equity_compare.csv", index=False)
nv = V[~V.m.isin(["DX", "KC", "LE"])].shape[0]
yrs = 7.8
print(f"{'rule':10s} {'cost':>5s} | {'trades/yr':>9s} {'verd%':>5s} {'stop':>5s} {'won':>4s} {'R/trade':>7s} | {'R/yr':>6s} {'maxDD':>6s} {'R/yr/DD':>7s} "
      f"{'longest L':>9s} {'yrs+':>5s} {'19-22 R/yr':>10s} {'23-26 R/yr':>10s} | top-5% share")
for nm in ("VERDICT", "WEEKLY", "WEEKLY re", "DAILY re"):
    g = T[T.set == nm].sort_values("d")
    for cost in (0.0, 0.02, 0.05):
        r = g.r - cost / g.stop_wk.clip(lower=0.1)
        eq = r.groupby(g.d).sum().cumsum(); dd = (eq - eq.cummax()).min()
        yr = r.groupby(g.d.dt.year).sum()
        cur = mx = 0
        for x in r:
            cur = cur + 1 if x <= 0 else 0; mx = max(mx, cur)
        top = r.sort_values(ascending=False); share = top.head(max(1, len(top) // 20)).sum() / r.sum() if r.sum() > 0 else np.nan
        e, l = r[g.t < "2023"].sum() / 4, r[g.t >= "2023"].sum() / 3.8
        print(f"{nm:10s} {cost:5.2f} | {len(g)/yrs:9.0f} {100*g.vid.nunique()/nv:4.0f}% {g.stop_wk.median():5.2f} {100*(r>0).mean():4.0f} {r.mean():+7.3f} | "
              f"{r.sum()/yrs:+6.1f} {dd:+6.1f} {r.sum()/yrs/abs(dd):7.2f} {mx:9d} {(yr>0).sum():>2d}/{len(yr)} {e:+10.1f} {l:+10.1f} | {100*share:5.0f}%")
    print("            yearly R at 0.02:", {int(y): round(v) for y, v in (g.r - 0.02 / g.stop_wk.clip(lower=0.1)).groupby(g.d.dt.year).sum().items()})
