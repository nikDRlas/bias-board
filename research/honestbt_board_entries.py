"""RESULT 2026-10-30 (honestbt, gap_stops on, futures-calibrated bps costs; R per setup, both halves, ratio = R/yr / DD):
  canon D own      21 mkts +0.83 (19-22 +0.85 / 23-26 +0.82) t 5.2  ratio 2.00 | 10 mkts +0.82 (+0.72/+0.94) ratio 1.16
  canon 4h >=0.25  10 mkts +1.27 (+1.07/+1.49) t 4.1 ratio 0.80 | own stop +2.22 (+1.72/+2.79) t 3.8 ratio 0.93
  V4 4h >=0.25     +0.99 (+0.74/+1.28) t 3.3 ratio 0.60 | 3T B 4h >=0.25 +0.74 (+0.51/+1.01) t 2.7 ratio 0.63
  Nested W->4h     +0.99 (+0.22/+1.87) t 2.4 ratio 1.00 | reference verdict entry D +0.18 ratio 0.78, 4h +0.21 / 0.47
All five survive, all positive in both halves. vs the research run() loop on the SAME flat 0.02 wk-ATR cost the engine
trims 0-0.4 R/setup (daily canon 10 mkts 0.96 -> 0.75, canon 4h own 2.25 -> 1.83, V4 own 1.80 -> 1.27): the old loop
filled a limit on a gap BEYOND the zone's far edge and gave it a 0.1 wk-ATR emergency stop (phantom +15..+23 R winners),
and measured R from the gap-improved fill instead of the planned risk. Realistic futures costs are cheaper than the flat
0.02 wk ATR, which gives most of it back; tight 4h stops are cost-sensitive (flat-cost ratio ~0.6 vs 0.8-0.9).
gap_stops off (engine default) adds 0.01-0.05 R/setup of phantom gap wins (Nested ratio 1.00 -> 1.34).
The board entries that made >= 0.8 R per setup, re-run on the honestbt engine (2026-10-30), so fills, stops and the
verdict exit are the engine's and not the research scripts' own run() loop.
  canon D       daily canon zones (body40, mult OFF, base 1-6), zone stop             21 markets, daily bars
  canon 4h      4h canon zones, stop >= 0.25 weekly ATR (and own zone stop)          10 markets, LSE 4h feed
  V4 4h         OTC V4 4h zones, stop >= 0.25 wk (and own)
  3T B 4h       three-tier loose 4h zones, stop >= 0.25 wk (and own)
  Nested W->4h  the user's Nested indicator, weekly->4h preset, own 0.75 x ATR14(4h) stop
  verdict       reference: market entry at the open after the verdict, 0.75 wk-ATR stop
How it maps onto honestbt (one Engine per market and entry, mode "seq" = one position at a time):
  * each zone rests a LIMIT at its proximal edge with its stop attached (stop measured from the proximal, the price the
    order is sized on). The order is issued at the close of the bar before the zone's first touch and only inside a
    verdict window in the verdict's direction. Issuing it only for that bar is outcome-identical to resting it from the
    zone's birth: an untouched zone's limit cannot fill, and the first touch consumes the zone (as in the research
    scripts). A touch while a trade is open is blocked by "seq" and the zone is gone, as before.
  * the engine fills it (gap-through = the better open), lets the fill bar stop it out, and walks the stop.
  * the verdict exit is a Close intent at the close of the exit day -> filled at the NEXT open (research: that close).
  * gap_stops=True: a stop that price gaps through fills at the open, not the level (engine fix found in this port -
    without it a limit filled on a gap beyond its stop was booked as a win at the stop price). Also run with it off.
  * R = P&L / planned risk (proximal to stop), the unit the position is sized on.
  * cost per market in basis points of price: round turn (spread + commission) on every trade + stop slippage on
    losers, futures-calibrated (1 tick + $4-5 commission). Also shown: the research scripts' flat 0.02 weekly ATR.
No sub-bars: with a stop and no target, the bar path cannot change the outcome - a long can only reach its stop after
passing (filling at) the proximal, and later bars only test the stop; the gap case is what gap_stops handles."""
import sys, os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import daily_stop_grid_test as DG                     # noqa: E402
import nested_bigbrother_test as NB                   # noqa: E402
from backtest.sd_fx_legout_atr import canon_meta      # noqa: E402
from backtest.sd_otc_challenger import otc_zones_v4   # noqa: E402
from honestbt.strategies.three_tier_sd import detect_zones_pine  # noqa: E402
from honestbt import Engine, Bars                     # noqa: E402
from honestbt.strategy.contract import Strategy, Limit, Market, Close  # noqa: E402
import core as C                                      # noqa: E402

OUT = f"{DG.BB}/data/research"
TEN = DG.TEN
# round turn bps (spread + commission), extra bps on losers (stop slippage); futures-calibrated
COST = {"6E": (1.0, 0.5), "6B": (1.2, 0.6), "6J": (1.2, 0.6), "6S": (1.5, 0.8), "6A": (1.2, 0.6), "6C": (1.2, 0.6),
        "6N": (1.5, 0.8), "GC": (1.0, 0.5), "SI": (2.5, 2.0), "PL": (3.0, 2.0), "PA": (4.0, 3.0), "HG": (2.0, 1.5),
        "CL": (2.0, 1.5), "NG": (5.0, 4.0), "ES": (1.0, 0.6), "NQ": (0.6, 0.4), "YM": (0.6, 0.4),
        "ZC": (3.0, 1.0), "ZW": (2.5, 1.0), "ZS": (1.5, 0.5), "SB": (8.0, 5.0)}


class BoardZones(Strategy):
    """events: {fill bar: [(side, prox, sl, tag)]}; vside[j] = verdict side live for entries on bar j (0 = none);
    close_at = bars whose close ends a verdict. market: {bar: (side, sl_dist, tag)} for the reference entry."""

    def __init__(self, events, vside, close_at, market=None):
        self.ev, self.vside, self.close_at, self.mkt = events, vside, close_at, market or {}

    def on_bar(self, ctx):
        i, out = ctx.i, []
        if i in self.close_at:
            out.append(Close("all", reason="verdict"))
        j = i + 1
        if j < len(self.vside) and self.vside[j]:
            for (sg, prox, sl, tag) in self.ev.get(j, []):
                if sg == self.vside[j]:
                    out.append(Limit(sg, prox, sl_price=sl, valid_bars=1, tag=tag))
            if j in self.mkt:
                sg, dist, tag = self.mkt[j]
                out.append(Market(sg, sl_dist=dist, tag=tag))
        return out


def windows(Vk, idx, h4):
    """verdict windows on this bar index: (vid, t, a, b, sg); entries on a..b-1, exit at the close of b"""
    w = []
    for r in Vk.itertuples():
        if h4:
            a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit + pd.Timedelta(days=1)) - 1
            if b >= len(idx) or b <= a or idx[a] < r.entry:
                continue
        else:
            a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
            if b >= len(idx) or b <= a or idx[a] != r.entry:
                continue
        w.append((r.Index, r.t, a, b, r.sg))
    return w


def first_touch(sg, prox, start, stop_at, H, L, dist=None):
    for i in range(start, min(len(H), stop_at)):
        if (L[i] <= prox) if sg > 0 else (H[i] >= prox):
            return i
        if dist is not None and ((L[i] < dist) if sg > 0 else (H[i] > dist)):
            return None
    return None


def zones_daily(d, H, L):
    out = []
    for (side, cb, top, bot, lo, a) in canon_meta(d, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d", "1")) or side == 1 else -1
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        i = first_touch(sg, prox, cb + 1, cb + 1 + 260, H, L)
        if i is not None:
            out.append((i, sg, prox, dist))
    return {"canon D": out}


def zones_4h(hb, H, L, O, Cc, wk, reg_w, atr):
    o, h, l, c = (hb[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    life = 6 * 13 * 5
    E = {"canon 4h": [], "V4 4h": [], "3T B 4h": [], "Nested W->4h": []}
    for (cb, sg, top, bot) in NB.canon(hb):
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        i = first_touch(sg, prox, cb + 1, cb + 1 + life, H, L)
        if i is not None:
            E["canon 4h"].append((i, sg, prox, dist))
    for (cb, top, bot, isSup) in otc_zones_v4(o, h, l, c):
        sg = -1 if isSup else 1
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        i = first_touch(sg, prox, cb + 2, cb + 2 + life, H, L, dist=dist)
        if i is not None:
            E["V4 4h"].append((i, sg, prox, dist))
    for z in detect_zones_pine(o, h, l, c):
        sg, cb, top, bot = z["side"], z["creation_bar"], z["top"], z["bottom"]
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        i = first_touch(sg, prox, cb + 1, cb + 1 + life, H, L)       # overlap from the outside = touch of the proximal
        if i is not None:
            E["3T B 4h"].append((i, sg, prox, dist))
    for (i, sg, f, st, prox, dist) in NB.nested_entries(hb, wk, reg_w, O, H, L, Cc, atr):
        E["Nested W->4h"].append((i, sg, prox, prox - sg * abs(f - st)))   # its stop = 0.75 ATR14(4h), from the proximal
    return E


def run_book(k, bars, events, stop_rule, wa, wins, gap, market=False):
    """one Engine over the whole history of one market; returns trades + the per-setup frame"""
    n = len(bars)
    vside, vid_of = np.zeros(n + 1, int), np.full(n + 1, -1)
    close_at = set()
    for (vid, t, a, b, sg) in wins:
        vside[a:b], vid_of[a:b] = sg, vid
        close_at.add(b)
    ev, plan = {}, {}
    for (i, sg, prox, dist) in events:
        if not vside[i] or vside[i] != sg:
            continue
        risk = abs(prox - dist)
        if stop_rule == "own":
            risk = max(risk, 0.10 * wa[i])
        elif stop_rule.startswith(">="):
            risk = max(risk, float(stop_rule[2:]) * wa[i])
        sl = prox - sg * risk
        tag = f"{i}:{sg}:{prox:.8g}"
        ev.setdefault(i, []).append((sg, prox, sl, tag))
        plan[tag] = (risk, vid_of[i])
    mkt = {}
    if market:
        for (vid, t, a, b, sg) in wins:
            tag = f"v{vid}"
            mkt[a] = (sg, 0.75 * wa[a], tag); plan[tag] = (0.75 * wa[a], vid)
    df = bars.copy(); df.index = pd.DatetimeIndex(df.index)
    res = Engine(Bars.from_df(df), symbol=k, mode="seq", gap_stops=gap).run(BoardZones(ev, vside, close_at, mkt))
    rt, sl_bps = COST[k]
    rows = []
    for tr in res.trades:
        if tr.tag not in plan:
            continue
        risk, vid = plan[tr.tag]
        g = tr.side * (tr.exit_px - tr.entry_px) / risk
        cost = tr.entry_px * (rt + (sl_bps if g < 0 else 0.0)) / 1e4 / risk
        rows.append({"k": k, "vid": vid, "tag": tr.tag, "entry_dt": tr.entry_dt, "exit_dt": tr.exit_dt, "reason": tr.reason,
                     "gross": g, "net": g - cost, "net_flat": g - 0.02 * wa[tr.entry_i] / risk, "risk_wk": risk / wa[tr.entry_i],
                     "gapfill": (tr.entry_px < tr.sl) if tr.side > 0 else (tr.entry_px > tr.sl)})
    return rows


def summary(T, setups, col="net", yrs=7.8):
    pv = T.groupby("vid")[col].sum().reindex(setups.index, fill_value=0.0)
    n = T.groupby("vid").size().reindex(setups.index, fill_value=0)
    t_ = setups.t
    e, l = pv[t_ < "2023"], pv[t_ >= "2023"]
    eq = T.sort_values("exit_dt").groupby("exit_dt")[col].sum().cumsum()
    dd = (eq - eq.cummax()).min() if len(eq) else np.nan
    ry = T[col].sum() / yrs
    return {"setups": len(pv), "entered": int((n > 0).sum()), "trades": len(T), "won%": 100 * (T.gross > 0).mean(),
            "R/setup": pv.mean(), "t": pv.mean() / pv.std(ddof=1) * np.sqrt(len(pv)), "19-22": e.mean(), "23-26": l.mean(),
            "R/yr": ry, "maxDD": dd, "ratio": ry / abs(dd) if dd else np.nan}


if __name__ == "__main__":
    pd.set_option("display.width", 220); pd.set_option("display.float_format", lambda v: f"{v:+.2f}")
    rows, setups = [], []
    for k, meta in C.M.items():
        if k in ("DX", "KC", "LE"):
            continue
        Vk = DG.V[DG.V.m == k]
        # ---- daily
        d = pd.read_csv(f"{DG.BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]
        d = d[(d.index.dayofweek < 5) & (d.high > d.low) & (d.index >= "2012-01-01")]
        if meta[2]:
            d = NB.inv(d)
        w = d.resample("W-FRI").agg(DG.AGG).dropna()
        tr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
        H, L = d.high.to_numpy(), d.low.to_numpy()
        wa = tr.ewm(alpha=1 / 14, adjust=False).mean().reindex(d.index, method="ffill").shift(1).bfill().to_numpy()
        wins = windows(Vk, d.index, False)
        setups += [{"tf": "D", "k": k, "vid": v, "t": t} for (v, t, a, b, sg) in wins]
        E = zones_daily(d, H, L)
        for gap in (True, False):
            rows += [dict(r, set="canon D", stop="own", gap=gap, tf="D") for r in run_book(k, d, E["canon D"], "own", wa, wins, gap)]
            rows += [dict(r, set="verdict D", stop="0.75 wk", gap=gap, tf="D") for r in run_book(k, d, [], "own", wa, wins, gap, market=True)]
        # ---- 4h
        if k in TEN:
            hb = pd.read_csv(f"{NB.H4}/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
            hb = hb[~hb.index.duplicated()].sort_index(); hb = hb[(hb.high > hb.low) & (hb.index >= "2016-01-01") & (hb.index.dayofweek < 5)]
            if meta[2]:
                hb = NB.inv(hb)
            O, H4, L4, C4, idx = hb.open.to_numpy(), hb.high.to_numpy(), hb.low.to_numpy(), hb.close.to_numpy(), hb.index
            wk = hb.resample("W-FRI").agg(NB.AGG).dropna()
            wtr = np.maximum(wk.high - wk.low, np.maximum(abs(wk.high - wk.close.shift()), abs(wk.low - wk.close.shift())))
            wa4 = wtr.ewm(alpha=1 / 14, adjust=False).mean().reindex(idx, method="ffill").shift(1).bfill().to_numpy()
            reg_w = idx.searchsorted(wk.index + pd.Timedelta(days=1))
            E4 = zones_4h(hb, H4, L4, O, C4, wk, reg_w, NB.wilder(H4, L4, C4))
            wins4 = windows(Vk, idx, True)
            setups += [{"tf": "4h", "k": k, "vid": v, "t": t} for (v, t, a, b, sg) in wins4]
            for gap in (True, False):
                for nm in ("canon 4h", "V4 4h", "3T B 4h"):
                    for st in (">=0.25", "own"):
                        rows += [dict(r, set=nm, stop=st, gap=gap, tf="4h") for r in run_book(k, hb, E4[nm], st, wa4, wins4, gap)]
                rows += [dict(r, set="Nested W->4h", stop="own", gap=gap, tf="4h")
                         for r in run_book(k, hb, E4["Nested W->4h"], "fixed", wa4, wins4, gap)]
                rows += [dict(r, set="verdict 4h", stop="0.75 wk", gap=gap, tf="4h") for r in run_book(k, hb, [], "own", wa4, wins4, gap, market=True)]
        print(k, end=" ", flush=True)
    print()
    T = pd.DataFrame(rows); S = pd.DataFrame(setups)
    T.to_csv(f"{OUT}/honestbt_board_entries.csv.gz", index=False)

    # research-script numbers on the same entries / stops, for the side-by-side
    old = {("canon D", "own", "21"): ("daily_stop_grid.csv.gz", "canon D", "own/zone"),
           ("canon D", "own", "10"): ("daily_stop_grid.csv.gz", "canon D", "own/zone"),
           ("canon 4h", ">=0.25", "10"): ("nested_bigbrother.csv", "canon 4h", "zone, >=0.25 wk"),
           ("canon 4h", "own", "10"): ("nested_bigbrother.csv", "canon 4h", "own/zone"),
           ("V4 4h", ">=0.25", "10"): ("nested_bigbrother.csv", "V4 4h", "zone, >=0.25 wk"),
           ("V4 4h", "own", "10"): ("nested_bigbrother.csv", "V4 4h", "own/zone"),
           ("3T B 4h", ">=0.25", "10"): ("nested_bigbrother.csv", "three-tier B 4h", "zone, >=0.25 wk"),
           ("3T B 4h", "own", "10"): ("nested_bigbrother.csv", "three-tier B 4h", "own/zone"),
           ("Nested W->4h", "own", "10"): ("weekly_stop_grid.csv.gz", "Nested W->4h", "own/zone")}

    def old_stats(f, s, sp, ten):
        G = pd.read_csv(f"{OUT}/{f}", parse_dates=["t", "d"])
        G = G[(G.set == s) & (G.stop == sp)]
        if ten:
            G = G[G.k.isin(TEN)]
        G = G.assign(rc=G.r - np.where(G.took, 0.02 / G.stop_wk.clip(lower=0.1), 0.0))
        pv = G.groupby("vid").agg(r=("rc", "sum"), t=("t", "first"))
        tk = G[G.took].sort_values("d"); eq = tk.rc.groupby(tk.d).sum().cumsum(); dd = (eq - eq.cummax()).min()
        return pv.r.mean(), tk.rc.sum() / 7.8 / abs(dd), int(G.took.sum())

    out = []
    for (s, sp, mk), g in [((s, sp, mk), T[(T.set == s) & (T.stop == sp)]) for (s, sp) in
                           T[["set", "stop"]].drop_duplicates().itertuples(index=False) for mk in ("21", "10")]:
        tf = g.tf.iloc[0] if len(g) else None
        if tf == "4h" and mk == "21":
            continue
        sel = (lambda x: x[x.k.isin(TEN)]) if mk == "10" else (lambda x: x)
        st = sel(S[S.tf == tf]).set_index("vid")
        for gap in (True, False):
            gg = sel(g[g.gap == gap])
            r = {"entry": s, "stop": sp, "mkts": mk, "gap_stops": gap, **summary(gg, st)}
            fl = summary(gg, st, "net_flat")
            r["flat-cost R/setup"], r["flat-cost ratio"] = fl["R/setup"], fl["ratio"]
            r["gross R/setup"] = summary(gg, st, "gross")["R/setup"]
            r["gap fills"] = int(gg.gapfill.sum())
            if gap and (s, sp, mk) in old:
                o = old_stats(*old[(s, sp, mk)], mk == "10")
                r["OLD R/setup"], r["OLD ratio"], r["OLD trades"] = o
            out.append(r)
    R = pd.DataFrame(out)
    R.to_csv(f"{OUT}/honestbt_board_entries_summary.csv", index=False)
    print(R[R.gap_stops].drop(columns="gap_stops").to_string(index=False))
    print("\n--- gap_stops OFF (engine default, phantom gap wins) ---")
    print(R[~R.gap_stops][["entry", "stop", "mkts", "trades", "R/setup", "ratio", "gap fills"]].to_string(index=False))
