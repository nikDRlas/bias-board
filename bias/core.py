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
    "ES": ("S&P 500", "ES", 0, "Indices"), "NQ": ("Nasdaq 100", "NQ", 0, "Indices"),
    "YM": ("Dow Jones", "YM", 0, "Indices"),
    "ZC": ("Corn", "ZC", 0, "Agriculture"), "ZW": ("Wheat", "ZW", 0, "Agriculture"),
    "ZS": ("Soybeans", "ZS", 0, "Agriculture"), "SB": ("Sugar", "SB", 0, "Agriculture"),
    "KC": ("Coffee", "KC", 0, "Agriculture"), "LE": ("Live Cattle", "LE", 0, "Agriculture"),
}
# LSE has these only from 2026: history = TradingView back-adjusted continuous futures (data/history, to May 2026),
# continued with LSE daily prices rescaled at the overlap. Win ratios are exact; % averages are approximate.
# (cotton and orange juice were left out: their back-adjusted history sits at or below zero for years)
SPLICED = {"KC", "LE"}
EURO = {"DAX", "ESTX"}
# DAX and Euro Stoxx 50 (quant strategies only): Eurex futures history; LSE's index series mixes in an unrelated
# instrument from April 2024 to early 2025, so only its clean recent part continues the history
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


def _spliced(k):
    h = pd.read_csv(os.path.join(ROOT, "data", "history", f"{k}_tv.csv"), parse_dates=["date"]).set_index("date").close
    live = _raw(k)
    j = pd.DataFrame({"h": h, "l": live}).dropna()
    rr = j.h / j.l
    rr = rr[(rr / rr.median()).between(0.8, 1.25)]          # ignore days where the live feed shows another instrument
    ratio = float(rr.median())
    p = pd.concat([h, live[live.index > h.index[-1]] * ratio])
    p = p[p.index.dayofweek < 5]
    return p[p.index <= TODAY]


def _euro(k):
    """chained from returns: LSE index data until 8 Apr 2024, Eurex futures history (data/history) until it ends,
    LSE again after that. LSE mixes in an unrelated instrument from 9 Apr 2024 to early 2025; the futures history is
    additively back-adjusted, which only distorts % moves far back, so only its recent stretch is used."""
    lse = _raw(k)
    tv = pd.read_csv(os.path.join(ROOT, "data", "history", f"{k}_tv.csv"), parse_dates=["date"]).set_index("date").close
    cut1, cut2 = pd.Timestamp("2024-04-08"), tv.index[-1]
    r = pd.concat([np.log(lse[lse.index <= cut1]).diff().dropna(),
                   np.log(tv[(tv.index >= cut1)]).diff().dropna()[lambda x: x.index > cut1],
                   np.log(lse[lse.index >= cut2]).diff().dropna()[lambda x: x.index > cut2]])
    r = r[~r.index.duplicated()].sort_index()
    if (r.abs() > 0.2).any():
        raise ValueError(f"{k}: implausible daily move in the chained series")
    p = float(lse.iloc[0]) * np.exp(r.cumsum())
    p = pd.concat([pd.Series([float(lse.iloc[0])], index=[lse.index[0]]), p])
    p = p[p.index.dayofweek < 5]
    return p[p.index <= TODAY]


def load_px(k):
    if k in EURO:
        return _euro(k)
    if k in SPLICED:
        return _spliced(k)
    if k == "DX":          # ICE formula; LSE's own DXY candle only starts 2026-06
        legs = pd.DataFrame({x: _raw(x) for x in ("6E", "6J", "6B", "6C", "SEK", "6S")}).dropna()
        return (50.14348112 * legs["6E"] ** -0.576 * legs["6J"] ** 0.136 * legs["6B"] ** -0.119
                * legs["6C"] ** 0.091 * legs["SEK"] ** 0.042 * legs["6S"] ** 0.036)
    p = _raw(k)
    return 1.0 / p if k in M and M[k][2] else p


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


# markets where a bearish COT signal counts as no side: on the US indices bearish signals lost money (41% won, -0.72%,
# worse than the index drift, both halves) while bullish ones beat the drift (68% won); research/cot_indices_test.py
LONG_ONLY = {"ES", "NQ", "YM"}


class CotReader:
    """The COT read: commercials at an extreme (>= 2 of their 5 lookbacks at the same extreme) are followed, but only
    when retail or the funds (non-commercials) sit at the OPPOSITE extreme (also >= 2 of 5), and the funds are not at an
    extreme on the commercials' own side. Otherwise no side.
    last_groups = how many speculator groups oppose the commercials (1 or 2).
    Uses the latest report RELEASED (Friday) by the given day. Tested in research/opposite_test.py."""

    def __init__(self, k):
        x = load_cot(k)
        self.k = k
        self.dates = x.index
        self.P = {g: {lb: pctile(x[g], L).to_numpy() for lb, L in LB.items()} for g in ("retail", "comm", "fund")}
        self.last_groups = 0

    def read(self, t):
        return self.read_at(self.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1)

    def side(self, g, i):
        s = [("hi" if v >= HI else "lo") for v in (self.P[g][lb][i] for lb in LB) if np.isfinite(v) and (v >= HI or v <= LO)]
        return s[0] if len(s) >= 2 and len(set(s)) == 1 else None

    def read_at(self, i):
        """the read on the i-th weekly report"""
        self.last_groups = 0
        self.skipped_short = False
        if i < 0:
            return "NEUTRAL"
        c = self.side("comm", i)
        if not c:
            return "NEUTRAL"
        opp = "lo" if c == "hi" else "hi"
        if self.side("fund", i) == c:
            return "NEUTRAL"        # funds on the commercials' side: no side (research/third_group_test.py, case E)
        n = (self.side("retail", i) == opp) + (self.side("fund", i) == opp)
        if not n:
            return "NEUTRAL"
        if c == "lo" and self.k in LONG_ONLY:
            self.skipped_short = True
            return "NEUTRAL"        # bearish COT on the US indices: no side (research/cot_indices_test.py)
        self.last_groups = int(n)
        return "BULLISH" if c == "hi" else "BEARISH"


# ---------------------------------------------------------------- how long a COT trade is held
# Held while the signal stays lit on each new weekly report, out one week after the last lit report's release
# (research/cot_lit_hold_test.py: best of lit+0/1/2/4 weeks and fixed 2/4/8 weeks, one trade per setup).
HOLD_AFTER = 1
# a COT trade's length depends on its outcome (losers tend to stay lit longer), so its result is scaled by this fixed
# typical length (about 3.5 weeks), never by its own length, which would shrink the long losers
COT_REF_DAYS = 17
SPEED_FILE = os.path.join(ROOT, "data", "research", "cot_speed.json")


def speed_series(k):
    """the commercials' 4-week net change in units of its prior 3-year standard deviation, per weekly report"""
    d4 = load_cot(k)["comm"].diff(4)
    return (d4 / d4.rolling(156, min_periods=52).std().shift(1)).to_numpy()


def speed_cutoffs():
    return json.load(open(SPEED_FILE))["move4w"]["cutoffs"] if os.path.exists(SPEED_FILE) else None


def speed_of(sp, i, side, cut=None):
    cut = cut or speed_cutoffs()
    v = sp[i] * (1 if side == "BULLISH" else -1) if 0 <= i < len(sp) and np.isfinite(sp[i]) else np.nan
    if not np.isfinite(v) or not cut:
        return None
    return "fast" if v > cut[1] else "slow" if v <= cut[0] else "medium"


def lit_sides(reader, sp=None, skip_slow=True):
    """the board's COT side on every weekly report (None = no side); slow signals count as no side"""
    cut = speed_cutoffs() if skip_slow else None
    out = []
    for i in range(len(reader.dates)):
        v = reader.read_at(i)
        if v not in ("BULLISH", "BEARISH") or (skip_slow and sp is not None and speed_of(sp, i, v, cut) == "slow"):
            v = None
        out.append(v)
    return out


def cot_exit(dates, lit, i, after=HOLD_AFTER):
    """exit date of a COT trade on report i: `after` weeks past the release of the last report of its lit run.
    None while the run is still lit on the latest report (the exit is not known yet)."""
    v, j = lit[i], i
    while j + 1 < len(lit) and lit[j + 1] == v:
        j += 1
    if j + 1 >= len(lit):
        return None
    return dates[j] + pd.Timedelta(days=3) + pd.Timedelta(weeks=after)


def lit_start(lit, i):
    """first report of the lit run that report i belongs to"""
    while i > 0 and lit[i - 1] == lit[i]:
        i -= 1
    return i


# ---------------------------------------------------------------- size of a market's own COT record
# A COT signal only counts if the market's earlier setups in that direction (one per lit run, held while lit + 1 week,
# finished by then) usually moved at least COT_MIN_MOVE normal daily moves (research/cot_record_size_test.py; grid
# -0.25..1 in data/research/cot_min_grid.json: plateau 0-0.5, 0.5 chosen on 2019-22 and confirmed on 2023-26).
COT_MIN_MOVE = float(os.environ.get("COT_MIN_MOVE", "0.5"))
_CASES = {}


def cot_cases(k):
    """every finished COT setup of market k: side, exit date, end move and worst move along the way (in %)"""
    if k in _CASES:
        return _CASES[k]
    p, rd = load_px(k), CotReader(k)
    lit = lit_sides(rd, speed_series(k))
    px = p.to_numpy(float)
    out = []
    for i in range(len(rd.dates)):
        v = lit[i]
        if not v or (i and lit[i - 1] == v):
            continue
        ex = cot_exit(rd.dates, lit, i)
        rel = rd.dates[i] + pd.Timedelta(days=3)
        if ex is None or rel < p.index[0]:
            continue
        a, b = p.index.searchsorted(rel), p.index.searchsorted(ex)
        if b >= len(p) or b <= a:
            continue
        sg = 1 if v == "BULLISH" else -1
        seg = sg * (px[a:b + 1] / px[a] - 1)
        out.append({"side": v, "start": rd.dates[i], "exit": p.index[b], "end": 100 * float(seg[-1]), "mae": 100 * float(seg.min())})
    _CASES[k] = (out, p)
    return _CASES[k]


def cot_usual(k, side, t, min_cases=5):
    """usual end move of market k's earlier COT setups in `side`, finished by t, in normal daily moves; None if fewer
    than `min_cases`"""
    cs, p = cot_cases(k)
    prior = [c["end"] for c in cs if c["side"] == side and c["exit"] <= t]
    if len(prior) < min_cases:
        return None
    ti = p.index.searchsorted(t)
    lr = np.diff(np.log(p.to_numpy(float)[max(0, ti - 253):ti]))
    vol = 100 * lr.std() if len(lr) > 20 else np.nan
    return float(np.mean(prior)) / vol if vol else None


def cot_big_enough(k, side, t):
    """does a COT signal in `side` clear the minimum record size (no minimum when the record is too short)?"""
    if COT_MIN_MOVE <= -90 or side not in ("BULLISH", "BEARISH"):
        return True
    u = cot_usual(k, side, t)
    return u is None or u >= COT_MIN_MOVE
