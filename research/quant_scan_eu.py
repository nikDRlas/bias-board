#!/usr/bin/env python3
"""European index round (DAX, Euro Stoxx 50) of pre-registered calendar strategies, same method as quant_scan.py:
in-sample 2003-2021, untouched out-of-sample 2022-2026, costs, drift control, walk-forward ranked by excess over drift.
Prices: core.load_px chained series (LSE index data + Eurex futures history for its broken stretch).
Output: data/research/quant_scan_eu.json"""
import json, os, sys
import numpy as np, pandas as pd
from dateutil.easter import easter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                                         # noqa: E402
from quant_scan import seasonal_dates, trades, stats, baseline, IS_END, OOS_START, santa   # noqa: E402

COST = 0.03
FOMC = pd.to_datetime(pd.read_csv(os.path.join(HERE, "..", "data", "fomc_dates.csv")).announce)


def months(idx):
    g = pd.Series(np.arange(len(idx)), index=idx).groupby([idx.year, idx.month])
    return [s.to_numpy() for _, s in g]


def fdom(idx):
    M = months(idx)
    return [(int(a[-1]), int(b[0])) for a, b in zip(M[:-1], M[1:])]


def tom(idx):
    M = months(idx)
    return [(int(a[-5]), int(b[2])) for a, b in zip(M[:-1], M[1:]) if len(a) >= 5 and len(b) >= 3]


def halloween(idx):
    out = []
    for y in range(idx[0].year, idx[-1].year):
        o = np.nonzero((idx.year == y) & (idx.month == 10))[0]
        a = np.nonzero((idx.year == y + 1) & (idx.month == 4))[0]
        if len(o) and len(a):
            out.append((int(o[-1]), int(a[-1])))
    return out


def fomc(idx):
    out = []
    for d in FOMC:
        i = idx.searchsorted(d)
        if 2 <= i < len(idx) and idx[i] == d:
            out.append((i - 2, i))
    return out


def eurex_holidays(y):
    e = pd.Timestamp(easter(y))
    return [d for d in (pd.Timestamp(y, 1, 1), e - pd.Timedelta(days=2), e + pd.Timedelta(days=1), pd.Timestamp(y, 5, 1),
                        pd.Timestamp(y, 12, 24), pd.Timestamp(y, 12, 25), pd.Timestamp(y, 12, 26), pd.Timestamp(y, 12, 31))
            if d.dayofweek < 5]


def preholiday_eu(idx):
    out = []
    for y in range(idx[0].year, idx[-1].year + 1):
        for h in eurex_holidays(y):
            b = idx.searchsorted(h) - 1
            if 1 <= b < len(idx) and 0 < (h - idx[b]).days <= 4:
                out.append((b - 1, b))
    return sorted(set(out))


RULES = []
for k, name in (("DAX", "DAX"), ("ESTX", "Euro Stoxx 50")):
    RULES += [
        (f"Halloween {name}", k, 1, halloween, "the winter half-year beats the summer half"),
        (f"first trading day {name}", k, 1, fdom, "start-of-month inflows"),
        (f"turn of the month {name}", k, 1, tom, "month-end and month-start fund flows"),
        (f"FOMC window {name}", k, 1, fomc, "pre-announcement drift before scheduled Fed decisions"),
        (f"Santa rally {name}", k, 1, santa, "year-end inflows"),
        (f"late-September short {name}", k, -1, lambda i: seasonal_dates(i, 9, 15, 9, 30), "late-September weakness (quarter-end rebalancing)"),
    ]
RULES.insert(5, ("pre-holiday DAX", "DAX", 1, preholiday_eu, "pre-holiday optimism, thin supply"))

if __name__ == "__main__":
    res = []
    for rid, k, side, build, cause in RULES:
        p = C.load_px(k)
        idx, lc = p.index, np.log(p.to_numpy(float))
        occ = build(idx)
        T = trades(lc, idx, occ, side, COST)
        IS = [t for t in T if t["d"] <= pd.Timestamp(IS_END)]
        OOS = [t for t in T if t["d"] >= pd.Timestamp(OOS_START)]
        V = {(da, db): trades(lc, idx, occ, side, COST, da, db) for da in (-2, 0, 2) for db in (-2, 0, 2)}
        lens_all = {t["len"] for tr in V.values() for t in tr}
        wf = []
        for y in range(2011, idx[-1].year + 1):
            base_y = baseline(lc, idx, side, COST, lens_all, (idx[0], pd.Timestamp(y - 1, 12, 31)))
            sc = {v: stats([t for t in tr if t["d"].year < y], base_y) for v, tr in V.items()}
            sc = {v: s["excess_t"] for v, s in sc.items() if s}
            if sc:
                best = max(sc, key=sc.get)
                wf += [t for t in V[best] if t["d"].year == y]
        lens = [t["len"] for t in T]
        b_is = baseline(lc, idx, side, COST, lens, (idx[0], pd.Timestamp(IS_END)))
        b_oos = baseline(lc, idx, side, COST, lens, (pd.Timestamp(OOS_START), idx[-1]))
        b_wf = baseline(lc, idx, side, COST, {t["len"] for t in wf} or {1}, (pd.Timestamp("2011-01-01"), idx[-1]))
        row = {"rule": rid, "market": k, "side": "long" if side > 0 else "short", "cause": cause,
               "is": stats(IS, b_is), "oos": stats(OOS, b_oos), "wf_2011": stats(wf, b_wf)}
        res.append(row)
        f = lambda o: f"{o['win']}% avg {o['avg']:+.2f}% t {o['t']:+.2f} ex {o['excess']:+.2f} (t {o['excess_t']:+.2f}) n{o['n']}" if o else "-"
        print(f"{rid:34s} IS {f(row['is'])} | OOS {f(row['oos'])} | WF {f(row['wf_2011'])}", flush=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "quant_scan_eu.json"), "w"), indent=1, default=str)
