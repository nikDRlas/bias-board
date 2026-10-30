"""Macro score rebuilt from the LSE economic calendar (data/macro/calendar_lse.csv.gz), the way the EdgeFinder replica
scores it (Projektbericht 16.09.2026): each indicator's latest release scores +1 above consensus, -1 below, 0 equal
(no consensus: against the previous value); unemployment and jobless claims count the other way round. A country's
score per group (growth, inflation, labour) is the sum of its indicators' latest values. Markets: a currency carries
its own country's score; US indices and commodities the US score with inflation inverted; gold and silver the US score
fully inverted."""
import json, os, re
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = os.path.join(ROOT, "data", "macro", "calendar_lse.csv.gz")
GROUPS = {"growth": ["GDP", "Retail", "MfgPMI", "SvcPMI", "ConsConf"], "inflation": ["CPI", "PPI", "PCE"],
          "labour": ["NFP", "ADP", "Claims", "JOLTS", "Unemp"]}
INVERT = {"Claims", "Unemp"}
REGION = {"USD": "US", "EUR": "EU", "GBP": "UK", "JPY": "JP", "CHF": "CH", "AUD": "AU", "CAD": "CA", "NZD": "NZ"}
# LSE event chosen per country and indicator (research/macro_calibrate.py picks them by matching the replica);
# Switzerland and New Zealand are on the calendar only from Feb 2026, so they use the same indicators by name
EVENTS_FILE = os.path.join(ROOT, "data", "macro", "events.json")
EVENTS = json.load(open(EVENTS_FILE))["events"] if os.path.exists(EVENTS_FILE) else {}
# market -> (country, sign of inflation, sign of everything): currencies their own country; US indices and
# commodities the US score with inflation inverted; gold and silver the US score fully inverted
MARKET = {"6E": ("EUR", 1, 1), "6B": ("GBP", 1, 1), "6J": ("JPY", 1, 1), "6S": ("CHF", 1, 1), "6A": ("AUD", 1, 1),
          "6C": ("CAD", 1, 1), "6N": ("NZD", 1, 1), "DX": ("USD", 1, 1),
          "ES": ("USD", -1, 1), "NQ": ("USD", -1, 1), "YM": ("USD", -1, 1), "CL": ("USD", -1, 1), "NG": ("USD", -1, 1),
          "HG": ("USD", -1, 1), "PL": ("USD", -1, 1), "GC": ("USD", 1, -1), "SI": ("USD", 1, -1)}

_num = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([KMBT%]?)")


def num(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    m = _num.match(str(x).replace(",", ""))
    if not m:
        return np.nan
    v = float(m.group(1))
    return v * {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}.get(m.group(2), 1)


_PERIOD = re.compile(r"\s+(?:(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(?:/\d{1,2})?|Q[1-4]|H[12]|\d{4})$")


_ALIAS = [(re.compile(r"^(IHS Markit|Markit/CIPS|Markit|S&P Global/CIPS|au Jibun Bank|Jibun Bank|Judo Bank|AiG|Commonwealth Bank)\s+", re.I), "S&P Global ")]
_STAGE = re.compile(r"\s+(Flash|Final|Prel|Preliminary|Adv|Advance|2nd Est|3rd Est|Third Estimate|Second Estimate)$", re.I)


def norm_event(e):
    """one name per indicator over the whole history: older rows carry the period ('Non Farm Payrolls DEC',
    'GDP Growth Rate QoQ Adv Q3'), newer ones do not; renamed PMIs (Markit -> S&P Global) are merged"""
    e = str(e).strip()
    for rx, rep in _ALIAS:
        e = rx.sub(rep, e)
    while True:
        e2 = _PERIOD.sub("", e)
        if e2 == e:
            return e
        e = e2


def load_calendar():
    c = pd.read_csv(CAL, low_memory=False)
    c["region_code"] = c["region_code"].replace({"EA": "EU", "GB": "UK"})   # older rows use EA / GB
    c["event"] = c["event"].map(norm_event)
    # also every release of an indicator whatever its stage (flash / preliminary / final ...), as 'ALL <name>'
    base = c.copy()
    base["event"] = "ALL " + base["event"].map(lambda e: _STAGE.sub("", e))
    c = pd.concat([c, base], ignore_index=True)
    c["day"] = pd.to_datetime(c["date"])
    for col in ("actual", "consensus", "previous"):
        c[col + "_n"] = c[col].map(num)
    c = c[c.actual_n.notna()]
    ref = np.where(c.consensus_n.notna(), c.consensus_n, c.previous_n)
    c["surprise"] = np.sign(c.actual_n - ref)
    return c[np.isfinite(c.surprise)]


def cell_series(cal, region, event, days, invert=False):
    """daily value of one indicator: the sign of its latest release's surprise"""
    s = cal[(cal.region_code == region) & (cal.event == event)].sort_values(["day", "time"]).groupby("day").surprise.last()
    if invert:
        s = -s
    s.index = pd.DatetimeIndex(s.index).astype("datetime64[ns]")
    return s.reindex(s.index.union(days)).ffill().reindex(days).fillna(0)


YIELDS = os.path.join(ROOT, "data", "macro", "yields_2y_lse.csv")
Y2 = {"USD": "US2Y", "EUR": "DE2Y", "GBP": "UK2Y", "JPY": "JP2Y", "AUD": "AU2Y", "CAD": "CA2Y", "CHF": "CH2Y", "NZD": "NZ2Y"}
RATE_DAYS = 20                                          # matched on the replica: 2-year yield vs 20 trading days earlier


US2Y = os.path.join(ROOT, "data", "macro", "us2y_lse.csv")      # current US 2-year (sovereign series), pulled weekly


def rate_cell(cur, days):
    """the inflation group's rate cell: +1 when the country's 2-year yield is above its level 20 trading days earlier,
    -1 below; 0 where there are no yields. US: the current sovereign series (pulled weekly); others: LSE's yield table,
    which stops on 10 Sep 2026"""
    if cur == "USD" and os.path.exists(US2Y):
        y = pd.read_csv(US2Y)
        y = pd.Series(y.value.values, index=pd.to_datetime(y.date)).astype(float)
    elif os.path.exists(YIELDS):
        y = pd.read_csv(YIELDS)
        y = y[y.symbol == Y2[cur]]
        y = pd.Series(y.close.values, index=pd.to_datetime(y.date)).astype(float)
    else:
        return pd.Series(0.0, index=days)
    y = y[~y.index.duplicated()].sort_index()
    cell = np.sign(y - y.shift(RATE_DAYS))
    cell.index = pd.DatetimeIndex(cell.index).astype("datetime64[ns]")
    out = cell.reindex(cell.index.union(days)).ffill().reindex(days)
    out[days > y.index.max()] = np.nan
    return out.fillna(0)


def country_groups(cal, cur, days, events=None, rates=True):
    ev = events or EVENTS
    out = {}
    for g, inds in GROUPS.items():
        tot = pd.Series(0.0, index=days)
        for ind in inds:
            e = ev.get(cur, {}).get(ind)
            if e:
                tot += cell_series(cal, REGION[cur], e, days, ind in INVERT)
        if g == "inflation" and rates:
            tot += rate_cell(cur, days)
        out[g] = tot
    return pd.DataFrame(out)


def market_scores(cal, k, days):
    """daily growth / inflation / labour / total macro score of board market k"""
    cur, inf, sg = MARKET[k]
    g = country_groups(cal, cur, days)
    g["inflation"] *= inf
    g = sg * g
    g["total"] = g.sum(axis=1)
    return g


US_DRIVEN = ("ES", "NQ", "YM", "GC", "SI")    # where the US macro score is shown (context only since 2026-10-30)
LABEL = {"GDP": "GDP", "Retail": "Retail sales", "MfgPMI": "Manufacturing PMI", "SvcPMI": "Services PMI",
         "ConsConf": "Consumer confidence", "CPI": "CPI", "PPI": "PPI", "PCE": "PCE prices", "NFP": "Payrolls",
         "ADP": "ADP employment", "Claims": "Jobless claims", "JOLTS": "JOLTS openings", "Unemp": "Unemployment rate"}


def board_macro(cal, k, today, side=None):
    """the macro reading for the board page of a US-driven market: score, groups, latest US releases, relation to
    the board's side"""
    if k not in US_DRIVEN:
        return None
    days = pd.date_range(today - pd.Timedelta(days=400), today)
    g = market_scores(cal, k, days).iloc[-1]
    total = int(g["total"])
    sg = int(np.sign(total))
    rel = None
    if side in ("BULLISH", "BEARISH"):
        rel = "flat" if sg == 0 else ("agrees" if sg == (1 if side == "BULLISH" else -1) else "against")
    cur, inf, all_ = MARKET[k]
    ev = EVENTS.get(cur, {})
    rec = cal[(cal.region_code == REGION[cur]) & (cal.event.isin(ev.values())) & (cal.day <= today)].sort_values(["day", "time"])
    inv = {v: i for i, v in ev.items()}
    latest = []
    for e, x in rec.groupby("event"):
        r = x.iloc[-1]
        ind = inv[e]
        cell = -r.surprise if ind in INVERT else r.surprise
        grp = next(gg for gg, inds in GROUPS.items() if ind in inds)
        effect = all_ * (inf if grp == "inflation" else 1) * cell
        latest.append({"indicator": LABEL.get(ind, ind), "group": grp, "date": str(r.day.date()), "actual": r.actual,
                       "consensus": r.consensus if isinstance(r.consensus, str) else None, "previous": r.previous,
                       "surprise": int(r.surprise), "effect": int(effect)})
    latest.sort(key=lambda x: x["date"], reverse=True)
    return {"total": total, "side": "BULLISH" if sg > 0 else "BEARISH" if sg < 0 else "NEUTRAL", "rel": rel,
            "groups": {x: int(g[x]) for x in ("growth", "inflation", "labour")}, "latest": latest,
            "inverted": "inflation" if inf < 0 and all_ > 0 else "all" if all_ < 0 else None}
