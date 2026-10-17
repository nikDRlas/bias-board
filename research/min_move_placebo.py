#!/usr/bin/env python3
"""Does the minimum-move gate remove luck? Count 12-of-15 windows on real prices and on placebo prices.

Placebo: each market's daily returns reshuffled at random (same volatility and drift, no calendar structure), 20 times.
On 12 dates a year (2019-26) count the windows the board's scan would accept (12 of 15, start -10..+40, length 5-63),
without the gate and with the usual move >= 2 / 3 normal days. real / placebo = how many times more windows the
real calendar produces than chance alone; if the gate raises it, the gate removes mostly luck windows.
Output: data/research/min_move_placebo.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402

GATES = (0, 2, 3)
N_PLACEBO = 20


def count(cal, dates):
    out = np.zeros(len(GATES))
    for t in dates:
        sc = cal.scan(t)
        if sc is None:
            continue
        ok = sc["wins"] >= SS.GATE
        vol = cal.day_vol(t)
        for i, g in enumerate(GATES):
            out[i] += (ok & (np.abs(sc["mu"]) >= g * vol)).sum()
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(7)
    dates = [pd.Timestamp(y, m, 15) for y in range(2019, 2027) for m in range(1, 13) if pd.Timestamp(y, m, 15) < C.TODAY]
    res, R, P = {}, np.zeros(len(GATES)), np.zeros(len(GATES))
    for k in C.M:
        p = C.load_px(k)
        real = count(SS.Calendar(p), dates)
        r = np.diff(np.log(p.to_numpy(float)))
        fake = np.zeros(len(GATES))
        for _ in range(N_PLACEBO):
            sh = np.exp(np.concatenate([[np.log(p.iloc[0])], np.log(p.iloc[0]) + np.cumsum(rng.permutation(r))]))
            fake += count(SS.Calendar(pd.Series(sh, index=p.index)), dates) / N_PLACEBO
        res[k] = {f"min {g}": {"real": int(a), "placebo": round(float(b), 1)} for g, a, b in zip(GATES, real, fake)}
        R += real
        P += fake
        print(k, " | ".join(f"min {g}: real {a:.0f} placebo {b:.0f} ratio {a / b if b else float('nan'):.2f}" for g, a, b in zip(GATES, real, fake)), flush=True)
    res["all"] = {f"min {g}": {"real": int(a), "placebo": round(float(b), 1), "ratio": round(float(a / b), 2),
                               "kept_real": round(100 * float(a / R[0]), 1), "kept_placebo": round(100 * float(b / P[0]), 1)}
                  for g, a, b in zip(GATES, R, P)}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "min_move_placebo.json"), "w"), indent=1)
    print(json.dumps(res["all"], indent=1))
