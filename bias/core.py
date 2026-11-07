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
    """the latest COT report released by TODAY (Friday release = report Tuesday + 3 days), from LSE's archive or the
    CFTC's own data, whichever is newer"""
    d = [pd.Timestamp(x) for x in _cot_raw()["date"].unique()]
    g = os.path.join(CFTC, "GC_legacy.json")
    if os.path.exists(g):
        d += [pd.Timestamp(r["report_date_as_yyyy_mm_dd"][:10]) for r in json.load(open(g))]
    return max(x for x in d if x + pd.Timedelta(days=3) <= TODAY)


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


# research switch (2026-11-05, research/cot_new_test.py): which CFTC report the COT groups come from. Default legacy.
#   legacy06  legacy, cut to June 2006 (the newer reports' start), to separate the group definition from history length
#   pm        commodities: commercials = producer/merchant, funds = managed money (disaggregated report)
#             currencies + indices: commercials = dealers, funds = leveraged funds (TFF report)
#   wide      commodities: producer/merchant + swap dealers vs managed money + other reportables
#             currencies + indices: dealers + asset managers vs leveraged funds + other reportables
#   am        currencies + indices: commercials = asset managers, funds = leveraged funds; commodities as pm
#   pmsw_mm / pm_mmo / sw_mm   commodities only (COT_SRC_SCOPE=cmdty), groupings as named in _NEWG
# retail = non-reportables in every variant. COT_SRC_SCOPE = all / cmdty / fin: which markets switch.
COT_SRC = os.environ.get("COT_SRC", "legacy")
COT_SRC_SCOPE = os.environ.get("COT_SRC_SCOPE", "all")
_NEWG = {"dis": {"pm": (["prod_merc"], ["m_money"]), "wide": (["prod_merc", "swap"], ["m_money", "other_rept"]),
                 "am": (["prod_merc"], ["m_money"]),
                 "pmsw_mm": (["prod_merc", "swap"], ["m_money"]),      # legacy commercials vs managed money only
                 "pm_mmo": (["prod_merc"], ["m_money", "other_rept"]),  # producers only vs all large specs
                 "sw_mm": (["swap"], ["m_money"])},                    # swap dealers vs managed money
         "tff": {"pm": (["dealer"], ["lev_money"]), "wide": (["dealer", "asset_mgr"], ["lev_money", "other_rept"]),
                 "am": (["asset_mgr"], ["lev_money"])}}


def _net(f, g):
    lo = next(c for c in f.columns if c.startswith(g + "_positions_long"))
    sh = next(c for c in f.columns if c.startswith(g + "_positions_short") or c.startswith(g + "__positions_short"))
    return f[lo] - f[sh]


def _load_cot_new(k):
    fin = M[k][3] in ("FX", "Indices") or k == "DX"
    tag = "tff" if fin else "dis"
    f = pd.DataFrame(json.load(open(os.path.join(ROOT, "data", "cftc_new", f"{k}_{tag}.json"))))
    f["date"] = pd.to_datetime(f.report_date_as_yyyy_mm_dd)
    f = f.drop(columns="report_date_as_yyyy_mm_dd").set_index("date").sort_index().astype(float)
    f = f[~f.index.duplicated()]
    cg, fg = _NEWG[tag][COT_SRC]
    x = pd.DataFrame({"comm": sum(_net(f, g) for g in cg), "fund": sum(_net(f, g) for g in fg),
                      "retail": _net(f, "nonrept")})
    return x[x.index <= ASOF]


def load_cot(k):
    if COT_SRC != "legacy":
        fin = M[k][3] in ("FX", "Indices") or k == "DX"
        if COT_SRC_SCOPE == "all" or (COT_SRC_SCOPE == "fin") == fin:
            if COT_SRC == "legacy06":
                x = _load_cot_legacy(k)
                return x[x.index >= "2006-06-13"]
            return _load_cot_new(k)
    return _load_cot_legacy(k)


def _load_cot_legacy(k):
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
    agree = bool((j.comm == j.comm_l).all() and (j.fund == j.fund_l).all())
    if not agree:                                              # a revised or shifted LSE row must not stop the build
        print(f"{k}: LSE and CFTC COT differ on recent reports, CFTC series used alone")
    x = pd.concat([cf, lse[lse.index > cf.index.max()]]) if (k in CFTC_ONLY or not agree) \
        else pd.concat([cf[cf.index < lse.index.min()], lse])
    x = pd.concat([x, cf[cf.index > x.index.max()]])          # the CFTC's newest reports, if LSE does not have them yet
    x["retail"] = -(x.comm + x.fund)                          # longs == shorts across the three groups
    return x[x.index <= ASOF]


# ---------------------------------------------------------------- full-range swing (wicks included)
# the move a setup made, measured on daily highs/lows: price did the move even if it did not close there (user 2026-11-07,
# research/swing_hl_test.py). Markets without a high/low history use closes.
NO_HL = {"DX", "KC", "LE"}


WICK_CAP = 3.0     # a wick may reach at most this many usual daily ranges beyond the day's or the previous day's close


def load_hl(k):
    """daily high and low on load_px's index, in the board's direction convention (inverted FX: 1/low, 1/high).
    The LSE feed has bad prints (corn high 18.66 on a 4.50 day, 13 Mar 2026; currency wicks of 15-25%; a few closes that
    jump 10-27% for one day and snap back, e.g. 6C 20 Dec 2024). Cleaned: a one-day close spike (> 6 daily sigmas, fully
    reversed the next day) counts as the previous close; a wick is capped at WICK_CAP x the median daily range of the
    60 days before, beyond the higher/lower of the day's and the previous day's close."""
    p = load_px(k)
    if k in NO_HL or k in EURO:
        return p, p
    d = pd.read_csv(os.path.join(LIVE, f"{k}.csv"), parse_dates=["ts"]).set_index("ts")
    d = d[~d.index.duplicated()].reindex(p.index)
    ok = d.high >= d.low
    h, l, c = d.high.where(ok), d.low.where(ok), d.close.where(ok).fillna(d.close)
    r = np.log(c).diff()
    vol = 1.4826 * r.abs().rolling(60, min_periods=20).median().shift(1)    # robust: one bad day cannot inflate it
    spike = (r.abs() > 6 * vol) & (r.shift(-1).abs() > 6 * vol) & (np.sign(r) != np.sign(r.shift(-1)))
    c = c.where(~spike).ffill()
    h, l = h.where(~spike, c), l.where(~spike, c)
    rng = (h - l).rolling(60, min_periods=20).median().shift(1)
    top, bot = np.maximum(c, c.shift()), np.minimum(c, c.shift())
    h = h.where(~(h > top + WICK_CAP * rng), top + WICK_CAP * rng)
    l = l.where(~(l < bot - WICK_CAP * rng), bot - WICK_CAP * rng)
    if M[k][2]:
        h, l, c = 1 / l, 1 / h, 1 / c
    c = c.reindex(p.index).fillna(p)
    return h.fillna(c).clip(lower=c), l.fillna(c).clip(upper=c)


def swing_path(sg, H, L):
    """per day: the biggest rise from a low to a later high so far (shorts: high to a later low), in %"""
    H, L = np.asarray(H, float), np.asarray(L, float)
    r = H / np.minimum.accumulate(L) - 1 if sg > 0 else np.maximum.accumulate(H) / L - 1
    return 100 * np.maximum.accumulate(r)


def swing_points(sg, H, L, idx):
    """the swing so far as (size %, date of its low, date of its top) - shorts: top first, then the low"""
    sw = swing_path(sg, H, L)
    H, L = np.asarray(H, float), np.asarray(L, float)
    if sg > 0:
        r = H / np.minimum.accumulate(L) - 1
        j = int(np.argmax(r)); i = int(np.argmin(L[:j + 1]))
    else:
        r = np.maximum.accumulate(H) / L - 1
        j = int(np.argmax(r)); i = int(np.argmax(H[:j + 1]))
    return round(float(sw[-1]), 2), str(idx[i].date()), str(idx[j].date())


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

    @property
    def lit(self):
        """the board's signal on every report (slow signals = None), cached"""
        if not hasattr(self, "_lit"):
            self._lit = lit_sides(self, speed_series(self.k))
        return self._lit

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


SPEED_AT_START = os.environ.get("COT_SPEED_AT_START", "0") == "1"   # tested worse: kept off (data/research/cot_speed_start.json)
# re-tested 2026-10-27 on the full board walk-forward (research/verdict_test.py SKIP_SLOW=1 COT_SPEED_AT_START=1):
# weekly 520 verdicts 58.8% won +1.53% total +796% t4.9 (2019-22 +1.28, 2023-26 +1.82) vs judged at start 351 verdicts
# 62.1% +1.66% total +583% t2.6 (2019-22 +0.63, 2023-26 +2.83): fails 2019-22, kept weekly


def lit_sides(reader, sp=None, skip_slow=True):
    """the board's COT side on every weekly report (None = no side); slow signals count as no side. The speed is
    judged once, on the first report of a run of the same raw read: a weekly flicker between 'medium' and 'slow' does
    not split one extreme into several signals. Off by default: judged weekly the speed acts as an early exit and
    tested better (data/research/cot_speed_start.json)"""
    cut = speed_cutoffs() if skip_slow else None
    raw = [reader.read_at(i) for i in range(len(reader.dates))]
    out, start_ok = [], None
    for i, v in enumerate(raw):
        if v not in ("BULLISH", "BEARISH"):
            out.append(None)
            start_ok = None
            continue
        slow = skip_slow and sp is not None and speed_of(sp, i, v, cut) == "slow"
        if not SPEED_AT_START:
            out.append(None if slow else v)
            continue
        if i == 0 or raw[i - 1] != v:
            start_ok = not slow                  # judged when the run starts
        out.append(v if start_ok else None)
    return out


# outside currencies a COT bias is held at least this many weeks after its signal, unless COT flips. Chosen on 2019-26
# (board +549% -> +763%, both halves better; late 4h entries 56% target-first, research/cot_late_entry_test.py). It did
# NOT hold in 2006-18 (research/holdout_cot_hold.py: 8-week hold -1.62% vs blind; the COT signal itself had no edge
# then); the user chose to weight 2019-26 as the relevant regime (2026-10-24). The live record is the check.
COT_MIN_WEEKS = int(os.environ.get("COT_MIN_WEEKS", "8"))


def min_weeks(k):
    return COT_MIN_WEEKS if k is not None and M[k][3] != "FX" else 0


def cot_exit(dates, lit, i, after=HOLD_AFTER, k=None):
    """exit date of a COT trade on report i: `after` weeks past the release of the last report of its lit run; for
    market k outside currencies at least min_weeks(k) after the run's first release, but not past the release of a
    report lit on the other side. None while the run is still lit on the latest report (the exit is not known yet)."""
    v, j = lit[i], i
    while j + 1 < len(lit) and lit[j + 1] == v:
        j += 1
    if j + 1 >= len(lit):
        return None
    ex = dates[j] + pd.Timedelta(days=3) + pd.Timedelta(weeks=after)
    mw = min_weeks(k)
    if mw:
        ex = max(ex, dates[lit_start(lit, i)] + pd.Timedelta(days=3) + pd.Timedelta(weeks=mw))
        flip = next((q for q in range(j + 1, len(lit)) if lit[q] not in (None, v)), None)
        if flip is not None:
            ex = min(ex, dates[flip] + pd.Timedelta(days=3))
    return ex


def held_side(dates, lit, i, t, k):
    """outside currencies: the side a COT verdict is still held on at day t after its signal went dark, and the report
    index of that run; (None, None) if nothing is held (lit now, or past the hold, or currencies)"""
    if not min_weeks(k) or i < 0 or i >= len(lit) or lit[i] is not None:
        return None, None
    q = i
    while q >= 0 and lit[q] is None:
        q -= 1
    if q < 0:
        return None, None
    ex = cot_exit(dates, lit, q, k=k)
    return (lit[q], q) if ex is not None and t < ex else (None, None)


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
COT_REC_YEARS = int(os.environ.get("COT_REC_YEARS", "0"))      # 0 = the whole history since 2003
# tested 2026-10-27 (walk-forward 2019-26): a record of only the last 5 / 7 years is worse in BOTH halves
# (all history 58.8% won +1.53%/verdict; 5y 56.5% +0.88%; 7y 56.6% +0.83%; 2019-22 and 2023-26 both lower) -> keep 0
_CASES = {}


def cot_setups(rd, k):
    """the starts of market k's COT setups: (report index, release date, exit date, side), one per setup. A run
    starts a setup on its first lit report; a run that begins while the previous same-side setup is still held (a
    slow week inside one extreme splits the run, and outside currencies the first piece is held 8 weeks) is the same
    setup and is NOT a new case (before 2026-10-27 it was: 19% of all cases were such second pieces of one move)"""
    lit = rd.lit
    out, held_to = [], {}
    for i in range(len(rd.dates)):
        v = lit[i]
        if not v or (i and lit[i - 1] == v):
            continue
        rel = rd.dates[i] + pd.Timedelta(days=3)
        if v in held_to and rel < held_to[v]:
            continue
        ex = cot_exit(rd.dates, lit, i, k=k)
        if ex is None:
            break                                    # the live run: nothing finished after it
        held_to[v] = ex
        out.append((i, rel, ex, v))
    return out


def cot_cases(k):
    """every finished COT setup of market k: side, exit date, end move and worst move along the way (in %)"""
    if k in _CASES:
        return _CASES[k]
    p, rd = load_px(k), CotReader(k)
    px = p.to_numpy(float)
    out = []
    for i, rel, ex, v in cot_setups(rd, k):
        if rel < p.index[0]:
            continue
        a, b = p.index.searchsorted(rel), p.index.searchsorted(ex)
        if b >= len(p) or b <= a:
            continue
        sg = 1 if v == "BULLISH" else -1
        seg = sg * (px[a:b + 1] / px[a] - 1)
        out.append({"side": v, "start": rd.dates[i], "exit": p.index[b], "end": 100 * float(seg[-1]), "mae": 100 * float(seg.min()),
                    "mfe": 100 * float(seg.max())})
    _CASES[k] = (out, p)
    return _CASES[k]


def cot_usual(k, side, t, min_cases=5):
    """usual end move of market k's earlier COT setups in `side`, finished by t, in normal daily moves; None if fewer
    than `min_cases`"""
    cs, p = cot_cases(k)
    since = t - pd.DateOffset(years=COT_REC_YEARS) if COT_REC_YEARS else pd.Timestamp("1900-01-01")
    prior = [c["end"] for c in cs if c["side"] == side and since <= c["start"] and c["exit"] <= t]
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


_GATES = {}


def cot_counts(k, side, t):
    """does the board count a COT signal in `side` on market k at t? Currencies: Bernd's evidence gate (bias/bernd.py,
    provisional since 2026-10-19); everything else: the COT minimum (cot_big_enough)"""
    if side not in ("BULLISH", "BEARISH"):
        return False
    if M[k][3] == "FX":
        import bernd
        if k not in _GATES:
            _GATES[k] = bernd.Gate(k)
        return _GATES[k].read(t) == side
    return cot_big_enough(k, side, t)
