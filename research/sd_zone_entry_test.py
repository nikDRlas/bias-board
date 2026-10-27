"""RESULT 2026-10-27: A) the board verdict is a real filter for OTC zone trades: all zones 49.8% / -0.00R (coin flip);
WITH verdict weekly +0.145R 57% (t3.1, both halves +), daily +0.128R 56% (t6.2); AGAINST -0.08 / -0.13R. Indices +0.51R
(75% won) weekly, metals +0.24, FX +0.20 / +0.14; agriculture and energy nothing on weekly. B) as the ENTRY: weekly zone
in 55% of verdicts (median 9 days later), better price (+1.69% vs +1.40%, 59% vs 55% won) but the 45% of verdicts that
never pull back to a weekly zone are the best ones (+2.21%, 64%); daily zone in 92% (median 3 days), result ~ same as
the verdict's own entry (+1.70% vs +1.88%).
Board verdicts x OTC S/D zones (2026-10-27). Two questions on the CURRENT walk-forward verdicts (verdict.json):
  A) zone trades (canon OTC zones: body40, mult OFF, base 1-6; first touch only, limit at the proximal, stop 0.75 x
     weekly ATR from the fill, target 1R, stop first, 130-day cap) WITH an active board verdict in the zone's
     direction vs NO verdict vs AGAINST the verdict. Weekly zones (W-FRI bars, live from the Monday after the leg-out,
     dead after 104 weeks) and daily zones (live from the next day, dead after 52 weeks).
  B) zone as the ENTRY for a verdict: the first fresh zone touched in the verdict's direction between the verdict's
     entry and its exit; result from the zone fill to the verdict exit vs the verdict's own result on the same verdicts.
21 markets (no OHLC history for DX, coffee, cattle). Board direction (yen, franc, CAD inverted)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic"); sys.path.insert(0, "/Users/Niklas/bias-board/bias")
from backtest.sd_fx_legout_atr import canon_meta
import core as C
BB = "/Users/Niklas/bias-board"
V = pd.DataFrame(json.load(open(f"{BB}/data/research/verdict.json"))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
V["sg"] = np.where(V.v == "BULLISH", 1, -1)


def zones(bars, tf):
    zs = canon_meta(bars, mult_on=False, body_min=40.0, base_min=1)
    tr = np.maximum(bars.high - bars.low, np.maximum(abs(bars.high - bars.close.shift()), abs(bars.low - bars.close.shift())))
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    out = []
    for (side, cb, top, bot, lo, a) in zs:
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        live = bars.index[cb] + pd.Timedelta(days=3 if tf == "W" else 1)
        out.append((sg, live, live + pd.Timedelta(weeks=104 if tf == "W" else 52), top, bot, cb))
    return out, atr


A, B = [], []
for k, meta in C.M.items():
    if k in ("DX", "KC", "LE"):
        continue
    d = pd.read_csv(f"{BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]
    d = d[(d.index.dayofweek < 5) & (d.high > d.low) & (d.index >= "2012-01-01")]
    if meta[2]:
        d = pd.DataFrame({"open": 1 / d.open, "high": 1 / d.low, "low": 1 / d.high, "close": 1 / d.close}, index=d.index)
    w = d.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    wtr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
    watr = pd.Series(wtr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy(), index=w.index)
    O, H, L, Cc, idx = d.open.to_numpy(), d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), d.index
    vk = V[V.m == k]
    for tf, bars in (("W", w), ("D", d)):
        zs, _ = zones(bars, tf)
        touches = []                                             # (fill day index, sg, fill, R)
        for sg, live, dead, top, bot, cb in zs:
            prox = top if sg > 0 else bot
            for i in range(idx.searchsorted(live), len(idx)):
                if idx[i] > dead:
                    break
                if not (L[i] <= prox if sg > 0 else H[i] >= prox):
                    continue
                fill = min(O[i], prox) if sg > 0 else max(O[i], prox)
                aw = watr[watr.index <= idx[i]].iloc[-1]
                touches.append((i, sg, fill, 0.75 * aw))
                break
        touches.sort()
        for i, sg, fill, R in touches:
            if idx[i] < pd.Timestamp("2019-01-07") or R <= 0:
                continue
            stop, tp, res = fill - sg * R, fill + sg * R, None
            for j in range(i, min(len(idx), i + 130)):
                hs = L[j] <= stop if sg > 0 else H[j] >= stop
                ht = H[j] >= tp if sg > 0 else L[j] <= tp
                if j == i:
                    ht = ht and (Cc[j] >= tp if sg > 0 else Cc[j] <= tp)
                if hs:
                    res = -1.0; break
                if ht:
                    res = 1.0; break
            if res is None:
                if i + 129 >= len(idx):
                    continue
                res = sg * (Cc[i + 129] - fill) / R
            g = vk[(vk.entry <= idx[i]) & (vk.exit >= idx[i])]
            tag = "no verdict" if not len(g) else ("with verdict" if g.iloc[-1].sg == sg else "against verdict")
            A.append({"k": k, "tf": tf, "d": idx[i], "r": res, "tag": tag, "sector": meta[3]})
        # B: the first zone touch inside each verdict, in its direction
        for r in vk.itertuples():
            a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
            if b >= len(idx) or b <= a:
                continue
            hit = [(i, fill, R) for i, sg, fill, R in touches if sg == r.sg and a <= i < b]
            own = 100 * r.sg * (Cc[b] / Cc[a] - 1)
            if not hit:
                B.append({"k": k, "tf": tf, "t": r.t, "own": own, "zone": None, "days": None, "sector": r.sector, "basis": r.basis})
                continue
            i, fill, R = hit[0]
            zr = 100 * r.sg * (Cc[b] / fill - 1)
            # stop 0.75 weekly ATR from the zone fill, hit before the verdict exit?
            stop = fill - r.sg * R
            stopped = any((L[j] <= stop) if r.sg > 0 else (H[j] >= stop) for j in range(i, b + 1))
            B.append({"k": k, "tf": tf, "t": r.t, "own": own, "zone": zr, "days": i - a, "stopped": stopped,
                      "zone_R": -1.0 if stopped else r.sg * (Cc[b] - fill) / R, "own_R": r.sg * (Cc[b] - Cc[a]) / R,
                      "sector": r.sector, "basis": r.basis})
    print(k, flush=True)
A, B = pd.DataFrame(A), pd.DataFrame(B)
A.to_csv(f"{BB}/data/research/sd_zone_entry_A.csv", index=False); B.to_csv(f"{BB}/data/research/sd_zone_entry_B.csv", index=False)


def line(g, lab, col="r"):
    if len(g) < 5:
        return
    x = g[col]
    print(f"   {lab:30s} n{len(g):5d} won{100*(x>0).mean():5.1f}% avg{x.mean():+.3f} t{x.mean()/x.std(ddof=1)*np.sqrt(len(x)):+5.1f} | "
          f"19-22 {x[g.t<'2023'].mean() if 't' in g else x[g.d<'2023'].mean():+.3f}  23-26 {x[g.t>='2023'].mean() if 't' in g else x[g.d>='2023'].mean():+.3f}")


for tf, nm in (("W", "WEEKLY zones"), ("D", "DAILY zones")):
    print(f"\n=== A) {nm}: zone trades 1:1, stop 0.75 weekly ATR, by board verdict at the fill (R) ===")
    G = A[A.tf == tf]
    line(G, "all zones")
    for tag in ("with verdict", "no verdict", "against verdict"):
        line(G[G.tag == tag], tag)
    for sec, g in G.groupby("sector"):
        line(g[g.tag == "with verdict"], f"  {sec}: with verdict"); line(g[g.tag == "no verdict"], f"  {sec}: no verdict")
    print(f"\n=== B) {nm} as the ENTRY for a board verdict ===")
    Gb = B[B.tf == tf]
    got = Gb[Gb.zone.notna()]
    print(f"   verdicts {len(Gb)}, with a fresh zone touched in their direction before the exit: {len(got)} "
          f"({100*len(got)/len(Gb):.0f}%), median {got.days.median():.0f} trading days after the verdict entry")
    line(got, "verdict's own result (%)", "own"); line(got, "from the zone fill (%)", "zone")
    line(got, "own entry, R (0.75 wk ATR)", "own_R"); line(got, "zone entry, R (stop 0.75 wk ATR)", "zone_R")
    line(Gb[Gb.zone.isna()], "verdicts WITHOUT a zone: own (%)", "own")
    for sec, g in got.groupby("sector"):
        line(g, f"  {sec}: own (%)", "own"); line(g, f"  {sec}: zone (%)", "zone")
