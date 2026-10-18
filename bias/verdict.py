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


def board_read(cot, cal, t, reader):
    """the board's verdict on day t from the COT side (slow signals already removed) and the seasonal calendar.
    A window that agrees with COT counts at any size ("COT + calendar"). A window that has to carry the bias alone
    (calendar only, or calendar over COT) must have a usual move of at least seasonal.SOLO_MIN_MOVE normal daily
    moves; a smaller one is ignored. Returns verdict, basis and the (windows, status) of the calendar used."""
    import seasonal as SS
    every = cal.windows(t, min_move=0)
    if cot in SIDES and _side(*every) == cot:
        return cot, "COT + calendar", every
    solo = cal.windows(t, min_move=SS.SOLO_MIN_MOVE) if SS.SOLO_MIN_MOVE > 0 else every
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
COT_DONE_AT = 1.5          # COT setup done at 150% of its usual winning move (research/cot_done_yardstick_test.py)


def final_read(k, v, basis, t, p, cal, ws, rd, lit, macro_sign=None):
    """the validated 'nothing left' situations turn a bias into no bias:
      macro against   on US indices, gold and silver the US macro score points the other way (or is flat):
                      such verdicts made about nothing above holding the market (research/tools_macro_align.py)
      move done       the calendar window already made its usual move this year, or the COT setup already made 150%
                      of its usual winning move (research/move_done_test.py, research/cot_done_yardstick_test.py)"""
    if v not in SIDES:
        return v, basis
    sg = 1 if v == "BULLISH" else -1
    if k in US_DRIVEN and macro_sign is not None and macro_sign != sg:
        return "STAND ASIDE", "Macro against"
    if horizon(basis) == "window":
        d = ws[0]
        r = cal.remaining(t, d)
        if r and r["started"] and r["so_far"] is not None and sg * d["avg"] > 0 and sg * r["so_far"] >= sg * d["avg"]:
            return "STAND ASIDE", "Move done"
    else:
        import core as C
        i = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
        if 0 <= i < len(lit) and lit[i] == v:
            j = C.lit_start(lit, i)
            a = p.index.searchsorted(rd.dates[j] + pd.Timedelta(days=3))
            c = p.index.searchsorted(t, "right") - 1
            cs, _ = C.cot_cases(k)
            wins = [x["end"] for x in cs if x["side"] == v and x["exit"] <= t and x["end"] > 0]
            if wins and c > a:
                so_far = 100 * sg * (p.iloc[c] / p.iloc[a] - 1)
                if so_far >= COT_DONE_AT * float(np.mean(wins)):
                    return "STAND ASIDE", "Move done"
    return v, basis
