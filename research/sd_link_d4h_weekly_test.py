"""The validated daily->4h S/D stream (1:1, 0.75 ATR stop, legout 0.5; 27 pairs, Massive, net 0.03R) tagged with the WEEKLY
state = side of the last weekly zone price touched (canon body40 mult OFF base 1-6 on NY-week bars from LSE 1h, usable after
its week, <= 104 weeks old, first touch), and with the board's currency bias (both legs, as in sd_link_daily4h_test.py)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic")
from backtest.sd_fx_legout_atr import canon_meta
D = "/Users/Niklas/supply_demand_intraday/data_cache/lse_1h"
AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}
T = pd.read_csv("/Users/Niklas/supply_demand_dynamic/backtest_output/grid/sl075_tp10_leg05.csv")
T["tf"] = pd.to_datetime(T.tf); T["r"] = T.r - 0.03
def weekly_events(pair):
    h = pd.read_csv(f"{D}/{pair}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
    h = h[~h.index.duplicated()].sort_index()
    utc = h.index
    ny = utc.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
    hn = h.copy(); hn.index = ny
    wk = hn.resample("W-FRI").agg(AGG).dropna()
    H, L = hn.high.to_numpy(), hn.low.to_numpy()
    ev = []
    for (side, cb, top, bot, lo, a) in canon_meta(wk, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith("d") or side == 1 else -1
        t0 = wk.index[cb] + pd.Timedelta(days=1); t1 = t0 + pd.Timedelta(weeks=104)
        a_, b_ = ny.searchsorted(t0, "right"), ny.searchsorted(t1)
        if a_ >= b_: continue
        hit = (L[a_:b_] <= top) if sg > 0 else (H[a_:b_] >= bot)
        j = int(np.argmax(hit))
        if hit[j]: ev.append((utc[a_ + j], sg))            # event time in UTC
    ev.sort()
    return np.array([e[0] for e in ev], dtype="datetime64[ns]"), np.array([e[1] for e in ev])
W = {}
for p in sorted(T.pair.unique()):
    W[p] = weekly_events(p)
def wstate(p, t):
    et, es = W[p]; n = int(np.searchsorted(et, np.datetime64(t), "right"))
    return int(es[n - 1]) if n else 0
T["weekly"] = [wstate(r.pair, r.tf) * r.side for r in T.itertuples()]
v = pd.DataFrame(json.load(open("/Users/Niklas/bias-board/data/research/sdlink_verdicts.json"))["trades"])
v["t"] = pd.to_datetime(v.t); v["exit"] = pd.to_datetime(v.exit)
CUR = {"EUR": "6E", "GBP": "6B", "JPY": "6J", "CHF": "6S", "AUD": "6A", "CAD": "6C", "NZD": "6N", "USD": "DX"}
def bias(c, d):
    g = v[(v.m == CUR[c]) & (v.t < d) & (v.exit >= d)]
    return 0 if not len(g) else (1 if g.iloc[-1].v == "BULLISH" else -1)
T["board"] = [np.sign(bias(r.pair[:3], r.tf) - bias(r.pair[3:], r.tf)) * r.side if r.tf >= pd.Timestamp("2019-01-07") else np.nan
              for r in T.itertuples()]
T.to_csv("/Users/Niklas/bias-board/data/research/sd_link_d4h_weekly.csv", index=False)
def line(g, lab):
    m = g.groupby(g.tf.dt.to_period("W")).r.mean(); t = m.mean() / m.std(ddof=1) * np.sqrt(len(m))
    yrs = g.groupby(g.tf.dt.year).r.sum()
    print(f"  {lab:40s} n {len(g):4d} won {100*(g.r>0).mean():5.1f}% exp {g.r.mean():+.3f}R  t(week) {t:+.1f}  R/yr {g.r.sum()/ (g.tf.max()-g.tf.min()).days*365.25:+6.1f}"
          f" | 14-18 {g[g.tf<'2019'].r.mean():+.3f} 19-22 {g[(g.tf>='2019')&(g.tf<'2023')].r.mean():+.3f} 23-26 {g[g.tf>='2023'].r.mean():+.3f}  yrs+ {(yrs>0).sum()}/{len(yrs)}")
print("daily->4h S/D, 1:1, 27 pairs, 2014-2026, net 0.03R")
line(T, "all trades")
line(T[T.weekly > 0], "last weekly zone SAME side")
line(T[T.weekly < 0], "last weekly zone OPPOSITE side")
line(T[T.weekly == 0], "no weekly touch yet")
B = T[T.tf >= "2019-01-07"]
print("\n2019-2026 with the board")
line(B, "all")
line(B[(B.weekly > 0) & (B.board > 0)], "weekly same + board agrees")
line(B[(B.weekly > 0) & (B.board >= 0)], "weekly same + board not against")
line(B[(B.weekly > 0) & (B.board < 0)], "weekly same + board against")
line(B[(B.weekly < 0) & (B.board > 0)], "weekly opposite + board agrees")
