"""RESULT 2026-10-30 (235 verdicts, 10 markets, 4h feed, hold to the verdict exit, R per verdict): canon 4h zones
+2.94 (t 4.5, 19-22 +2.23 / 23-26 +3.76, every sector) stay far ahead. NESTED (user's Pine, Daily->4h) +0.52 with its
own 0.75 ATR stop (t 1.6; 19-22 +0.13, 23-26 +0.97), entry in only 49% of verdicts, FX negative (-0.02), metals +2.0;
its own 2R exit +0.25 and +0.02 after 0.02 wk-ATR cost. Nested 4h zones are canon zones, so its armed-daily +
liquidity filter keeps 12% of them and lowers R per attempt (+0.51 vs +0.64). BIG-BROTHER +0.39 (t 2.2) but 2019-22
-0.07, entry in 30% of verdicts, indices negative; 2R exit +0.01. Confluence: BB zones overlapping a canon 4h zone
+1.41 R/attempt (+0.37/verdict) vs BB without +0.72 (+0.10) - the canon overlap carries it, 2019-22 still negative.
Neither indicator adds to the canon zones inside a verdict.
WIDER STOPS (same run, + V4 and three-tier B on 4h; R per verdict / R per yr / maxDD at 0.02 cost): wider stops lower
the R for every indicator, keep the % per verdict about the same and cut the drawdown. canon 4h zone stop +2.94 (ratio
0.73) -> >=0.25 wk +1.47 (0.74) -> >=0.5 wk +0.66 (0.52) -> fixed 0.75 wk +0.43 (0.47); V4 +2.41 -> +0.32; three-tier
B +1.51 -> +0.28; Nested +0.52 -> +0.05 (2019-22 negative with every wider stop). BIG-BROTHER is the exception: it gets
SAFER and turns positive in both halves - fixed 0.75 wk 60% won, +0.17/verdict (t 3.2, 19-22 +0.09 / 23-26 +0.26),
maxDD -3.1R, ratio 1.51, top 5% = 29% of R - but only 30% of verdicts and +4.7 R/yr; on FX its own stop ratio 1.37.
Two more S/D indicators as entries inside board verdicts (2026-10-30). Ported from the user's Pine (pasted today),
run on the LSE 4h feed (10 markets with 4h history: 6E 6B 6J 6S 6A 6C GC SI ES NQ); daily bars = the 4h bars per date.
  NESTED (Daily->4h preset): daily canon zones (body40, mult OFF, base 1-6), registered the 4h bar after the day closes;
      a daily zone ARMS when price leaves it and returns, dies on a far-side break or on an opposing valid entry
      (armedopp barrier). A 4h canon zone becomes VALID when its leg-out fired at/after an armed same-side daily zone's
      arm bar AND it qualified on liquidity (p3: a same-side pivot formed after the zone was taken, and an opposite pivot
      formed before that one was taken after it). Limit at the proximal from the NEXT bar (the Pine also lets the
      validation bar fill: it knows that bar's low only at its close). Indicator stop 0.75 x ATR14(4h), target 2R.
  BIG-BROTHER (Daily-covered 4h): literal zones (leg-out body >= 40% of its range, base 2-6 bars with leg-out range >=
      1.5x base range, no leg-in), on 4h and daily. When a daily zone confirms, untouched 4h zones of the same side made
      in the 60 bars before it and overlapping it qualify; limit at the 4h proximal. The Pine has no stop: tested with
      the stop beyond the 4h zone (as the canon test) and 0.75 x ATR14(4h).
Inside each verdict (current verdict.json, macro gate off), in its direction, re-enter after a stop, hold to the
verdict exit (the board rule from multi_attempt_entry_test); also the indicator's own 2R exit. References on the same
feed and verdicts: canon 4h zones (stop beyond the zone) and the verdict entry (0.75 wk-ATR stop).
Confluence: Big-Brother entries whose 4h zone overlaps a fresh canon 4h zone of the same side vs not. (Nested 4h zones
ARE canon 4h zones, so Nested = a filtered subset of canon 4h.)"""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic"); sys.path.insert(0, "/Users/Niklas/bias-board/bias")
from backtest.sd_fx_legout_atr import canon_meta
from backtest.sd_otc_challenger import otc_zones_v4
sys.path.insert(0, "/Users/Niklas/honestbt")
from honestbt.strategies.three_tier_sd import detect_zones_pine
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


def wilder(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def canon(bars):
    out = []
    for (side, cb, top, bot, lo, a) in canon_meta(bars, mult_on=False, body_min=40.0, base_min=1):
        out.append((cb, 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1, top, bot))
    return out


def literal(o, h, l, c):
    """Big-Brother literal detector: leg-out = bar i; base = bars i-1..i-nb, nb 2..6 (largest run that still holds)."""
    out = []
    for i in range(8, len(c)):
        r0, b0 = h[i] - l[i], abs(c[i] - o[i])
        if r0 <= 0 or b0 < 0.40 * r0 or c[i] == o[i]:
            continue
        best = 0
        for nb in range(2, 7):
            bh, bl = h[i - nb:i].max(), l[i - nb:i].min()
            if bh - bl > 0 and r0 >= 1.5 * (bh - bl):
                best = nb
            elif bh - bl > 0:
                break
        if best < 2:
            continue
        sl_ = slice(i - best, i)
        btop, bbot = np.maximum(o[sl_], c[sl_]).max(), np.minimum(o[sl_], c[sl_]).min()
        if c[i] > o[i]:
            out.append((i, 1, btop, l[sl_].min(), btop))
        else:
            out.append((i, -1, h[sl_].max(), bbot, bbot))
    return out


def pivots(h, l, n=3):
    """(pivot bar, taken bar) for strict pivot lows and highs; taken = first bar from the confirm bar on through it."""
    N = len(h); lows, highs = [], []
    for p in range(n, N - n):
        nb = np.r_[np.arange(p - n, p), np.arange(p + 1, p + n + 1)]
        for arr, is_lo, store in ((l, True, lows), (h, False, highs)):
            if (arr[nb] > arr[p]).all() if is_lo else (arr[nb] < arr[p]).all():
                s = p + n
                m = (arr[s:] <= arr[p]) if is_lo else (arr[s:] >= arr[p])
                store.append((p, s + int(np.argmax(m)) if m.any() else 10**9))
    return np.array(lows or [(0, 10**9)]), np.array(highs or [(0, 10**9)])


def qual_times(zones, lows, highs):
    """earliest bar each 4h zone is liquidity-qualified (Pine 'qualified'): same-side pivot s formed after the zone and
    taken, plus an opposite pivot o formed before s and taken after s; time = max(s.taken, min o.taken)."""
    def side_q(same, opp):
        oq = np.full(len(same), 10**9)
        for k, (sb, st) in enumerate(same):
            m = (opp[:, 0] < sb) & (opp[:, 1] > sb)
            if m.any():
                oq[k] = opp[m, 1].min()
        t = np.maximum(same[:, 1], oq)
        suf = np.minimum.accumulate(t[::-1])[::-1]
        return same[:, 0], suf
    lo_b, lo_suf = side_q(lows, highs); hi_b, hi_suf = side_q(highs, lows)
    out = {}
    for (cb, sg, top, bot) in zones:
        b_, suf = (lo_b, lo_suf) if sg > 0 else (hi_b, hi_suf)
        k = int(np.searchsorted(b_, cb, "right"))
        out[(cb, sg)] = suf[k] if k < len(suf) else 10**9
    return out


def nested_entries(hb, db, reg_of_day, O, H, L, Cc, atr):
    """forward simulation of the Nested indicator on the 4h bars; returns fills (bar, side, fill, stop, prox, dist)."""
    n = len(Cc)
    hz = [dict(reg=reg_of_day[cb], sg=sg, top=top, bot=bot, left=False, armed=False, arm=-1, done=False)
          for (cb, sg, top, bot) in canon(db) if reg_of_day[cb] < n]
    hz_by = {}
    for z in hz:
        hz_by.setdefault(z["reg"], []).append(z)
    ez = canon(hb)
    lows, highs = pivots(H, L, 3)
    qt = qual_times(ez, lows, highs)
    ez_by = {}
    for z in ez:
        ez_by.setdefault(z[0], []).append(dict(cb=z[0], sg=z[1], top=z[2], bot=z[3], valid=False, done=False, vb=-1, prox=None, R=None))
    live_h, pend, fills = [], [], []
    for i in range(n):
        live_h += hz_by.get(i, [])
        for z in live_h:                                     # arm / far-break (Pine order: left, else arm; then break)
            if z["done"]:
                continue
            if not z["left"] and ((L[i] > z["top"]) if z["sg"] > 0 else (H[i] < z["bot"])):
                z["left"] = True
            elif z["left"] and not z["armed"] and ((L[i] <= z["top"]) if z["sg"] > 0 else (H[i] >= z["bot"])):
                z["armed"], z["arm"] = True, i
            if (L[i] < z["bot"]) if z["sg"] > 0 else (H[i] > z["top"]):
                z["done"] = True
        live_h = [z for z in live_h if not z["done"]]
        min_arm = {s: min([z["arm"] for z in live_h if z["armed"] and z["sg"] == s] or [10**9]) for s in (1, -1)}
        pend += ez_by.get(i, [])
        if len(pend) > 300:
            pend = pend[-250:]
        new = {1: False, -1: False}
        for z in pend:
            if z["done"]:
                continue
            sg = z["sg"]
            if not z["valid"]:
                if (L[i] < z["bot"]) if sg > 0 else (H[i] > z["top"]):
                    z["done"] = True
                elif z["cb"] >= min_arm[sg] and qt[(z["cb"], sg)] <= i:
                    z.update(valid=True, vb=i, prox=z["top"] if sg > 0 else z["bot"], R=0.75 * atr[i]); new[sg] = True
            elif z["vb"] < i:
                if not (z["cb"] >= min_arm[sg]):
                    z["done"] = True                         # HTF window died
                elif (L[i] <= z["prox"]) if sg > 0 else (H[i] >= z["prox"]):
                    f = min(O[i], z["prox"]) if sg > 0 else max(O[i], z["prox"])
                    fills.append((i, sg, f, f - sg * z["R"], z["prox"], z["bot"] if sg > 0 else z["top"]))
                    z["done"] = True
        for s in (1, -1):                                    # armedopp barrier
            if new[s]:
                for z in pend:
                    if z["valid"] and not z["done"] and z["sg"] == -s and z["vb"] < i:
                        z["done"] = True
                for z in live_h:
                    if z["armed"] and z["sg"] == -s:
                        z["done"] = True
        pend = [z for z in pend if not z["done"]]
    return fills


def bigbrother_entries(hb, db, reg_of_day, O, H, L, atr):
    n = len(O)
    z4 = literal(hb.open.to_numpy(), H, L, hb.close.to_numpy())
    zd = literal(db.open.to_numpy(), db.high.to_numpy(), db.low.to_numpy(), db.close.to_numpy())
    reg = {}
    for (cb, sg, top, bot, prox) in zd:
        if reg_of_day[cb] < n:
            reg.setdefault(reg_of_day[cb], []).append((sg, top, bot))
    used, fills = set(), []
    for r_i, dzs in sorted(reg.items()):
        for (dsg, dtop, dbot) in dzs:
            for (cb, sg, top, bot, prox) in z4:
                if sg != dsg or cb >= r_i or r_i - cb > 60 or (cb, sg) in used:
                    continue
                if max(bot, dbot) > min(top, dtop):
                    continue
                used.add((cb, sg))
                hit_before = ((L[cb + 1:r_i] <= prox) if sg > 0 else (H[cb + 1:r_i] >= prox)).any()
                if hit_before:
                    continue                                 # limit already spent before the daily zone confirmed
                m = (L[r_i:] <= prox) if sg > 0 else (H[r_i:] >= prox)
                if not m.any():
                    continue
                i = r_i + int(np.argmax(m))
                f = min(O[i], prox) if sg > 0 else max(O[i], prox)
                fills.append((i, sg, f, bot if sg > 0 else top, top, bot))
    return sorted(fills)


def canon_entries(hb, O, H, L):
    out = []
    for (cb, sg, top, bot) in canon(hb):
        prox = top if sg > 0 else bot
        m = (L[cb + 1:] <= prox) if sg > 0 else (H[cb + 1:] >= prox)
        if not m.any():
            continue
        i = cb + 1 + int(np.argmax(m))
        if i - cb > 6 * 13 * 5:                              # dead after 13 weeks (as the canon 4h test)
            continue
        f = min(O[i], prox) if sg > 0 else max(O[i], prox)
        out.append((i, sg, f, bot if sg > 0 else top, top, bot))
    return sorted(out)


def v4_entries(hb, O, H, L):
    """OTC V4: live from leg-out + 2, wick through the distal before a touch = broken, first touch of the proximal."""
    out = []
    for (cb, top, bot, isSup) in otc_zones_v4(*(hb[c].to_numpy(float) for c in ("open", "high", "low", "close"))):
        sg = -1 if isSup else 1
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        for i in range(cb + 2, min(len(O), cb + 2 + 6 * 13 * 5)):
            if (L[i] <= prox) if sg > 0 else (H[i] >= prox):
                f = min(O[i], prox) if sg > 0 else max(O[i], prox)
                out.append((i, sg, f, dist, top, bot)); break
            if (L[i] < dist) if sg > 0 else (H[i] > dist):
                break
    return sorted(out)


def tier_b_entries(hb, O, H, L):
    """three-tier B (every loose zone): live from leg-out + 1, first bar overlapping the zone = limit at the proximal."""
    out = []
    for z in detect_zones_pine(*(hb[c].to_numpy(float) for c in ("open", "high", "low", "close"))):
        sg, cb, top, bot = z["side"], z["creation_bar"], z["top"], z["bottom"]
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        m = (L[cb + 1:] <= top) & (H[cb + 1:] >= bot)
        if not m.any():
            continue
        i = cb + 1 + int(np.argmax(m))
        if i - cb > 6 * 13 * 5:
            continue
        f = min(O[i], prox) if sg > 0 else max(O[i], prox)
        out.append((i, sg, f, dist, top, bot))
    return sorted(out)


def run(events, a, b, sg, O, H, L, Cc, wa, target=None):
    """events (i, fill, stop): take while flat inside [a, b), stop first (limit fill can stop on its own bar),
    hold to b or to the target (in R)."""
    res, i0 = [], a
    for (i, fill, stop) in events:
        if i < i0 or i < a or i >= b:
            continue
        R = max(sg * (fill - stop), 0.10 * wa[i]); stop = fill - sg * R
        tp = fill + sg * target * R if target else None
        out = None
        if (L[i] <= stop) if sg > 0 else (H[i] >= stop):
            out, j_end = -1.0, i
        else:
            for j in range(i + 1, b + 1):
                if (O[j] <= stop) if sg > 0 else (O[j] >= stop):
                    out, j_end = sg * (O[j] - fill) / R, j; break
                if (L[j] <= stop) if sg > 0 else (H[j] >= stop):
                    out, j_end = -1.0, j; break
                if tp is not None and ((H[j] >= tp) if sg > 0 else (L[j] <= tp)):
                    out, j_end = target, j; break
        if out is None:
            j_end, out = b, sg * (Cc[b] - fill) / R
        res.append((out, 100 * out * R / fill, R / wa[i], i))
        i0 = j_end + 1
    return res


if __name__ == "__main__":
    rows, stats = [], []
    for k in MK:
        meta = C.M[k]
        hb = pd.read_csv(f"{H4}/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
        hb = hb[~hb.index.duplicated()].sort_index(); hb = hb[(hb.high > hb.low) & (hb.index >= "2016-01-01") & (hb.index.dayofweek < 5)]
        if meta[2]:
            hb = inv(hb)
        db = hb.groupby(hb.index.normalize()).agg(AGG)
        O, H, L, Cc, idx = hb.open.to_numpy(), hb.high.to_numpy(), hb.low.to_numpy(), hb.close.to_numpy(), hb.index
        reg_of_day = idx.searchsorted(db.index + pd.Timedelta(days=1))     # first 4h bar of the next date
        wk = hb.resample("W-FRI").agg(AGG).dropna()
        wtr = np.maximum(wk.high - wk.low, np.maximum(abs(wk.high - wk.close.shift()), abs(wk.low - wk.close.shift())))
        wa = wtr.ewm(alpha=1 / 14, adjust=False).mean().reindex(idx, method="ffill").shift(1).bfill().to_numpy()
        atr = wilder(H, L, Cc)
        E = {"canon 4h": canon_entries(hb, O, H, L),
             "V4 4h": v4_entries(hb, O, H, L),
             "three-tier B 4h": tier_b_entries(hb, O, H, L),
             "Nested (D->4h)": nested_entries(hb, db, reg_of_day, O, H, L, Cc, atr),
             "Big-Brother 4h": bigbrother_entries(hb, db, reg_of_day, O, H, L, atr)}
        stats.append({"k": k, **{nm: len(v) for nm, v in E.items()}})
        for r in V[V.m == k].itertuples():
            a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit + pd.Timedelta(days=1)) - 1
            if b >= len(idx) or b <= a or idx[a] < r.entry:
                continue
            sg = r.sg
            out = {("verdict entry", "0.75 wk"): run([(a, Cc[a], Cc[a] - sg * 0.75 * wa[a])], a, b, sg, O, H, L, Cc, wa)}
            for nm, ev in E.items():
                ev = [e for e in ev if e[1] == sg]
                # own stop: the zone's far edge, Nested its 0.75 x ATR14(4h) (set at validation)
                own = [(i, f, st) for (i, s_, f, st, top, bot) in ev]
                for lab, kk, fixed in (("own/zone", 0, False), ("zone, >=0.25 wk", 0.25, False), ("zone, >=0.5 wk", 0.5, False),
                                       ("fixed 0.75 wk", 0.75, True)):
                    if fixed:
                        evs = [(i, f, f - sg * kk * wa[i]) for (i, f, st) in own]
                    else:
                        evs = [(i, f, st if sg * (f - st) >= kk * wa[i] else f - sg * kk * wa[i]) for (i, f, st) in own]
                    out[(nm, lab)] = run(evs, a, b, sg, O, H, L, Cc, wa)
            for (nm, lab), res in out.items():
                for x in (res or [None]):
                    rows.append({"k": k, "sector": meta[3], "t": r.t, "vid": r.Index, "set": nm, "stop": lab, "took": x is not None,
                                 "r": x[0] if x else 0.0, "pct": x[1] if x else 0.0, "stop_wk": x[2] if x else np.nan,
                                 "d": idx[x[3]] if x else pd.NaT})
        print(k, stats[-1], flush=True)
    T = pd.DataFrame(rows)
    T.to_csv(f"{BB}/data/research/nested_bigbrother.csv", index=False)


    def tstat(x):
        return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan


    YRS = 7.8


    def show(G, title, equity=True):
        print(f"\n=== {title}: {G.vid.nunique()} verdicts ===")
        print(f"{'entry':18s} {'stop':16s} {'att/v':>5s} {'w/ent':>5s} {'stop':>5s} {'won':>4s} {'R/att':>6s} | {'R/verd':>6s} {'t':>5s} {'19-22':>6s} {'23-26':>6s} | "
              f"{'%/verd':>6s} | cost .02: {'R/verd':>6s} {'R/yr':>6s} {'maxDD':>6s} {'ratio':>5s} {'top5%':>5s}")
        for (nm, lab), g in G.groupby(["set", "stop"], sort=False):
            g = g.assign(rc=g.r - np.where(g.took, 0.02 / g.stop_wk.clip(lower=0.1), 0.0))
            pv = g.groupby("vid").agg(r=("r", "sum"), pct=("pct", "sum"), n=("took", "sum"), t=("t", "first"), rc=("rc", "sum"))
            tk = g[g.took].sort_values("d"); e, l = pv[pv.t < "2023"], pv[pv.t >= "2023"]
            eq = tk.rc.groupby(tk.d).sum().cumsum(); dd = (eq - eq.cummax()).min() if len(eq) else np.nan
            top = tk.rc.sort_values(ascending=False); sh = top.head(max(1, len(top) // 20)).sum() / top.sum() if top.sum() > 0 else np.nan
            print(f"{nm:18s} {lab:16s} {pv.n.mean():5.2f} {100*(pv.n>0).mean():4.0f}% {tk.stop_wk.median():5.2f} {100*(tk.r>0).mean():4.0f} {tk.r.mean():+6.3f} | "
                  f"{pv.r.mean():+6.3f} {tstat(pv.r):+5.1f} {e.r.mean():+6.3f} {l.r.mean():+6.3f} | {pv.pct.mean():+6.2f} | "
                  f"{pv.rc.mean():+16.3f} {tk.rc.sum()/YRS:+6.1f} {dd:+6.1f} {tk.rc.sum()/YRS/abs(dd) if dd else np.nan:5.2f} {100*sh:4.0f}%")


    show(T, "10 markets, 4h feed")
    for sec, g in T.groupby("sector"):
        show(g[g.stop.isin(["own/zone", "zone, >=0.5 wk", "0.75 wk", "fixed 0.75 wk"])], sec)
    print("\nentries generated (whole history, both sides):", pd.DataFrame(stats).set_index("k").sum().to_dict())
