"""RESULT 2026-10-27: DEAD. 15 FX pairs (no CHF/JPY), 2015-26, n1015: won 42%, end -0.05%/trade vs random same-length 0.00% (t -0.5); all 3 periods ~0; MFE 2.77% vs random 2.57%. +-3 slightly negative, +-7 ~0; since 2024 +-5 +0.04%, +-7 -0.05% (2024 neg, 2025-26 pos).
EdgeFinder flip test on FX (no CHF/JPY pairs): long when score >= +TH, hold until score <= -TH (then short, held until
score >= +TH). Score = replica ef_score (daily, ends 2026-09-16). Signal on day d -> enter at the OPEN of the next
trading day after d; exit the same way. Along each trade: end %, MFE %, MAE % (daily highs/lows), the opposite side's
MFE, and a random-start control (same pair, same direction, same length, 200 random starts per trade)."""
import json, os, sys
import numpy as np, pandas as pd

TH = float(sys.argv[1]) if len(sys.argv) > 1 else 5
D = "/Users/Niklas/supply_demand_intraday/data_cache/lse_daily"
SRC = os.path.expanduser("~/Downloads/scores_taeglich_gesamt_und_macro.csv")
P = ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCAD', 'EURGBP', 'EURAUD', 'EURCAD', 'EURNZD', 'GBPAUD', 'GBPCAD',
     'GBPNZD', 'AUDCAD', 'AUDNZD', 'NZDCAD']
rng = np.random.default_rng(7)


def load(p):
    df = pd.read_csv(f"/Users/Niklas/supply_demand_intraday/data_cache/lse_daily/{p}.csv", parse_dates=["ts"])
    df = df.rename(columns={"open": "o", "high": "h", "low": "l", "close": "c"}).set_index("ts").sort_index()
    df = df[df.index.dayofweek < 5]
    df = df[df.index >= "2014-01-01"]
    # spike filter: a close far off the 5-day median that reverts (known LSE daily glitches, e.g. EURGBP/NZDCAD)
    med = df.c.rolling(5, center=True, min_periods=3).median()
    bad = (df.c / med - 1).abs() > 0.03
    for c in "ohl":
        bad |= (df[c] / med - 1).abs() > 0.06
    print(p, "spike days dropped:", int(bad.sum()))
    return df[~bad]


ef = pd.read_csv(SRC, usecols=["date", "symbol", "ef_score"], parse_dates=["date"])
rows = []
for p in P:
    px = load(p)
    s = ef[ef.symbol == p].set_index("date").ef_score.sort_index()
    wk = np.log(px.c).diff().rolling(260).std() * np.sqrt(5)          # normal weekly move (log)
    pos, sig_d = 0, None
    events = []                                                        # (signal date, new side)
    for d, v in s.items():
        if pos <= 0 and v >= TH:
            pos = 1; events.append((d, 1))
        elif pos >= 0 and v <= -TH:
            pos = -1; events.append((d, -1))
    for i, (d, side) in enumerate(events):
        a = px.index.searchsorted(d + pd.Timedelta(days=1))
        if a >= len(px):
            continue
        if i + 1 < len(events):
            b = px.index.searchsorted(events[i + 1][0] + pd.Timedelta(days=1))
            done = b < len(px)
            b = min(b, len(px) - 1)
        else:
            b = px.index.searchsorted(s.index[-1] + pd.Timedelta(days=1)); b = min(b, len(px) - 1); done = False
        if b <= a:
            continue
        e = px.o.iloc[a]
        seg = px.iloc[a:b + 1]
        hi, lo, ex = seg.h.max(), seg.l.min(), px.o.iloc[b]
        up, dn = 100 * (hi / e - 1), 100 * (lo / e - 1)
        w = 100 * wk.iloc[a]
        L = b - a
        # random control: same pair, same side, same length
        cand = np.arange(260, len(px) - L - 1)
        rs = rng.choice(cand, 200)
        r_end = side * 100 * (px.o.values[rs + L] / px.o.values[rs] - 1)
        r_mfe = np.array([100 * ((px.h.values[k:k + L + 1].max() / px.o.values[k] - 1) if side > 0 else
                                 (1 - px.l.values[k:k + L + 1].min() / px.o.values[k])) for k in rs])
        rows.append({"pair": p, "side": side, "sig": d, "entry": px.index[a], "exit": px.index[b], "days": L, "done": done,
                     "end": side * 100 * (ex / e - 1), "mfe": up if side > 0 else -dn, "mae": dn if side > 0 else -up,
                     "opp_mfe": -dn if side > 0 else up, "wk": w, "rnd_end": r_end.mean(), "rnd_mfe": r_mfe.mean()})

T = pd.DataFrame(rows)
T = T[T.entry >= "2015-06-01"]
T.to_csv(os.path.join(os.path.dirname(D), f"ef_flip_{int(TH)}.csv"), index=False)


def st(g, lab):
    if len(g) == 0:
        return
    x = g.end - g.rnd_end
    t = x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 2 else np.nan
    print(f"{lab:22s} n{len(g):4d} days{g.days.median():5.0f} won{100*(g.end>0).mean():5.1f}% end{g.end.mean():+6.2f}% "
          f"rndEnd{g.rnd_end.mean():+6.2f}% edge{x.mean():+6.2f} t{t:+5.2f} | MFE{g.mfe.mean():5.2f}% rndMFE{g.rnd_mfe.mean():5.2f}% "
          f"oppMFE{g.opp_mfe.mean():5.2f}% MAE{g.mae.mean():+6.2f}% | MFE/wk{(g.mfe/g.wk).mean():4.1f} oppMFE/wk{(g.opp_mfe/g.wk).mean():4.1f}")


print(f"=== threshold +-{TH} ===")
st(T, "ALL")
st(T[T.side > 0], "long")
st(T[T.side < 0], "short")
for a, b in [("2015", "2019"), ("2019", "2023"), ("2023", "2027")]:
    st(T[(T.entry >= a) & (T.entry < b)], f"{a}-{int(b)-1}")
st(T[T.entry >= "2019"], "2019+")
print()
for p, g in T.groupby("pair"):
    st(g, p)
