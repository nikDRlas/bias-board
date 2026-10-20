"""Board bias as a filter on the validated daily->4h S/D stream (1:1, 27 pairs, 2019-26). Needs data/research/sdlink_verdicts.json
(OUT=sdlink_verdicts.json python3 research/verdict_test.py) and /Users/Niklas/supply_demand_dynamic. Result 2026-10-20: no effect."""
import json, numpy as np, pandas as pd
v = pd.DataFrame(json.load(open("/Users/Niklas/bias-board/data/research/sdlink_verdicts.json"))["trades"])
v["t"] = pd.to_datetime(v.t); v["exit"] = pd.to_datetime(v.exit)
CUR = {"EUR": "6E", "GBP": "6B", "JPY": "6J", "CHF": "6S", "AUD": "6A", "CAD": "6C", "NZD": "6N", "USD": "DX"}
def bias(cur, d):
    g = v[(v.m == CUR[cur]) & (v.t < d) & (v.exit >= d)]
    if not len(g): return 0
    return 1 if g.iloc[-1].v == "BULLISH" else -1
T = pd.read_csv("/Users/Niklas/supply_demand_dynamic/backtest_output/grid/sl075_tp10_leg05.csv")
T["tf"] = pd.to_datetime(T.tf); T = T[(T.tf >= "2019-01-07") & (T.tf <= "2026-10-09")].copy()
T["r"] = T.r - 0.03                                         # pipeline cost
out = []
for _, r in T.iterrows():
    a, b = bias(r.pair[:3], r.tf), bias(r.pair[3:], r.tf)
    sc = a - b                                              # + = board favours the pair going up
    s = np.sign(sc) * r.side
    out.append({"tag": "agrees" if s > 0 else "against" if s < 0 else "no read",
                "both": abs(sc) == 2, "legs": int((a != 0) + (b != 0))})
T = pd.concat([T.reset_index(drop=True), pd.DataFrame(out)], axis=1)
def line(g, lab):
    m = g.groupby(g.tf.dt.to_period("M")).r.sum()
    t = g.r.mean() / g.r.std(ddof=1) * np.sqrt(len(g))
    print(f"  {lab:28s} n {len(g):4d} won {100*(g.r>0).mean():5.1f}%  exp {g.r.mean():+.3f}R  t {t:+.1f} | "
          f"19-22 {g[g.tf<'2023'].r.mean():+.3f}  23-26 {g[g.tf>='2023'].r.mean():+.3f}")
print("1:1 S/D daily->4h, 27 pairs, 2019-26, net of 0.03R")
line(T, "all trades")
for tag in ("agrees", "no read", "against"): line(T[T.tag == tag], tag)
line(T[(T.tag == "agrees") & T.both], "agrees on both legs")
line(T[(T.tag == "against") & T.both], "against on both legs")
line(T[T.tag != "against"], "skip 'against' only")
