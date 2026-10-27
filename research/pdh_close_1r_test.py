"""RESULT 2026-10-27: small and only on the FIRST close. First close beyond the previous day's extreme inside a
verdict, stop beyond that day, 1:1: 487 trades, 55.0% won, +0.093R (t 2.0), 19-22 +0.082 / 23-26 +0.105, longs +0.126
/ shorts +0.032; same-bar stop+target only 3% (if all target first +0.159R). Stop median 0.35 weekly ATR, resolves in ~2
days. EVERY such close while the verdict is on: 47.7% / -0.052R (later ones lose); no verdict +0.018R, against the
verdict -0.171R (t -5.0): the verdict sets the direction, the trigger adds little. In weekly-ATR terms the 1:1 earns
~0.03 wk-ATR per trade vs ~0.21 for holding the verdict to its exit (0.75 wk-ATR stop, +0.275R): the 1:1 target cuts
off the multi-week move. Control at the verdict's entry day with the same bracket: 18% of bars hit both, unreliable.
RE-RUN + exits (2026-10-27, both scripts reproduce exactly): same first-close entry and break-day stop, target 2R
39.6% / -0.201R (t -4.2), 3R 29.4% / -0.408R (t -9.0), held to the verdict exit 27.1% won / +0.256R (t 1.9): the
break-day stop is too tight for a multi-week hold (73% stopped), the few survivors carry it. The same entry with the
0.75 wk-ATR stop (pdh_close_entry_test) gives the same +0.254R at 56% won and t 3.4 -> if the close is used as the
entry, the stop belongs at the wider level, not under the break day.
Close beyond the previous day's extreme as a 1:1 trade (2026-10-27).
Long: a daily close above the previous day's high; enter at that close, stop below the LOW OF THAT DAY (the day that
broke the high), target 1R above the entry. Short mirrored (close below the previous low, stop above that day's high).
Resolved on the following daily bars: stop first when a bar touches both (daily bars can't tell the order), a gap
through the level fills at the open. Unresolved after 60 trading days = closed at that close (in R).
Signals counted while a board verdict is active (verdict.json, current walk-forward; entry day to exit day), in its
direction, vs the same rule with NO verdict and AGAINST the verdict (control: does the verdict add anything?).
  first   only the first such close in each verdict
  every   every such close while flat (one trade at a time per market)
  CONTROL the verdict's own entry day with the same bracket (stop beyond that day, 1:1), no close condition
Also: the same trades closed at the verdict exit instead of the 60-day cap. No costs.
21 markets (no OHLC history for DX, coffee, cattle). Board direction (yen, franc, CAD inverted)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/bias-board/bias")
import core as C
BB = "/Users/Niklas/bias-board"
V = pd.DataFrame(json.load(open(f"{BB}/data/research/verdict.json"))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
V["sg"] = np.where(V.v == "BULLISH", 1, -1)
CAP = 60

rows = []
for k, meta in C.M.items():
    if k in ("DX", "KC", "LE"):
        continue
    d = pd.read_csv(f"{BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]
    d = d[(d.index.dayofweek < 5) & (d.high > d.low) & (d.index >= "2018-06-01")]
    if meta[2]:
        d = pd.DataFrame({"open": 1 / d.open, "high": 1 / d.low, "low": 1 / d.high, "close": 1 / d.close}, index=d.index)
    w = d.resample("W-FRI").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    wtr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
    watr = wtr.ewm(alpha=1 / 14, adjust=False).mean()
    O, H, L, Cc, idx = d.open.to_numpy(), d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), d.index
    n = len(idx)
    # board state per day: +1 / -1 verdict direction, 0 none; and the verdict's exit index
    state, vex, vid = np.zeros(n, int), np.full(n, -1), np.full(n, -1)
    for r in V[V.m == k].itertuples():
        a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
        if b >= n or b <= a:
            continue
        state[a:b] = r.sg; vex[a:b] = b; vid[a:b] = r.Index

    def trade(i, sg, mult=1.0, hold=False):
        e = Cc[i]; stop = L[i] if sg > 0 else H[i]; R = sg * (e - stop)
        if R <= 0:
            return None
        tp = e + sg * R * (mult if not hold else 1e9)
        out, j_end, amb = None, None, False
        last = vex[i] if hold else min(n, i + 1 + CAP)
        if hold and last < 0:
            return None
        for j in range(i + 1, last):
            if (O[j] <= stop) if sg > 0 else (O[j] >= stop):
                out, j_end = sg * (O[j] - e) / R, j; break           # gap through the stop
            if (O[j] >= tp) if sg > 0 else (O[j] <= tp):
                out, j_end = sg * (O[j] - e) / R, j; break           # gap through the target
            hs = (L[j] <= stop) if sg > 0 else (H[j] >= stop)
            ht = (H[j] >= tp) if sg > 0 else (L[j] <= tp)
            if hs:
                out, j_end, amb = -1.0, j, ht; break
            if ht:
                out, j_end = 1.0, j; break
        if out is None:
            if hold:
                j_end = last; out = sg * (Cc[j_end] - e) / R
            else:
                if i + CAP >= n:
                    return None
                j_end = i + CAP; out = sg * (Cc[j_end] - e) / R
        # alternative: close at the verdict exit if that comes first
        b = vex[i]
        alt = out if (b < 0 or j_end <= b) else sg * (Cc[b] - e) / R
        wa = watr[watr.index < idx[i]]
        return out, alt, j_end, R / wa.iloc[-1] if len(wa) else np.nan, 100 * R / e, amb

    busy = {1: -1, -1: -1, "any": -1}
    seen = set()
    for i in range(1, n):
        if idx[i] < pd.Timestamp("2019-01-07"):
            continue
        for sg in (1, -1):
            if not ((Cc[i] > H[i - 1]) if sg > 0 else (Cc[i] < L[i - 1])):
                continue
            tag = "with verdict" if state[i] == sg else ("no verdict" if state[i] == 0 else "against verdict")
            first = tag == "with verdict" and vid[i] not in seen
            if first:
                seen.add(vid[i])
            if i <= busy["any"] and not first:
                continue
            x = trade(i, sg)
            if x is None:
                continue
            if i > busy["any"]:
                busy["any"] = x[2]
                rows.append({"k": k, "d": idx[i], "sg": sg, "tag": tag, "mode": "every", "r": x[0], "alt": x[1],
                             "days": x[2] - i, "stop_wk": x[3], "stop_pct": x[4], "amb": x[5], "sector": meta[3]})
            if first:
                rows.append({"k": k, "d": idx[i], "sg": sg, "tag": tag, "mode": "first", "r": x[0], "alt": x[1],
                             "days": x[2] - i, "stop_wk": x[3], "stop_pct": x[4], "amb": x[5], "sector": meta[3]})
                for md, kw in (("first 2R", {"mult": 2.0}), ("first 3R", {"mult": 3.0}), ("first hold", {"hold": True})):
                    y = trade(i, sg, **kw)
                    if y is not None:
                        rows.append({"k": k, "d": idx[i], "sg": sg, "tag": tag, "mode": md, "r": y[0], "alt": y[1],
                                     "days": y[2] - i, "stop_wk": y[3], "stop_pct": y[4], "amb": y[5], "sector": meta[3]})
    # control: the verdict's own entry day, same bracket (stop beyond that day's low/high, 1:1), no close condition
    for r in V[V.m == k].itertuples():
        a = idx.searchsorted(r.entry)
        if a >= n or idx[a] != r.entry:
            continue
        x = trade(a, r.sg)
        if x is not None:
            rows.append({"k": k, "d": idx[a], "sg": r.sg, "tag": "with verdict", "mode": "verdict day", "r": x[0],
                         "alt": x[1], "days": x[2] - a, "stop_wk": x[3], "stop_pct": x[4], "amb": x[5], "sector": meta[3]})
    print(k, end=" ", flush=True)
T = pd.DataFrame(rows)
T.to_csv(f"{BB}/data/research/pdh_close_1r.csv", index=False)
print()


def line(g, lab, col="r"):
    if len(g) < 5:
        return
    x = g[col]; e, l = x[g.d < "2023"], x[g.d >= "2023"]
    print(f"  {lab:28s} n{len(g):5d} won{100*(x>0).mean():5.1f}% avg{x.mean():+.3f}R t{x.mean()/x.std(ddof=1)*np.sqrt(len(x)):+5.1f} | "
          f"19-22 {e.mean():+.3f} ({100*(e>0).mean():.0f}%)  23-26 {l.mean():+.3f} ({100*(l>0).mean():.0f}%) | "
          f"stop {g.stop_wk.median():.2f} wkATR {g.stop_pct.median():.2f}%  days {g.days.median():.0f}  both-hit {100*g.amb.mean():.0f}%"
          f" (if target first: {(x + 2 * g.amb).mean():+.3f}R)")


line(T[T["mode"] == "verdict day"], "CONTROL verdict entry day, same bracket")
print("\n=== FIRST close, stop beyond that day, other exits (R = the break-day stop) ===")
for md in ("first", "first 2R", "first 3R", "first hold"):
    g = T[T["mode"] == md]
    line(g, md + (" (to verdict exit)" if md == "first hold" else ""))
    line(g[g.sg > 0], "  longs"); line(g[g.sg < 0], "  shorts")
for mode in ("first", "every"):
    G = T[T["mode"] == mode]
    print(f"\n=== {mode.upper()} close beyond the previous day's extreme, stop beyond that day, 1:1 ===")
    for tag in ("with verdict", "no verdict", "against verdict"):
        line(G[G.tag == tag], tag)
    W = G[G.tag == "with verdict"]
    line(W, "with verdict, out at verdict exit", "alt")
    line(W[W.sg > 0], "  with verdict: longs"); line(W[W.sg < 0], "  with verdict: shorts")
    for sec, g in W.groupby("sector"):
        line(g, f"  {sec}")
    q = W.stop_wk.quantile([1 / 3, 2 / 3]).to_numpy()
    line(W[W.stop_wk <= q[0]], f"  small day (stop <= {q[0]:.2f} wkATR)")
    line(W[(W.stop_wk > q[0]) & (W.stop_wk <= q[1])], "  medium day")
    line(W[W.stop_wk > q[1]], f"  big day (stop > {q[1]:.2f} wkATR)")
