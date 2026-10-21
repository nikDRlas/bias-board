"""Weekly context WITH validity: the last weekly zone touched counts for its side only until price breaks through its far
(distal) edge - primary: a 4h CLOSE beyond it; check: any 1h wick beyond it. A newer weekly touch replaces it.
Applied to (1) plain 4h zones on 14 board markets (data/research/sd_link_4h_weekly.csv) and (2) the validated daily->4h
stream on 27 pairs (data/research/sd_link_d4h_weekly.csv). Zones/bars as in sd_link_4h_weekly_test.py."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic")
from backtest.sd_fx_legout_atr import canon_meta
D = "/Users/Niklas/supply_demand_intraday/data_cache/lse_1h"
AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}
MAP = {"6E": ("EURUSD", 0), "6B": ("GBPUSD", 0), "6A": ("AUDUSD", 0), "6N": ("NZDUSD", 0), "6C": ("USDCAD", 1),
       "6S": ("USDCHF", 1), "6J": ("USDJPY", 1), "ES": ("SP500", 0), "NQ": ("NAS100", 0), "YM": ("DOW", 0),
       "GC": ("GOLD", 0), "SI": ("SILVER", 0), "HG": ("COPPER", 0), "CL": ("USOIL", 0)}
def shift(utc_naive):
    return utc_naive.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
def events(f, inv):
    """(touch time, side, break-by-4h-close time, break-by-wick time) in shifted NY time"""
    h = pd.read_csv(f"{D}/{f}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
    h = h[~h.index.duplicated()].sort_index()
    if inv: h = pd.DataFrame({"open": 1 / h.open, "high": 1 / h.low, "low": 1 / h.high, "close": 1 / h.close}, index=h.index)
    h.index = shift(h.index)
    wk = h.resample("W-FRI").agg(AGG).dropna(); h4 = h.resample("4h").agg(AGG).dropna()
    idx, H, L = h.index, h.high.to_numpy(), h.low.to_numpy()
    i4, C4 = h4.index, h4.close.to_numpy()
    NEVER = pd.Timestamp("2100-01-01")
    ev = []
    for (side, cb, top, bot, lo, a) in canon_meta(wk, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith("d") or side == 1 else -1
        t0 = wk.index[cb] + pd.Timedelta(days=1)
        a_, b_ = idx.searchsorted(t0, "right"), idx.searchsorted(t0 + pd.Timedelta(weeks=104))
        if a_ >= b_: continue
        hit = (L[a_:b_] <= top) if sg > 0 else (H[a_:b_] >= bot)
        j = int(np.argmax(hit))
        if not hit[j]: continue
        tt = idx[a_ + j]; dist = bot if sg > 0 else top
        k = i4.searchsorted(tt)                                   # 4h bars from the touch bar on
        brk = (C4[k:] < dist) if sg > 0 else (C4[k:] > dist)
        bc = i4[k + int(np.argmax(brk))] + pd.Timedelta(hours=4) if brk.any() else NEVER   # known at that bar's close
        m = a_ + j
        brw = (L[m:] < dist) if sg > 0 else (H[m:] > dist)
        bw = idx[m + int(np.argmax(brw))] if brw.any() else NEVER
        ev.append((tt, sg, bc, bw))
    ev.sort(key=lambda e: e[0])
    return ev
def state(ev, t, kind):
    tts = [e[0] for e in ev]; n = int(np.searchsorted(np.array(tts, dtype="datetime64[ns]"), np.datetime64(t), "right"))
    if not n: return 0
    tt, sg, bc, bw = ev[n - 1]
    return sg if t < (bc if kind == "close" else bw) else 0
def line(g, lab, tcol):
    if len(g) < 10: print(f"    {lab:46s} n {len(g)}"); return
    m = g.groupby(g[tcol].dt.to_period("W")).r.mean(); t = m.mean() / m.std(ddof=1) * np.sqrt(len(m))
    span = (g[tcol].max() - g[tcol].min()).days / 365.25
    print(f"    {lab:46s} n {len(g):5d} won {100*(g.r>0).mean():5.1f}% exp {g.r.mean():+.3f}R t(week) {t:+5.1f} R/yr {g.r.sum()/span:+6.1f}"
          f" | 19-22 {g[g[tcol]<'2023'].r.mean():+.3f} 23-26 {g[g[tcol]>='2023'].r.mean():+.3f}")
# (1) plain 4h zones, 14 markets
P = pd.read_csv("/Users/Niklas/bias-board/data/research/sd_link_4h_weekly.csv", parse_dates=["d"])
P = P[P.stop == "B 0.75 ATR"].copy()
for k, (f, inv) in MAP.items():
    ev = events(f, inv); s = P.k == k
    P.loc[s, "wc"] = [state(ev, d, "close") * sd for d, sd in zip(P.loc[s, "d"], P.loc[s, "side"])]
    P.loc[s, "ww"] = [state(ev, d, "wick") * sd for d, sd in zip(P.loc[s, "d"], P.loc[s, "side"])]
print("(1) PLAIN 4h zones, 14 markets, 2019-Aug 2026, 1:1, 0.75 ATR stop, net 0.03R")
line(P, "all", "d")
for col, lab in (("wc", "break = 4h close"), ("ww", "break = wick")):
    print(f"  [{lab}]")
    line(P[P[col] > 0], "weekly zone valid, same side", "d")
    line(P[P[col] == 0], "no valid weekly zone", "d")
    line(P[P[col] < 0], "valid weekly zone on the OTHER side", "d")
    line(P[(P[col] > 0) & (P.board > 0)], "weekly valid same side + board agrees", "d")
# (2) daily->4h stream, 27 pairs
T = pd.read_csv("/Users/Niklas/bias-board/data/research/sd_link_d4h_weekly.csv", parse_dates=["tf"])
T["ts"] = shift(pd.DatetimeIndex(T.tf))
for p in T.pair.unique():
    ev = events(p, 0); s = T.pair == p
    T.loc[s, "wc"] = [state(ev, d, "close") * sd for d, sd in zip(T.loc[s, "ts"], T.loc[s, "side"])]
    T.loc[s, "ww"] = [state(ev, d, "wick") * sd for d, sd in zip(T.loc[s, "ts"], T.loc[s, "side"])]
print("\n(2) DAILY->4h S/D (validated), 27 pairs, 2014-2026, 1:1, net 0.03R")
line(T, "all", "tf")
for col, lab in (("wc", "break = 4h close"), ("ww", "break = wick")):
    print(f"  [{lab}]")
    line(T[T[col] > 0], "weekly zone valid, same side", "tf")
    line(T[T[col] == 0], "no valid weekly zone", "tf")
    line(T[T[col] < 0], "valid weekly zone on the OTHER side", "tf")
    B = T[T.tf >= "2019-01-07"]
    line(B[(B[col] > 0) & (B.board > 0)], "weekly valid same side + board agrees (19-26)", "tf")
