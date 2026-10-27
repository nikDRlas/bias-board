"""RESULT 2026-10-27: NO, waiting for the close beyond the previous day's extreme does not help. 505 verdicts on 21
markets: verdict entry 59.0% won / +1.77% / +0.275R (fixed 0.75 wk-ATR stop) vs PDH close 56.1% / +1.54% / +0.254R,
worse in both halves on % (19-22 +1.51 -> +1.37, 23-26 +2.07 -> +1.73), and in every sector. It triggers fast (median 2
days, 96% of verdicts) and simply pays a worse price. With the tighter structure stop it reads +0.251R, but 2019-22 is
below the verdict entry's (+0.149 vs +0.169). Weekly zone THEN PDH close (49% of verdicts): +0.93% / +0.201R / +0.282R
struct, worse than the plain weekly-zone limit (+1.69% / +0.285R / +0.303R with the stop beyond the distal edge): the
confirmation gives back the zone's price. Daily zone + PDH: +1.47% / +0.195R, also below the verdict entry.
Board verdict + wait for a daily CLOSE beyond the previous day's extreme (2026-10-27).
Long: first daily close above the previous day's high; short: first close below the previous day's low. Counted from
the verdict's entry day (that day included, so a verdict whose entry day already closed beyond counts as entered at
once) until the verdict exit; enter at that close, exit with the verdict (its exit close). No trigger before the exit
= no trade.
Variants on the CURRENT walk-forward verdicts (verdict.json):
  BASE      the verdict's own entry (close of its entry day)
  PDH       first close beyond the previous day's extreme
  W+PDH     first touch of a fresh weekly OTC zone in the verdict's direction (canon: body40, mult OFF, base 1-6),
            then the first close beyond the previous day's extreme from that touch day on
  D+PDH     the same with a fresh daily zone
  W only    limit fill at the weekly zone's proximal (as in sd_zone_entry_test B), for reference
Structure stop (struct R): beyond the extreme from the verdict entry (BASE: last 5 days; zone variants: from the
touch) to the entry day, at least 0.25 x weekly ATR; W only: beyond the zone's distal edge.
Measured as % to the verdict exit, in R with a stop 0.75 x weekly ATR from the entry (stop first; -1R if hit
before the exit). "per verdict" counts a verdict without an entry as 0 (what the rule earns from the whole set).
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


def zone_touches(bars, tf, idx, O, H, L):
    """First touch of each fresh zone on the daily bars: (day index, side, fill at the proximal)."""
    out = []
    for (side, cb, top, bot, lo, a) in canon_meta(bars, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        live = bars.index[cb] + pd.Timedelta(days=3 if tf == "W" else 1)
        dead = live + pd.Timedelta(weeks=104 if tf == "W" else 52)
        prox = top if sg > 0 else bot
        for i in range(idx.searchsorted(live), len(idx)):
            if idx[i] > dead:
                break
            if L[i] <= prox if sg > 0 else H[i] >= prox:
                out.append((i, sg, min(O[i], prox) if sg > 0 else max(O[i], prox), bot if sg > 0 else top))
                break
    return sorted(out)


rows = []
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
    zt = {tf: zone_touches(bars, tf, idx, O, H, L) for tf, bars in (("W", w), ("D", d))}

    def pdh(i, b, sg):
        """First day j in [i, b) whose close is beyond the previous day's extreme."""
        for j in range(max(i, 1), b):
            if (Cc[j] > H[j - 1]) if sg > 0 else (Cc[j] < L[j - 1]):
                return j
        return None

    def res(j, px, b, sg, s0=None, distal=None):
        R = 0.75 * watr[watr.index < idx[j]].iloc[-1]          # last completed week
        stop = px - sg * R
        hit = any((L[x] <= stop) if sg > 0 else (H[x] >= stop) for x in range(j + 1, b + 1))
        # structure stop: beyond the extreme from s0 (verdict entry or zone touch) to the entry day, at least 0.25 x weekly ATR
        s0 = j if s0 is None else s0
        ext = L[s0:j + 1].min() if sg > 0 else H[s0:j + 1].max()
        if distal is not None:                                 # zone limit fill: stop beyond the zone's distal edge
            ext = distal
        Rs = max(sg * (px - ext), 0.25 * R / 0.75)
        st = px - sg * Rs
        hs = any((L[x] <= st) if sg > 0 else (H[x] >= st) for x in range(j + 1, b + 1))
        return 100 * sg * (Cc[b] / px - 1), (-1.0 if hit else sg * (Cc[b] - px) / R), j, (-1.0 if hs else sg * (Cc[b] - px) / Rs)

    for r in V[V.m == k].itertuples():
        a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
        if b >= len(idx) or b <= a or idx[a] != r.entry:
            continue
        sg, out = r.sg, {}
        out["BASE"] = res(a, Cc[a], b, sg, max(a - 5, 0))
        j = pdh(a, b, sg)
        out["PDH"] = res(j, Cc[j], b, sg, a) if j is not None else None
        for tf in ("W", "D"):
            hit = [(i, f, dl) for i, s, f, dl in zt[tf] if s == sg and a <= i < b]
            j = pdh(hit[0][0], b, sg) if hit else None
            out[f"{tf}+PDH"] = res(j, Cc[j], b, sg, hit[0][0]) if j is not None else None
            if tf == "W":
                out["W only"] = res(hit[0][0], hit[0][1], b, sg, distal=hit[0][2]) if hit else None
        for v, x in out.items():
            rows.append({"k": k, "t": r.t, "sector": r.sector, "basis": r.basis, "var": v, "took": x is not None,
                         "pct": x[0] if x else 0.0, "R": x[1] if x else 0.0, "wait": (x[2] - a) if x else np.nan, "Rs": x[3] if x else 0.0,
                         "board_r": r.r})
    print(k, end=" ", flush=True)
T = pd.DataFrame(rows)
T.to_csv(f"{BB}/data/research/pdh_close_entry.csv", index=False)
print()


def tstat(x):
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan


def show(G, lab):
    print(f"\n=== {lab} ===")
    nv = G[G["var"] == "BASE"].shape[0]
    print(f"{'':8s} {'taken':>11s} {'wait':>5s} | {'won':>5s} {'avg %':>7s} {'t':>5s} {'19-22':>6s} {'23-26':>6s} | "
          f"{'avg R':>6s} {'t':>5s} {'19-22':>6s} {'23-26':>6s} | per verdict: {'%':>6s} {'R':>6s} | struct R {'t':>5s} {'19-22':>6s} {'23-26':>6s}")
    for v in ("BASE", "PDH", "W+PDH", "D+PDH", "W only"):
        g = G[G["var"] == v]; tk = g[g.took]
        if len(tk) < 5:
            continue
        e, l = tk[tk.t < "2023"], tk[tk.t >= "2023"]
        print(f"{v:8s} {len(tk):4d} ({100*len(tk)/nv:3.0f}%) {tk.wait.median():5.0f} | {100*(tk.pct>0).mean():5.1f} "
              f"{tk.pct.mean():+7.2f} {tstat(tk.pct):+5.1f} {e.pct.mean():+6.2f} {l.pct.mean():+6.2f} | "
              f"{tk.R.mean():+6.3f} {tstat(tk.R):+5.1f} {e.R.mean():+6.3f} {l.R.mean():+6.3f} | "
              f"{g.pct.mean():+12.2f} {g.R.mean():+6.3f} | {tk.Rs.mean():+8.3f} {tstat(tk.Rs):+5.1f} {e.Rs.mean():+6.3f} {l.Rs.mean():+6.3f}")


show(T, f"ALL verdicts ({T[T['var']=='BASE'].shape[0]} on 21 markets)")
for sec, g in T.groupby("sector"):
    show(g, sec)
for bs, g in T.groupby(T.basis.str.contains("calendar|Calendar|seasonal", regex=True)):
    show(g, "with calendar" if bs else "COT only")
# same verdicts: those the PDH rule takes, own entry vs PDH entry
b = T[T["var"] == "BASE"].reset_index(drop=True); p = T[T["var"] == "PDH"].reset_index(drop=True)
m = p.took & (p.wait > 0)
print(f"\nPDH entered LATER than the verdict ({m.sum()} verdicts): own entry {b.pct[m].mean():+.2f}% / {b.R[m].mean():+.3f}R "
      f"vs PDH entry {p.pct[m].mean():+.2f}% / {p.R[m].mean():+.3f}R")
print(f"PDH never triggered ({(~p.took).sum()} verdicts): own entry {b.pct[~p.took].mean():+.2f}% / {b.R[~p.took].mean():+.3f}R")
for v in ("W+PDH", "D+PDH"):
    q = T[T["var"] == v].reset_index(drop=True)
    print(f"{v}: verdicts without it ({(~q.took).sum()}): own entry {b.pct[~q.took].mean():+.2f}% / {b.R[~q.took].mean():+.3f}R")
