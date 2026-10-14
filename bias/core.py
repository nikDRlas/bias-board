"""Shared data loading and constants for the Bias Board.

Dates: OUTLOOK_DATE (YYYY-MM-DD, env) sets the report date, default today (UTC). The COT
report used is the latest one released (Tuesday data, Friday release) by that date, and prices
are cut at that date, so an older report date rebuilds that week's board without hindsight.
"""
import json, os
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "data", "live")       # pulled each run (gitignored)
CFTC = os.path.join(ROOT, "data", "cftc")       # CFTC legacy history, static
DRIFT_N = 252
LB = {"6 mo": 26, "1 yr": 52, "2 yr": 104, "3 yr": 156, "Multi-yr": 260}
HIST = {"6 mo": 5, "1 yr": 5, "2 yr": 8, "3 yr": 12, "Multi-yr": 15}   # years of past cases per lookback
HI, LO = 80.0, 20.0
BAR_N, BAR_WIN = 6, 60.0

# key: name, LSE COT symbol, spot is USD/XXX (invert to futures direction), sector
M = {
    "GC": ("Gold", "GC", 0, "Metals"), "SI": ("Silver", "SI", 0, "Metals"),
    "PL": ("Platinum", "PL", 0, "Metals"), "PA": ("Palladium", "PA", 0, "Metals"),
    "HG": ("Copper", "HG", 0, "Metals"), "CL": ("WTI Crude Oil", "CL", 0, "Energy"),
    "NG": ("Natural Gas", "NG", 0, "Energy"), "6E": ("Euro FX", "E6", 0, "FX"),
    "DX": ("US Dollar Index", "DX", 0, "FX"), "6B": ("British Pound", "B6", 0, "FX"),
    "6J": ("Japanese Yen", "J6", 1, "FX"), "6S": ("Swiss Franc", "S6", 1, "FX"),
    "6A": ("Australian Dollar", "A6", 0, "FX"), "6C": ("Canadian Dollar", "D6", 1, "FX"),
    "6N": ("NZ Dollar", "N6", 0, "FX"),
}
# LSE's CL and NG COT history is a different contract before 2026: use the CFTC series, append LSE after it
CFTC_ONLY = {"CL", "NG"}

TODAY = pd.Timestamp(os.environ.get("OUTLOOK_DATE") or pd.Timestamp.utcnow().date()).normalize()

_COT = None


def _cot_raw():
    global _COT
    if _COT is None:
        _COT = pd.DataFrame(json.load(open(os.path.join(LIVE, "cot.json"))))
        _COT["date"] = pd.to_datetime(_COT["date"])
    return _COT


def _asof():
    d = sorted(_cot_raw()["date"].unique())
    return pd.Timestamp(max(x for x in d if pd.Timestamp(x) + pd.Timedelta(days=3) <= TODAY))


ASOF = _asof() if os.path.exists(os.path.join(LIVE, "cot.json")) else None


def _raw(k):
    p = pd.read_csv(os.path.join(LIVE, f"{k}.csv"), parse_dates=["ts"]).set_index("ts").close
    p = p[p.index.dayofweek < 5]
    return p[p.index <= TODAY]


def load_px(k):
    if k == "DX":          # ICE formula; LSE's own DXY candle only starts 2026-06
        legs = pd.DataFrame({x: _raw(x) for x in ("6E", "6J", "6B", "6C", "SEK", "6S")}).dropna()
        return (50.14348112 * legs["6E"] ** -0.576 * legs["6J"] ** 0.136 * legs["6B"] ** -0.119
                * legs["6C"] ** 0.091 * legs["SEK"] ** 0.042 * legs["6S"] ** 0.036)
    p = _raw(k)
    return 1.0 / p if M[k][2] else p


def load_cot(k):
    c = _cot_raw()
    d = c[c.symbol == M[k][1]].drop_duplicates("date", keep="last").set_index("date").sort_index()
    lse = pd.DataFrame({"comm": d.comm_long - d.comm_short, "fund": d.noncomm_long - d.noncomm_short})
    f = pd.DataFrame(json.load(open(os.path.join(CFTC, f"{k}_legacy.json"))))
    f["date"] = pd.to_datetime(f.report_date_as_yyyy_mm_dd)
    f = f.drop(columns="report_date_as_yyyy_mm_dd").set_index("date").sort_index().astype(float)
    f = f[~f.index.duplicated()]
    cf = pd.DataFrame({"comm": f.comm_positions_long_all - f.comm_positions_short_all,
                       "fund": f.noncomm_positions_long_all - f.noncomm_positions_short_all})
    j = cf.join(lse, how="inner", rsuffix="_l").tail(8)       # both sources must agree where both are current
    assert (j.comm == j.comm_l).all() and (j.fund == j.fund_l).all(), k
    x = pd.concat([cf, lse[lse.index > cf.index.max()]]) if k in CFTC_ONLY \
        else pd.concat([cf[cf.index < lse.index.min()], lse])
    x["retail"] = -(x.comm + x.fund)                          # longs == shorts across the three groups
    return x[x.index <= ASOF]


def pctile(s, L):
    """share of the last L weekly nets (current included) strictly below the current one"""
    return s.rolling(L).apply(lambda w: (w[:-1] < w[-1]).sum() / L * 100.0, raw=True)
