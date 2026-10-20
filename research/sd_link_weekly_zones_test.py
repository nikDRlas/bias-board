"""Weekly S/D zones on the board's markets, 1:1, traded with / against / without the board's bias.
Pre-set before looking: canon zones (body40, mult OFF, base 1-6) on Mon-Fri weekly bars; zone usable from the week
after its leg-out closes, at most 104 weeks old, FIRST touch only (the touch is the trade); limit at the proximal line
(gap through -> fill at the open); stop A = distal + 0.1 x weekly ATR, stop B = 0.75 x weekly ATR from the fill;
target 1R; daily bars, stop first when both are hit the same day; hold cap 26 weeks (exit at close).
Bias = the board's walk-forward verdict for that market active on the fill day."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic"); sys.path.insert(0, "/Users/Niklas/bias-board/bias")
from backtest.sd_fx_legout_atr import canon_meta
import core as C
BB = "/Users/Niklas/bias-board"
v = pd.DataFrame(json.load(open(f"{BB}/data/research/sdlink_verdicts.json"))["trades"])
v["t"] = pd.to_datetime(v.t); v["exit"] = pd.to_datetime(v.exit)
def bias(k, d):
    g = v[(v.m == k) & (v.t < d) & (v.exit >= d)]
    return 0 if not len(g) else (1 if g.iloc[-1].v == "BULLISH" else -1)
rows = []
for k, meta in C.M.items():
    if k in ("DX", "KC", "LE"): continue                      # live OHLC only from 2025-26
    d = pd.read_csv(f"{BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]
    d = d[(d.index.dayofweek < 5) & (d.index <= "2026-10-16")]
    if meta[2]:                                               # board direction (e.g. yen, not USD/JPY)
        d = pd.DataFrame({"open": 1 / d.open, "high": 1 / d.low, "low": 1 / d.high, "close": 1 / d.close}, index=d.index)
    w = d.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    zs = canon_meta(w, mult_on=False, body_min=40.0, base_min=1)
    tr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    O, H, L, Cc, idx = d.open.to_numpy(), d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), d.index
    for (side, cb, top, bot, lo, a) in zs:
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        live_from = w.index[cb] + pd.Timedelta(days=3)        # Monday after the leg-out week
        a0 = idx.searchsorted(live_from)
        dead = live_from + pd.Timedelta(weeks=104)
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        aw = atr[cb]
        for i in range(a0, len(idx)):
            if idx[i] > dead: break
            touched = L[i] <= prox if sg > 0 else H[i] >= prox
            if not touched: continue
            fill = min(O[i], prox) if sg > 0 else max(O[i], prox)
            if idx[i] < pd.Timestamp("2019-01-07"): break     # first touch before the test period: zone used up
            for stop_lab, stop in (("A zone stop", dist - sg * 0.1 * aw), ("B 0.75 ATR", fill - sg * 0.75 * aw)):
                R = sg * (fill - stop)
                if not np.isfinite(R) or R <= 0:
                    rows.append({"k": k, "sector": meta[3], "d": idx[i], "side": sg, "stop": stop_lab, "r": -1.0}); continue
                tp = fill + sg * R; res = None
                for j in range(i, min(len(idx), i + 130)):
                    hl_stop = L[j] <= stop if sg > 0 else H[j] >= stop
                    hl_tp = H[j] >= tp if sg > 0 else L[j] <= tp
                    if j == i:                                   # fill day: only the part after the fill is unknown
                        hl_tp = hl_tp and (Cc[j] >= tp if sg > 0 else Cc[j] <= tp)
                    if hl_stop: res = -1.0; break
                    if hl_tp: res = 1.0; break
                if res is None:
                    j = min(len(idx) - 1, i + 129)
                    if j < i + 129 and idx[-1] < pd.Timestamp("2026-10-16"): continue
                    if j == len(idx) - 1 and i + 129 >= len(idx): continue   # still open
                    res = sg * (Cc[j] - fill) / R
                rows.append({"k": k, "sector": meta[3], "d": idx[i], "side": sg, "stop": stop_lab, "r": res})
            break
T = pd.DataFrame(rows)
T["b"] = [bias(r.k, r.d) for r in T.itertuples()]
T["tag"] = np.where(T.b == 0, "no bias", np.where(T.b == T.side, "with bias", "against bias"))
T.to_csv("/Users/Niklas/bias-board/data/research/sd_link_weekly_zones.csv", index=False)
def line(g, lab):
    if len(g) < 3: return
    t = g.r.mean() / g.r.std(ddof=1) * np.sqrt(len(g)) if len(g) > 2 else np.nan
    print(f"    {lab:26s} n {len(g):4d} won {100*(g.r>0).mean():5.1f}%  exp {g.r.mean():+.3f}R  t {t:+.1f} | "
          f"19-22 {g[g.d<'2023'].r.mean():+.3f} (n{(g.d<'2023').sum()})  23-26 {g[g.d>='2023'].r.mean():+.3f} (n{(g.d>='2023').sum()})")
for st, G in T.groupby("stop"):
    print(f"\n=== {st} | weekly zones, 21 markets, fills 2019-26, 1:1 ===")
    line(G, "all zones")
    for tag in ("with bias", "no bias", "against bias"): line(G[G.tag == tag], tag)
    for sec, g in G.groupby(G.sector.replace({"Metals": "Metals & energy", "Energy": "Metals & energy"})):
        print(f"  {sec}:"); line(g, "all"); line(g[g.tag == "with bias"], "with bias"); line(g[g.tag == "against bias"], "against bias")
