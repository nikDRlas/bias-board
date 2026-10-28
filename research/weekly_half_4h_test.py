"""RESULT 2026-10-28: NO. Half on the weekly zone + half on 4h zones formed after it = +0.356R per verdict (t 1.9;
19-22 +0.15, 23-26 +0.58; % per verdict -0.14 in 19-22) vs daily-zone re-entries +0.78 and 4h zones from the verdict
start +2.25 on the same 207 verdicts / 10 markets. Weekly zone touched in only 47% of verdicts; the weekly leg itself is
weak here (+0.11R, 19-22 flat, negative in %; stop 0.78 wk-ATR wide) and the 4h zones AFTER the touch (+0.60) earn far
less than 4h zones from the verdict start (+2.25) because the weekly condition both delays the entry and loses the
verdicts that never pull back. Restricting to 4h zones inside the weekly zone (+/-0.25 wk-ATR) is worse still (+0.45).
"half/half-always" (+1.10) is just "4h zones from the start" on the 53% without a weekly touch. Among verdicts WITH a
weekly touch: W +0.24, 4h-after +1.29, half/half +0.76, but 19-22 % negative for every weekly-based leg. Fails the
both-halves bar; by sector positive only in FX (+0.38, both halves +). Keep: zones from the verdict start.
Half on the weekly zone, half on 4h zones formed from it (2026-10-28). Canon OTC zones (body40, mult OFF, base 1-6).
Inside each board verdict (current walk-forward verdict.json), in its direction:
  W        first touch of a fresh WEEKLY zone (W-FRI bars from the daily feed, live the Monday after the leg-out,
           dead after 104 weeks): limit at the proximal, stop beyond the distal (floor 0.10 weekly ATR), hold to the
           verdict exit, one shot.
  H4 after 4h zones (LSE 4h feed, live next bar, dead 13 weeks) whose leg-out closed AFTER the weekly touch, first
           touch = limit at the proximal, stop beyond the distal, hold to the verdict exit, re-enter after a stop.
  H4 in W  the same, but only 4h zones whose proximal lies inside the weekly zone (+/- 0.25 weekly ATR).
  H4 all   4h zones from the verdict entry on (no weekly condition), for reference.
  D zone   daily canon zones, re-entries (the daily result from multi_attempt_entry_test), for reference.
Combos (R per verdict, 1 = one full risk unit):  half/half = 0.5 x W + 0.5 x H4-after (verdicts without a weekly
touch get nothing); half/half-always = the 4h half runs from the verdict entry when no weekly zone is touched.
Each leg is resolved on its own feed (the daily and 4h feeds are different sources, only the DATE of the weekly touch
crosses over). Entry bar checked against the stop for limit fills. No costs.
Markets: 6E 6B 6J 6S 6A 6C GC SI ES NQ (4h history back to 2016). Board direction (yen, franc, CAD inverted)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic"); sys.path.insert(0, "/Users/Niklas/bias-board/bias")
from backtest.sd_fx_legout_atr import canon_meta
import core as C
BB = "/Users/Niklas/bias-board"
H4 = "/Users/Niklas/supply_demand_intraday/data_cache/lse_4h"
MK = ["6E", "6B", "6J", "6S", "6A", "6C", "GC", "SI", "ES", "NQ"]
AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}
V = pd.DataFrame(json.load(open(f"{BB}/data/research/verdict.json"))["trades"])
for c in ("t", "entry", "exit"):
    V[c] = pd.to_datetime(V[c])
V["sg"] = np.where(V.v == "BULLISH", 1, -1)


def inv(d):
    return pd.DataFrame({"open": 1 / d.open, "high": 1 / d.low, "low": 1 / d.high, "close": 1 / d.close}, index=d.index)


def watr_of(bars):
    w = bars.resample("W-FRI").agg(AGG).dropna()
    tr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
    return tr.ewm(alpha=1 / 14, adjust=False).mean()


def zones(bars, live_lag, dead, O, H, L, idx):
    """(first-touch bar index, side, fill, distal, zone top, zone bottom, creation time)."""
    out = []
    for (side, cb, top, bot, lo, a) in canon_meta(bars, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        t0 = bars.index[cb] + live_lag; t1 = t0 + dead
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        for i in range(idx.searchsorted(t0), len(idx)):
            if idx[i] > t1:
                break
            if (L[i] <= prox) if sg > 0 else (H[i] >= prox):
                out.append((i, sg, min(O[i], prox) if sg > 0 else max(O[i], prox), dist, top, bot, bars.index[cb]))
                break
    return sorted(out)


def run(events, a, b, sg, O, H, L, Cc, wa, cap):
    """events = (i, fill, stop); take in order while flat, hold to b; returns [(R, %, Rsize, i, j_end)]."""
    res, i0 = [], a
    for (i, fill, stop) in events:
        if i < i0 or i < a or i >= b or (cap and len(res) >= cap):
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
        res.append((out, 100 * out * R / fill, R / wa[i], i, j_end))
        i0 = j_end + 1
    return res


rows = []
for k in MK:
    meta = C.M[k]
    d = pd.read_csv(f"{BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]
    d = d[(d.index.dayofweek < 5) & (d.high > d.low) & (d.index >= "2012-01-01")]
    h = pd.read_csv(f"{H4}/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
    h = h[~h.index.duplicated()].sort_index(); h = h[(h.high > h.low) & (h.index >= "2016-01-01")]
    if meta[2]:
        d, h = inv(d), inv(h)
    w = d.resample("W-FRI").agg(AGG).dropna()
    O, H, L, Cc, idx = d.open.to_numpy(), d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), d.index
    hO, hH, hL, hC, hidx = h.open.to_numpy(), h.high.to_numpy(), h.low.to_numpy(), h.close.to_numpy(), h.index
    wa_d = watr_of(d).reindex(idx, method="ffill").shift(1).bfill().to_numpy()
    wa_h = watr_of(h).reindex(hidx, method="ffill").shift(1).bfill().to_numpy()
    wz = zones(w, pd.Timedelta(days=3), pd.Timedelta(weeks=104), O, H, L, idx)
    dz = zones(d, pd.Timedelta(days=1), pd.Timedelta(weeks=52), O, H, L, idx)
    hz = zones(h, pd.Timedelta(hours=4), pd.Timedelta(weeks=13), hO, hH, hL, hidx)
    for r in V[V.m == k].itertuples():
        a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
        ha, hb = hidx.searchsorted(r.entry), hidx.searchsorted(r.exit + pd.Timedelta(days=1)) - 1
        if b >= len(idx) or b <= a or idx[a] != r.entry or hb >= len(hidx) or hb <= ha:
            continue
        sg = r.sg
        tot = lambda res: (sum(x[0] for x in res), sum(x[1] for x in res), len(res), [x[2] for x in res])
        row = {"k": k, "sector": meta[3], "t": r.t, "vid": r.Index}
        W = run([(i, f, s) for i, s_, f, s, top, bot, ct in wz if s_ == sg and a <= i < b], a, b, sg, O, H, L, Cc, wa_d, 1)
        row["W"] = tot(W)
        h4all = [(i, f, s) for i, s_, f, s, top, bot, ct in hz if s_ == sg]
        row["H4 all"] = tot(run(h4all, ha, hb, sg, hO, hH, hL, hC, wa_h, 0))
        row["D zone"] = tot(run([(i, f, s) for i, s_, f, s, top, bot, ct in dz if s_ == sg], a, b, sg, O, H, L, Cc, wa_d, 0))
        if W:
            iw = W[0][3]; tw = idx[iw] + pd.Timedelta(days=1)              # 4h zones created from the next day on
            wtop, wbot = [(top, bot) for i, s_, f, s, top, bot, ct in wz if s_ == sg and i == iw][0]
            pad = 0.25 * wa_d[iw]
            after = [(i, f, s) for i, s_, f, s, top, bot, ct in hz if s_ == sg and ct >= tw]
            inw = [(i, f, s) for i, s_, f, s, top, bot, ct in hz if s_ == sg and ct >= tw
                   and (wbot - pad) <= (top if sg > 0 else bot) <= (wtop + pad)]
            hs = hidx.searchsorted(tw)
            row["H4 after"] = tot(run(after, max(ha, hs), hb, sg, hO, hH, hL, hC, wa_h, 0))
            row["H4 in W"] = tot(run(inw, max(ha, hs), hb, sg, hO, hH, hL, hC, wa_h, 0))
        else:
            row["H4 after"] = row["H4 in W"] = (0.0, 0.0, 0, [])
        rows.append(row)
    print(k, end=" ", flush=True)
print()
T = pd.DataFrame(rows)
legs = ["W", "H4 all", "H4 after", "H4 in W", "D zone"]
for lg in legs:
    T[lg + "_R"] = T[lg].str[0]; T[lg + "_pct"] = T[lg].str[1]; T[lg + "_n"] = T[lg].str[2]
T["hasW"] = T.W_n > 0
T["half/half_R"] = 0.5 * T.W_R + 0.5 * T["H4 after_R"]; T["half/half_pct"] = 0.5 * T.W_pct + 0.5 * T["H4 after_pct"]
T["half/half-inW_R"] = 0.5 * T.W_R + 0.5 * T["H4 in W_R"]; T["half/half-inW_pct"] = 0.5 * T.W_pct + 0.5 * T["H4 in W_pct"]
T["half/half-always_R"] = 0.5 * T.W_R + 0.5 * np.where(T.hasW, T["H4 after_R"], T["H4 all_R"])
T["half/half-always_pct"] = 0.5 * T.W_pct + 0.5 * np.where(T.hasW, T["H4 after_pct"], T["H4 all_pct"])
T["W+H4after_R"] = T.W_R + T["H4 after_R"]; T["W+H4after_pct"] = T.W_pct + T["H4 after_pct"]
T.drop(columns=legs).to_csv(f"{BB}/data/research/weekly_half_4h.csv", index=False)


def tstat(x):
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan


def show(G, title):
    print(f"\n=== {title}: {len(G)} verdicts, weekly zone touched in {100*G.hasW.mean():.0f}% ===")
    print(f"{'leg / combo':20s} {'att/v':>5s} {'stop':>5s} {'won':>5s} | per VERDICT {'R':>7s} {'t':>5s} {'19-22':>7s} {'23-26':>7s} | {'%':>6s} {'19-22':>6s} {'23-26':>6s}")
    for nm in ["W", "H4 all", "H4 after", "H4 in W", "D zone", "half/half", "half/half-inW", "half/half-always", "W+H4after"]:
        R, P = G[nm + "_R"], G[nm + "_pct"]
        e, l = G.t < "2023", G.t >= "2023"
        if nm in legs:
            att = G[nm + "_n"].mean(); st = np.median([x for xs in G[nm].str[3] for x in xs]) if G[nm + "_n"].sum() else np.nan
            won = 100 * np.mean([x > 0 for xs in G[nm] for x in [xs]]) if False else np.nan
            extra = f"{att:5.2f} {st:5.2f} {'':>5s}"
        else:
            extra = f"{'':>5s} {'':>5s} {'':>5s}"
        print(f"{nm:20s} {extra} | {R.mean():+7.3f} {tstat(R):+5.1f} {R[e].mean():+7.3f} {R[l].mean():+7.3f} | {P.mean():+6.2f} {P[e].mean():+6.2f} {P[l].mean():+6.2f}")


show(T, "ALL 10 markets")
show(T[T.hasW], "verdicts WITH a weekly zone touched")
for sec, g in T.groupby("sector"):
    show(g, sec)
