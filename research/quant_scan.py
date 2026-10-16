#!/usr/bin/env python3
"""Pre-registered calendar strategies with a known cause: in-sample, untouched out-of-sample, drift control, walk-forward.

Rules are fixed below BEFORE any results (date, direction, market). Data: the board's daily prices (LSE spot, 2003+;
coffee and cattle = TradingView history continued with LSE). Entry and exit at the close; trading days.
  In-sample   2003-2021           out-of-sample 2022-2026 (last ~20%, run once)
  Costs       round trip, by asset class (FX 0.02%, indices 0.03%, metals 0.05%, energy 0.08%, agriculture 0.10%)
  Control     the same market held the same number of days, same direction, from every trading day of the period:
              the rule must beat that, not just the market's drift
  Walk-forward  9 variants per rule (entry and exit each shifted -5 / 0 / +5 trading days); from 2011 each year the
              variant with the best t on all earlier years is traded; compared with the fixed pre-registered rule
Output: data/research/quant_scan.json"""
import json, os, sys
import numpy as np, pandas as pd
from dateutil.easter import easter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

IS_END, OOS_START = "2021-12-31", "2022-01-01"
COST = {"FX": 0.02, "Indices": 0.03, "Metals": 0.05, "Energy": 0.08, "Agriculture": 0.10}


def nyse_holidays(y):
    """NYSE full-day holidays (observed)"""
    def obs(d):
        d = pd.Timestamp(d)
        return d - pd.Timedelta(days=1) if d.dayofweek == 5 else d + pd.Timedelta(days=1) if d.dayofweek == 6 else d
    def nth(month, wd, n):
        d = pd.Timestamp(y, month, 1)
        d += pd.Timedelta(days=(wd - d.dayofweek) % 7)
        return d + pd.Timedelta(weeks=n - 1)
    def last(month, wd):
        d = pd.Timestamp(y, month, 1) + pd.offsets.MonthEnd(0)
        return d - pd.Timedelta(days=(d.dayofweek - wd) % 7)
    h = [obs(f"{y}-01-01"), nth(1, 0, 3), nth(2, 0, 3), pd.Timestamp(easter(y)) - pd.Timedelta(days=2), last(5, 0),
         obs(f"{y}-07-04"), nth(9, 0, 1), nth(11, 3, 4), obs(f"{y}-12-25")]
    if y >= 2022:
        h.append(obs(f"{y}-06-19"))
    return [d for d in h if d.dayofweek < 5]


# ---------------------------------------------------------------- occurrence builders: list of (entry idx, exit idx)
def seasonal_dates(idx, m1, d1, m2, d2):
    out = []
    for y in range(idx[0].year, idx[-1].year + 1):
        a = idx.searchsorted(pd.Timestamp(y, m1, d1))
        y2 = y + (1 if (m2, d2) < (m1, d1) else 0)
        b = idx.searchsorted(pd.Timestamp(y2, m2, d2), "right") - 1
        if 0 < a < b < len(idx) and idx[a].year == y:
            out.append((a, b))
    return out


def month_end(idx, last_n=3):
    out, g = [], pd.Series(np.arange(len(idx)), index=idx).groupby([idx.year, idx.month])
    for _, s in g:
        v = s.to_numpy()
        if len(v) > last_n + 1:
            out.append((int(v[-last_n - 1]), int(v[-1])))
    return out


def preholiday(idx):
    out = []
    for y in range(idx[0].year, idx[-1].year + 1):
        for h in nyse_holidays(y):
            b = idx.searchsorted(h) - 1                    # last trading day before the holiday
            if 1 <= b < len(idx) and (h - idx[b]).days <= 4:
                out.append((b - 1, b))
    return out


def opex_week(idx):
    out = []
    for y in range(idx[0].year, idx[-1].year + 1):
        for mo in range(1, 13):
            d = pd.Timestamp(y, mo, 1)
            fri3 = d + pd.Timedelta(days=(4 - d.dayofweek) % 7) + pd.Timedelta(weeks=2)
            b = idx.searchsorted(fri3, "right") - 1
            a = idx.searchsorted(fri3 - pd.Timedelta(days=7), "right") - 1
            if 0 < a < b < len(idx) and (fri3 - idx[b]).days <= 3:
                out.append((a, b))
    return out


def santa(idx):
    out = []
    for y in range(idx[0].year, idx[-1].year):
        dec = np.nonzero((idx.year == y) & (idx.month == 12))[0]
        jan = np.nonzero((idx.year == y + 1) & (idx.month == 1))[0]
        if len(dec) > 6 and len(jan) > 2:
            out.append((int(dec[-6]), int(jan[1])))
    return out


RULES = [  # id, market, side, builder, cause
    ("month-end USD", "DX", 1, month_end, "month-end dollar demand from rebalancing"),
    ("JPY fiscal year-end", "6J", 1, lambda i: seasonal_dates(i, 2, 28, 3, 31), "Japanese repatriation before the 31 March year end"),
    ("pre-holiday S&P", "ES", 1, preholiday, "pre-holiday optimism, thin supply"),
    ("pre-holiday Nasdaq", "NQ", 1, preholiday, "pre-holiday optimism, thin supply"),
    ("pre-holiday Dow", "YM", 1, preholiday, "pre-holiday optimism, thin supply"),
    ("OPEX week S&P", "ES", 1, opex_week, "dealer hedging flows into monthly options expiry"),
    ("OPEX week Nasdaq", "NQ", 1, opex_week, "dealer hedging flows into monthly options expiry"),
    ("OPEX week Dow", "YM", 1, opex_week, "dealer hedging flows into monthly options expiry"),
    ("Santa rally S&P", "ES", 1, santa, "year-end inflows and tax timing"),
    ("Santa rally Nasdaq", "NQ", 1, santa, "year-end inflows and tax timing"),
    ("Santa rally Dow", "YM", 1, santa, "year-end inflows and tax timing"),
    ("gold Chinese New Year", "GC", 1, lambda i: seasonal_dates(i, 12, 15, 1, 31), "Chinese New Year physical buying"),
    ("gold Indian festivals", "GC", 1, lambda i: seasonal_dates(i, 7, 15, 9, 30), "Indian festival and wedding demand"),
    ("natural gas pre-winter", "NG", 1, lambda i: seasonal_dates(i, 9, 1, 11, 15), "pre-winter heating demand"),
    ("crude spring", "CL", 1, lambda i: seasonal_dates(i, 2, 15, 4, 30), "refinery restarts before the driving season"),
    ("soybeans harvest", "ZS", -1, lambda i: seasonal_dates(i, 7, 1, 10, 1), "US harvest supply"),
    ("wheat harvest", "ZW", -1, lambda i: seasonal_dates(i, 5, 15, 7, 15), "winter-wheat harvest"),
    ("coffee frost season", "KC", 1, lambda i: seasonal_dates(i, 6, 1, 8, 31), "Brazil frost-risk premium"),
    ("sugar Brazil harvest", "SB", -1, lambda i: seasonal_dates(i, 5, 1, 9, 30), "Brazil centre-south harvest"),
    ("cattle grilling season", "LE", 1, lambda i: seasonal_dates(i, 3, 1, 5, 31), "grilling-season beef demand"),
]


def trades(lc, idx, occ, side, cost, da=0, db=0):
    out = []
    for a, b in occ:
        a2, b2 = a + da, b + db
        if a2 < 1 or b2 >= len(idx) or b2 <= a2:
            continue
        r = 100 * (np.exp(side * (lc[b2] - lc[a2])) - 1) - cost
        out.append({"d": idx[a2], "r": r, "len": b2 - a2})
    return out


def stats(tr, base=None):
    if len(tr) < 3:
        return None
    r = np.array([t["r"] for t in tr])
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    o = {"n": len(r), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 3),
         "pf": round(float(pos / neg), 2) if neg > 0 else None, "t": round(float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))), 2)}
    if base is not None:
        ex = r - np.array([base[t["len"]] for t in tr])
        o["excess"] = round(float(ex.mean()), 3)
        o["excess_t"] = round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(ex))), 2)
    return o


def baseline(lc, idx, side, cost, lens, period):
    """average return of holding `L` trading days from every trading day in the period, same direction, after cost"""
    sel = np.nonzero((idx >= period[0]) & (idx <= period[1]))[0]
    out = {}
    for L in set(lens):
        a = sel[sel + L < len(idx)]
        out[L] = float(np.mean(100 * (np.exp(side * (lc[a + L] - lc[a])) - 1)) - cost)
    return out


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
        lens = [t["len"] for t in T]
        b_is = baseline(lc, idx, side, cost, lens, (idx[0], pd.Timestamp(IS_END)))
        b_oos = baseline(lc, idx, side, cost, lens, (pd.Timestamp(OOS_START), idx[-1]))
        # walk-forward over 9 date-shift variants
        V = {(da, db): trades(lc, idx, occ, side, cost, da, db) for da in (-5, 0, 5) for db in (-5, 0, 5)}
        wf, picks = [], []
        for y in range(2011, idx[-1].year + 1):
            past = {v: [t for t in tr if t["d"].year < y] for v, tr in V.items()}
            ok = {v: stats(tr) for v, tr in past.items() if len(tr) >= 8}
            ok = {v: s for v, s in ok.items() if s}
            if not ok:
                continue
            best = max(ok, key=lambda v: ok[v]["t"])
            picks.append(best)
            wf += [t for t in V[best] if t["d"].year == y]
        fixed_wf = [t for t in T if t["d"].year >= 2011]
        row = {"rule": rid, "market": k, "side": "long" if side > 0 else "short", "cause": cause,
               "is": stats(IS, b_is), "oos": stats(OOS, b_oos), "wf": stats(wf), "fixed_2011": stats(fixed_wf),
               "wf_picks_center_share": round(sum(1 for v in picks if v == (0, 0)) / len(picks), 2) if picks else None,
               "years": sorted({t["d"].year for t in T})[:1] + sorted({t["d"].year for t in T})[-1:]}
        res.append(row)
        print(rid, "| IS", row["is"], "| OOS", row["oos"], "| WF", row["wf"], "| fixed", row["fixed_2011"], flush=True)
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "quant_scan.json"), "w"), indent=1, default=str)
