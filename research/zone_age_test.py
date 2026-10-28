"""RESULT 2026-10-28: zone age needs NO restriction. Daily (977 attempts): 78% of entries are zones formed AFTER the
verdict (+0.27R/attempt, 29.5% won, t 2.8), 12% formed 0-10 days before = the zone price sits at when the verdict shows
(fill day 0) and the BEST bucket (+0.88R, 32% won, t 2.7, both halves), older zones only 10% of attempts, noisy but net
positive (10-30d +1.07, 30-90d +0.24, 90-180d +0.13, >180d +2.26 on n 20-28). Restricting to after-only cuts the rule
from +0.79 to +0.50R/verdict; <=10d +0.67, <=30d +0.69, <=90d +0.71, any +0.79 (both halves at every limit). 4h: 87%
formed after (+0.36/attempt), 0-10d before +0.62, older n<=16; any age = <=30d (+2.25/+2.31). Take any fresh zone.
Zone age vs the verdict (2026-10-28). Canon OTC zones (body40, mult OFF, base 1-6), inside the board verdicts, in
the verdict's direction, limit at the proximal, stop beyond the distal (floor 0.10 wk-ATR), hold to the verdict exit,
re-enter after a stop (the multi_attempt_entry_test rule). Every attempt is tagged with the zone's AGE at the verdict
entry: creation (leg-out close) minus the verdict entry day, in calendar days (negative = formed before the verdict).
  daily zones: 21 markets, zone dead after 52 weeks;  4h zones: 10 markets, dead after 13 weeks.
Then the rule is re-run restricted to zones formed no earlier than X days before the verdict, X in
{after only, 10, 30, 90, any}, per verdict (no attempt = 0)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic"); sys.path.insert(0, "/Users/Niklas/bias-board/bias")
from backtest.sd_fx_legout_atr import canon_meta
import core as C
BB = "/Users/Niklas/bias-board"
H4 = "/Users/Niklas/supply_demand_intraday/data_cache/lse_4h"
H4_OK = ["6E", "6B", "6J", "6S", "6A", "6C", "GC", "SI", "ES", "NQ"]
AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}
V = pd.DataFrame(json.load(open(f"{BB}/data/research/verdict.json"))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
V["sg"] = np.where(V.v == "BULLISH", 1, -1)


def inv(d):
    return pd.DataFrame({"open": 1 / d.open, "high": 1 / d.low, "low": 1 / d.high, "close": 1 / d.close}, index=d.index)


def watr_of(bars, idx):
    w = bars.resample("W-FRI").agg(AGG).dropna()
    tr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
    return tr.ewm(alpha=1 / 14, adjust=False).mean().reindex(idx, method="ffill").shift(1).bfill().to_numpy()


def zones(bars, live_lag, dead, O, H, L, idx):
    out = []
    for (side, cb, top, bot, lo, a) in canon_meta(bars, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        ct = bars.index[cb]; t0 = ct + live_lag; t1 = t0 + dead
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        for i in range(idx.searchsorted(t0), len(idx)):
            if idx[i] > t1:
                break
            if (L[i] <= prox) if sg > 0 else (H[i] >= prox):
                out.append((i, sg, min(O[i], prox) if sg > 0 else max(O[i], prox), dist, ct))
                break
    return sorted(out)


def run(events, a, b, sg, O, H, L, Cc, wa):
    res, i0 = [], a
    for (i, fill, stop, ct) in events:
        if i < i0 or i < a or i >= b:
            continue
        R = max(sg * (fill - stop), 0.10 * wa[i]); stop = fill - sg * R
        out, j_end = None, None
        if (L[i] <= stop) if sg > 0 else (H[i] >= stop):
            out, j_end = -1.0, i
        else:
            for j in range(i + 1, b + 1):
                if (O[j] <= stop) if sg > 0 else (O[j] >= stop):
                    out, j_end = sg * (O[j] - fill) / R, j; break
                if (L[j] <= stop) if sg > 0 else (H[j] >= stop):
                    out, j_end = -1.0, j; break
        if out is None:
            j_end, out = b, sg * (Cc[b] - fill) / R
        res.append((out, 100 * out * R / fill, R / wa[i], ct, i - a))
        i0 = j_end + 1
    return res


LIMS = [("after only", 0), ("<=10d before", -10), ("<=30d before", -30), ("<=90d before", -90), ("any age", -10**6)]
rows = []
for k, meta in C.M.items():
    if k in ("DX", "KC", "LE"):
        continue
    feeds = []
    d = pd.read_csv(f"{BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]
    d = d[(d.index.dayofweek < 5) & (d.high > d.low) & (d.index >= "2012-01-01")]
    if meta[2]:
        d = inv(d)
    feeds.append(("D", d, pd.Timedelta(days=1), pd.Timedelta(weeks=52)))
    if k in H4_OK:
        h = pd.read_csv(f"{H4}/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
        h = h[~h.index.duplicated()].sort_index(); h = h[(h.high > h.low) & (h.index >= "2016-01-01")]
        if meta[2]:
            h = inv(h)
        feeds.append(("H4", h, pd.Timedelta(hours=4), pd.Timedelta(weeks=13)))
    for tf, bars, lag, dead in feeds:
        O, H, L, Cc, idx = bars.open.to_numpy(), bars.high.to_numpy(), bars.low.to_numpy(), bars.close.to_numpy(), bars.index
        wa = watr_of(bars, idx)
        zs = zones(bars, lag, dead, O, H, L, idx)
        for r in V[V.m == k].itertuples():
            if tf == "D":
                a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
                if b >= len(idx) or b <= a or idx[a] != r.entry:
                    continue
            else:
                a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit + pd.Timedelta(days=1)) - 1
                if b >= len(idx) or b <= a:
                    continue
            sg = r.sg
            ev = [(i, f, s, ct) for i, s_, f, s, ct in zs if s_ == sg]
            for lab, lim in LIMS:
                sel = [e for e in ev if (e[3] - r.entry).days >= lim]
                res = run(sel, a, b, sg, O, H, L, Cc, wa)
                for x in (res or [None]):
                    rows.append({"k": k, "tf": tf, "sector": meta[3], "t": r.t, "vid": r.Index, "lim": lab,
                                 "r": x[0] if x else 0.0, "pct": x[1] if x else 0.0, "stop_wk": x[2] if x else np.nan,
                                 "age": (x[3] - r.entry).days if x else np.nan, "wait": x[4] if x else np.nan, "took": x is not None})
    print(k, end=" ", flush=True)
print()
T = pd.DataFrame(rows)
T.to_csv(f"{BB}/data/research/zone_age.csv", index=False)


def tstat(x):
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan


for tf, nm in (("D", "DAILY zones, 21 markets"), ("H4", "4h zones, 10 markets")):
    G = T[(T.tf == tf) & (T.lim == "any age") & T.took].copy()
    nv = T[(T.tf == tf) & (T.lim == "any age")].vid.nunique()
    print(f"\n=== {nm}: {len(G)} attempts in {nv} verdicts, by zone age at the verdict entry (creation - entry, days) ===")
    edges = [-10**6, -180, -90, -30, -10, 0, 10**6]
    labs = ["older than 180d", "90-180d before", "30-90d before", "10-30d before", "0-10d before", "formed AFTER the verdict"]
    G["bucket"] = pd.cut(G.age, edges, labels=labs, right=False)
    print(f"{'zone age':26s} {'n':>5s} {'share':>6s} {'won':>5s} {'avg R':>7s} {'t':>5s} {'19-22':>7s} {'23-26':>7s} {'avg %':>6s} {'stop':>5s} {'fill day':>8s}")
    for lab in labs:
        g = G[G.bucket == lab]
        if len(g) < 5:
            continue
        print(f"{lab:26s} {len(g):5d} {100*len(g)/len(G):5.0f}% {100*(g.r>0).mean():5.1f} {g.r.mean():+7.3f} {tstat(g.r):+5.1f} "
              f"{g[g.t<'2023'].r.mean():+7.3f} {g[g.t>='2023'].r.mean():+7.3f} {g.pct.mean():+6.2f} {g.stop_wk.median():5.2f} {g.wait.median():8.0f}")
    print(f"\n   rule restricted to zones formed no earlier than ... before the verdict (per verdict, no attempt = 0):")
    print(f"   {'limit':14s} {'att/v':>5s} {'verd w/ entry':>13s} | {'R/verdict':>9s} {'t':>5s} {'19-22':>7s} {'23-26':>7s} | {'%/verdict':>9s} {'19-22':>6s} {'23-26':>6s}")
    for lab, lim in LIMS:
        g = T[(T.tf == tf) & (T.lim == lab)]
        pv = g.groupby("vid").agg(r=("r", "sum"), pct=("pct", "sum"), n=("took", "sum"), t=("t", "first"))
        e, l = pv[pv.t < "2023"], pv[pv.t >= "2023"]
        print(f"   {lab:14s} {pv.n.mean():5.2f} {100*(pv.n>0).mean():12.0f}% | {pv.r.mean():+9.3f} {tstat(pv.r):+5.1f} {e.r.mean():+7.3f} {l.r.mean():+7.3f} | "
              f"{pv.pct.mean():+9.2f} {e.pct.mean():+6.2f} {l.pct.mean():+6.2f}")
