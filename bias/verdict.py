"""The board's verdict rule, shared by build.py and research/verdict_test.py.

  COT and calendar agree                 -> that side            "COT + calendar"
  only COT has a side                    -> COT's side           "COT only"
  only the calendar has a side           -> the calendar's side  "Calendar only"
  they contradict, and the window already paid in >= 2/3 of its past years
  where COT was against it (>= 3 such years)   -> calendar       "Calendar over COT"
  they contradict otherwise              -> no bias              "Conflict · COT relevant"
"""
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
