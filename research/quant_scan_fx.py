#!/usr/bin/env python3
"""Currency round of pre-registered calendar strategies (rules fixed before results), same method as quant_scan.py:
in-sample 2003-2021, untouched out-of-sample 2022-2026, costs, drift control. Walk-forward variants (entry and exit
shifted -5/0/+5 trading days) are now ranked by EXCESS over the drift control, so longer holds that just ride a trend
are not favoured. Output: data/research/quant_scan_fx.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                                         # noqa: E402
from quant_scan import seasonal_dates, trades, stats, baseline, COST, IS_END, OOS_START   # noqa: E402


def month_start(idx, n=3):
    out, g = [], pd.Series(np.arange(len(idx)), index=idx).groupby([idx.year, idx.month])
    groups = [s.to_numpy() for _, s in g]
    for a, b in zip(groups[:-1], groups[1:]):
        if len(b) >= n:
            out.append((int(a[-1]), int(b[n - 1])))
    return out


RULES = [
    ("yen half-year end", "6J", 1, lambda i: seasonal_dates(i, 9, 1, 9, 30), "Japanese half-year-end repatriation"),
    ("yen year-end", "6J", 1, lambda i: seasonal_dates(i, 12, 1, 12, 31), "Japanese year-end repatriation"),
    ("dollar late December", "DX", -1, lambda i: seasonal_dates(i, 12, 15, 12, 31), "year-end dollar funding unwinds"),
    ("dollar month start", "DX", -1, month_start, "the other side of month-end dollar demand"),
    ("euro dividend season", "6E", -1, lambda i: seasonal_dates(i, 4, 15, 5, 31), "European dividends paid out, foreign holders sell euros"),
    ("AUD fiscal year-end", "6A", 1, lambda i: seasonal_dates(i, 6, 1, 6, 30), "Australian fiscal-year-end repatriation"),
    ("franc late-summer risk-off", "6S", 1, lambda i: seasonal_dates(i, 8, 1, 9, 30), "safe-haven demand in the late-summer risk-off season"),
    ("pound UK tax year-end", "6B", 1, lambda i: seasonal_dates(i, 3, 15, 4, 5), "UK tax-year-end flows"),
]

if __name__ == "__main__":
    res = []
    for rid, k, side, build, cause in RULES:
        p = C.load_px(k)
        idx, lc = p.index, np.log(p.to_numpy(float))
        cost = COST[C.M[k][3]]
        occ = build(idx)
        T = trades(lc, idx, occ, side, cost)
        IS = [t for t in T if t["d"] <= pd.Timestamp(IS_END)]
        OOS = [t for t in T if t["d"] >= pd.Timestamp(OOS_START)]
        V = {(da, db): trades(lc, idx, occ, side, cost, da, db) for da in (-5, 0, 5) for db in (-5, 0, 5)}
        lens_all = {t["len"] for tr in V.values() for t in tr}
        wf = []
        for y in range(2011, idx[-1].year + 1):
            base_y = baseline(lc, idx, side, cost, lens_all, (idx[0], pd.Timestamp(y - 1, 12, 31)))
            sc = {}
            for v, tr in V.items():
                past = [t for t in tr if t["d"].year < y]
                st = stats(past, base_y) if len(past) >= 8 else None
                if st:
                    sc[v] = st["excess_t"]
            if sc:
                best = max(sc, key=sc.get)
                wf += [t for t in V[best] if t["d"].year == y]
        lens = [t["len"] for t in T]
        b_is = baseline(lc, idx, side, cost, lens, (idx[0], pd.Timestamp(IS_END)))
        b_oos = baseline(lc, idx, side, cost, lens, (pd.Timestamp(OOS_START), idx[-1]))
        b_wf = baseline(lc, idx, side, cost, {t["len"] for t in wf} or {1}, (pd.Timestamp("2011-01-01"), idx[-1]))
        row = {"rule": rid, "market": k, "side": "long" if side > 0 else "short", "cause": cause,
               "is": stats(IS, b_is), "oos": stats(OOS, b_oos), "wf_2011": stats(wf, b_wf)}
        res.append(row)
        print(f"{rid:28s} IS {row['is']} | OOS {row['oos']} | WF {row['wf_2011']}", flush=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "quant_scan_fx.json"), "w"), indent=1, default=str)
