#!/usr/bin/env python3
"""Does a 'won 12+ of 15 years' window need a real calendar effect?

For each market, on 40 Saturdays, count the windows the board's scan accepts (>= 12 of 15 years, 5-90 days,
entry -2..+8 weeks) on the REAL prices and on the same daily returns SHUFFLED in time (any calendar effect
destroyed, same volatility). If the shuffled series produces as many winning windows, the past record alone
cannot tell a real seasonal from luck.
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                     # noqa: E402
from conflict_test import Seas, STARTS, LENS, NY     # noqa: E402


def count(S, t):
    starts = pd.DatetimeIndex(t + pd.to_timedelta(STARTS, "D"))
    up = np.zeros((len(STARTS), len(LENS)))
    for k in range(1, NY + 1):
        s = (starts - pd.DateOffset(years=k)).values.astype("datetime64[D]")
        a = np.searchsorted(S.dv, s)
        b = np.searchsorted(S.dv, s[:, None] + LENS[None, :].astype("timedelta64[D]"))
        res = (S.cum[b] - S.cum[a][:, None]) - S.drift[a][:, None] * (b - a[:, None])
        up += res > 0
    w = np.maximum(up, NY - up)
    return int((w >= 12).sum()), int(w.max())


rng = np.random.default_rng(7)
rows = []
dates = pd.date_range("2022-01-01", "2026-09-30", freq="W-SAT")
for k in C.M:
    p = C.load_px(k)
    lr = np.log(p).diff().dropna().to_numpy()
    real, fake = Seas(p), []
    for rep in range(3):
        sh = rng.permutation(lr)
        q = pd.Series(np.exp(np.concatenate([[0.0], np.cumsum(sh)])) * p.iloc[0], index=p.index)
        fake.append(Seas(q))
    for t in rng.choice(dates, 40, replace=False):
        t = pd.Timestamp(t)
        try:
            r = count(real, t)
            f = [count(F, t) for F in fake]
        except Exception:
            continue
        rows.append({"m": k, "real_n": r[0], "real_best": r[1], "fake_n": np.mean([x[0] for x in f]),
                     "fake_best": np.mean([x[1] for x in f])})
d = pd.DataFrame(rows)
print(d.groupby("m")[["real_n", "fake_n", "real_best", "fake_best"]].mean().round(1))
print("ALL", d[["real_n", "fake_n", "real_best", "fake_best"]].mean().round(1).to_dict(),
      "| share of dates with a 12+/15 window: real", round(100 * (d.real_n > 0).mean()), "% shuffled", round(100 * (d.fake_n > 0).mean()), "%")
print("windows scanned per date:", len(STARTS) * len(LENS), "; expected by chance at 12+/15 (binomial, both sides):",
      round(len(STARTS) * len(LENS) * 2 * sum(__import__("math").comb(15, i) for i in range(12, 16)) / 2 ** 15))
