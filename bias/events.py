"""Quant strategies: calendar rules with a known cause, defined in advance and validated in our July 2026 test
(20 years after publication). All counted in trading days, entry and exit at the close.

  Turn of the month   last 4 + first 3 trading days (month-end and month-start fund flows)
  First trading day   the first trading day of the month (inflows at the start of the month)
  Halloween           1 November to 30 April ("sell in May"; the winter half beats the summer half)
  FOMC window         the day before and the day of a scheduled Fed announcement (Lucca-Moench drift)
  Corn pre-harvest   short from 15 June to 30 September (new-crop supply arrives)
FOMC dates: data/fomc_dates.csv (scheduled meetings, announcement day; 2027 dates are tentative per the Fed).
"""
import os
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOMC = pd.to_datetime(pd.read_csv(os.path.join(ROOT, "data", "fomc_dates.csv")).announce)
NY = 15

EVENTS = {
    "tom": {"rule": "Buy at the close 5 trading days before month end, sell at the close of the 3rd trading day of the new month.", "name": "Turn of the month", "why": "month-end and month-start fund flows",
            "test": "held out of sample on the Nasdaq (t 2.1); positive but weaker on the S&P and the Dow"},
    "fdom": {"rule": "Buy at the close of the last trading day of the month, sell at the close of the first trading day.", "name": "First trading day", "why": "pension and payroll inflows at the start of the month",
             "test": "held out of sample on all six indices tested (t 2.0 to 2.4)"},
    "halloween": {"rule": "Buy at the close of the last trading day of October, sell at the close of the last trading day of April.", "name": "Halloween (Nov to Apr)", "why": "the winter half-year has beaten the summer half",
                  "test": "held out of sample on the S&P, Dow and Nasdaq, about 7 vol-units a year"},
    "fomc": {"rule": "Buy at the close two trading days before a scheduled Fed announcement, sell at the close on announcement day.", "name": "FOMC window", "why": "pre-announcement drift before scheduled Fed decisions",
             "test": "the two-day window held out of sample (Nasdaq t 2.5); the day before alone did not"},
    "harvest": {"rule": "Sell at the close of the first trading day on or after 15 June, buy back at the close of the last trading day on or before 30 September.", "name": "Corn pre-harvest short", "why": "the new crop arrives and hedging pressure weighs on price",
                "test": "t 3.6 over 50+ years, 5 of 6 decades positive; held out of sample since 2006 (t 2.6)"},
}
SIDE = {"harvest": "SELL"}
# which strategies run on which market
MARKETS = {"tom": ["ES", "NQ", "YM"], "fdom": ["ES", "NQ", "YM"], "halloween": ["ES", "NQ", "YM"],
           "fomc": ["ES", "NQ", "YM"], "harvest": ["ZC"]}


def _bdays(start, n):
    return pd.Timestamp(np.busday_offset(start.date(), n, roll="forward"))


def occurrences(p, kind, until):
    """(entry date, exit date) of every occurrence, entry and exit at the close; future ones projected on weekdays"""
    idx = p.index
    allday = idx.append(pd.DatetimeIndex([_bdays(idx[-1], i) for i in range(1, 300)]))
    out = []
    if kind in ("tom", "fdom"):
        mon = pd.Series(allday, index=allday).groupby([allday.year, allday.month])
        groups = [g.to_numpy() for _, g in mon]
        for a, b in zip(groups[:-1], groups[1:]):
            if kind == "tom" and len(a) >= 5 and len(b) >= 3:
                out.append((pd.Timestamp(a[-5]), pd.Timestamp(b[2])))
            if kind == "fdom":
                out.append((pd.Timestamp(a[-1]), pd.Timestamp(b[0])))
    elif kind == "halloween":
        for y in range(idx[0].year, until.year + 1):
            octo = allday[(allday.year == y) & (allday.month == 10)]
            apr = allday[(allday.year == y + 1) & (allday.month == 4)]
            if len(octo) and len(apr):
                out.append((octo[-1], apr[-1]))
    elif kind == "harvest":
        for y in range(idx[0].year, until.year + 2):
            a = allday[allday >= pd.Timestamp(f"{y}-06-15")]
            b = allday[allday <= pd.Timestamp(f"{y}-09-30")]
            if len(a) and len(b) and a[0] < b[-1]:
                out.append((a[0], b[-1]))
    elif kind == "fomc":
        for d in FOMC:
            i = allday.searchsorted(d)
            if 2 <= i < len(allday) and allday[i] == d:
                out.append((allday[i - 2], allday[i]))
    return out


def strategy(p, kind, today):
    meta = EVENTS[kind]
    side = SIDE.get(kind, "BUY")
    sg = 1 if side == "BUY" else -1
    occ = occurrences(p, kind, today)
    cut = today - pd.DateOffset(years=NY)
    done = [(a, b) for a, b in occ if a >= cut and b <= today and b <= p.index[-1] and a in p.index and b in p.index]
    hist = [{"d": str(a.date()), "r": round(float(100 * sg * (p.loc[b] / p.loc[a] - 1)), 2)} for a, b in done]
    r = np.array([h["r"] for h in hist])
    live = [(a, b) for a, b in occ if a < today <= b]
    nxt = [(a, b) for a, b in occ if a >= today]
    cur = live[0] if live else (nxt[0] if nxt else None)
    z = r / r.std(ddof=1) if len(r) > 2 and r.std() > 0 else r
    return {"kind": kind, **meta, "side": side,
            "n": len(r), "win": round(100 * float((r > 0).mean()), 1) if len(r) else None,
            "avg": round(float(r.mean()), 2) if len(r) else None,
            "median": round(float(np.median(r)), 2) if len(r) else None,
            "t": round(float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))), 2) if len(r) > 2 else None,
            "active": bool(live),
            "entry": str(cur[0].date()) if cur else None, "exit": str(cur[1].date()) if cur else None,
            "days_to": int(np.busday_count(today.date(), cur[0].date())) if cur and not live else 0,
            "days_left": int(np.busday_count(today.date(), cur[1].date())) if cur and live else None,
            "hist": hist}
