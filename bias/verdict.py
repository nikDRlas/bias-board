"""The board's verdict rule, shared by build.py and research/verdict_test.py.

  COT and calendar agree                 -> that side            "COT + calendar"
  only COT has a side                    -> COT's side           "COT only"
  only the calendar has a side           -> the calendar's side  "Calendar only"
  they contradict, and the window already paid in >= 2/3 of its past years
  where COT was against it (>= 3 such years)   -> calendar       "Calendar over COT"
  they contradict otherwise              -> no bias              "Conflict · COT relevant"
"""
import numpy as np, pandas as pd

SIDES = ("BULLISH", "BEARISH")


def _side(ws, status):
    return ("BULLISH" if ws[0]["side"] == "BUY" else "BEARISH") if status == "driver" else None


# where a calendar window may carry a bias alone: agriculture only (harvest, planting, weather repeat every year).
# Elsewhere seasonality counts only when COT agrees. Walk-forward 2019-26: 632 -> 451 verdicts, +0.80% -> +1.22% each,
# total +505% -> +549%, t 2.7 -> 4.3, better in both halves (research/seas_solo_where_test.py). SEAS_SOLO_SECTORS=all: old rule.
_SS = __import__("os").environ.get("SEAS_SOLO_SECTORS", "Agriculture")
SOLO_SECTORS = set() if _SS == "all" else set(_SS.split(",")) - {""}


def solo_allowed(k):
    return not SOLO_SECTORS or __import__("core").M[k][3] in SOLO_SECTORS


# research switch (2026-10-27): a window below SOLO_MIN_MOVE may still carry an agricultural bias alone when the same
# window (same trading days, same side) was already a 12-of-15 window in each of the last PROVEN_YEARS years
# (each year judged on its own 15 years before; no hindsight). 0 = off. TESTED 2026-10-27, REJECTED: the verdicts it adds
# are a coin flip and fail 2023-26 at every setting: 3 yrs +202 verdicts 51.5% +0.12% (2023-26 48.4%); 5 yrs +105 50.5%
# +0.55% (2023-26 45.7% +0.08%); 7 yrs +44 50.0% +0.29% (2023-26 46.2% -0.13%)
PROVEN_YEARS = int(__import__("os").environ.get("PROVEN_YEARS", "0"))


def proven(cal, Y, w, years=None):
    import seasonal as SS
    years = years or PROVEN_YEARS
    ny, gate = SS.LOOKBACKS[0]
    for y in range(Y - years + 1, Y + 1):
        if any(x not in cal.first for x in range(y - ny, y)):
            return False
        try:
            if cal.stats(y, w["s"], w["len"], w["side"], ny)["wins"] < gate:
                return False
        except (IndexError, KeyError, ValueError):
            return False
    return True


def board_read(cot, cal, t, reader):
    """the board's verdict on day t from the COT side (slow signals already removed) and the seasonal calendar.
    A window that agrees with COT counts at any size ("COT + calendar"). A window may carry the bias alone (calendar
    only, or calendar over COT) only on agricultural markets (solo_allowed), and it must have a usual move of at least seasonal.SOLO_MIN_MOVE normal daily
    moves; a smaller one is ignored. Returns verdict, basis and the (windows, status) of the calendar used."""
    import seasonal as SS
    every = cal.windows(t, min_move=0)
    if cot in SIDES and _side(*every) == cot:
        return cot, "COT + calendar", every
    if reader is not None and not solo_allowed(reader.k):
        v, basis = decide(cot, None)                     # outside agriculture the calendar may not stand alone
        return v, basis, every
    solo = cal.windows(t, min_move=SS.SOLO_MIN_MOVE) if SS.SOLO_MIN_MOVE > 0 else every
    if PROVEN_YEARS and solo[1] != "driver" and every[1] == "driver" and proven(cal, t.year, every[0][0]):
        solo = every                                     # research switch: a small window proven year after year
    seas = _side(*solo)
    if cot in SIDES and seas == cot:
        return cot, "COT + calendar", solo
    ag = cal.past(t.year, solo[0][0], reader)["summary"]["against"] if seas and cot in SIDES and cot != seas else None
    v, basis = decide(cot, seas, ag)
    return v, basis, solo


def decide(cot, seas, past_against=None):
    cd = cot if cot in SIDES else None
    sd = seas if seas in SIDES else None
    if cd and sd:
        if cd == sd:
            return cd, "COT + calendar"
        ag = past_against or {"n": 0, "w": 0}
        if ag["n"] >= 3 and ag["w"] / ag["n"] >= 2 / 3:
            return sd, "Calendar over COT"
        return "STAND ASIDE", "Conflict · COT relevant"
    if cd:
        return cd, "COT only"
    if sd:
        return sd, "Calendar only"
    return "STAND ASIDE", "No side"


def horizon(basis):
    """how long a verdict is held in the tests: COT-led verdicts while the COT signal stays lit + 1 week (core.cot_exit),
    calendar-led ones to the window end"""
    return "window" if basis in ("Calendar only", "Calendar over COT") else "lit"


US_DRIVEN = ("ES", "NQ", "YM", "GC", "SI")
# MACRO GATE switched OFF 2026-10-30 (research/macro_strength_test.py): in the board's own walk-forward 2019-26 the
# verdicts it cancelled were the BETTER ones (US indices + gold/silver, macro against: 64 verdicts 76.6% won +3.50%,
# +2.61% above drift t 3.4; agreeing 38 verdicts 63.2% +2.31%; silver against 84% won). Without it the whole board:
# 538 -> 571 verdicts, 58.9 -> 61.1% won, +1.66 -> +1.82% per verdict, 2019-22 +1.43 -> +1.66, 2023-26 +1.93 -> +2.00.
# The earlier support (tools_macro_align.py) was a 4-week fixed hold every 4th Saturday 2016-26, not the board's rules.
# MACRO_GATE=1 restores it for research
MACRO_GATE = __import__("os").environ.get("MACRO_GATE") == "1"
COT_DONE_AT = 1.5          # COT setup done at 150% of its usual winning move (research/cot_done_yardstick_test.py)
# research switch (2026-10-27): COT_DONE_WK=k -> done when the move since entry is >= k NORMAL WEEKS of the market
# (daily vol over the year before entry x sqrt 5) instead of the market's own winning record (cot_done_general_test.py)
# TESTED 2026-10-27 walk-forward 2019-26: 2 wks 528 verdicts +1.72% (19-22 +1.47, 23-26 +2.00); 3 wks +1.67%; 4 wks
# +1.64%; board (1.5x own winners) 538 +1.66% (+1.43 / +1.93). All within noise of each other; kept off for now
COT_DONE_WK = float(__import__("os").environ.get("COT_DONE_WK", "0"))


DONE_YARD = __import__("os").environ.get("SEAS_DONE", "end")


def final_read(k, v, basis, t, p, cal, ws, rd, lit, macro_sign=None):
    """the validated 'nothing left' situations turn a bias into no bias:
      macro against   (only with MACRO_GATE=1, off since 2026-10-30) on US indices, gold and silver the US macro score
                      points the other way (or is flat); failed the board's walk-forward (research/macro_strength_test.py)
      move done       the calendar window already made its usual move this year, or the COT setup already made 150%
                      of its usual winning move (research/move_done_test.py, research/cot_done_yardstick_test.py)"""
    if v not in SIDES:
        return v, basis
    sg = 1 if v == "BULLISH" else -1
    if MACRO_GATE and k in US_DRIVEN and macro_sign is not None and macro_sign != sg:
        return "STAND ASIDE", "Macro against"
    if horizon(basis) == "window":
        d = ws[0]
        r = cal.remaining(t, d)
        usual = d.get("mfe") if DONE_YARD == "mfe" else sg * d["avg"]       # research switch SEAS_DONE=mfe
        if r and r["started"] and r["so_far"] is not None and sg * d["avg"] > 0 and usual and sg * r["so_far"] >= usual:
            return "STAND ASIDE", "Move done"
    else:
        import core as C
        i = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
        if 0 <= i < len(lit) and lit[i] != v:
            hs, q = C.held_side(rd.dates, lit, i, t, k)
            i = q if hs == v else -1                       # a held verdict: its own run
        if 0 <= i < len(lit) and lit[i] == v:
            j = C.lit_start(lit, i)
            a = p.index.searchsorted(rd.dates[j] + pd.Timedelta(days=3))
            c = p.index.searchsorted(t, "right") - 1
            if COT_DONE_WK and c > a and a >= 253:
                lc = np.log(p.to_numpy(float))
                wk = np.diff(lc[a - 252:a]).std() * np.sqrt(5)
                if sg * (lc[c] - lc[a]) >= COT_DONE_WK * wk:
                    return "STAND ASIDE", "Move done"
                return v, basis
            cs, _ = C.cot_cases(k)
            wins = [x["end"] for x in cs if x["side"] == v and x["exit"] <= t and x["end"] > 0]
            if wins and c > a:
                so_far = 100 * sg * (p.iloc[c] / p.iloc[a] - 1)
                if so_far >= COT_DONE_AT * float(np.mean(wins)):
                    return "STAND ASIDE", "Move done"
    return v, basis
