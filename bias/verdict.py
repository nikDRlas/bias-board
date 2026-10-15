"""The board's verdict rule, shared by build.py and research/verdict_test.py.

  COT and calendar agree                 -> that side            "COT + calendar"
  only COT has a side                    -> COT's side           "COT only"
  only the calendar has a side           -> the calendar's side  "Calendar only"
  they contradict, and the window already paid in >= 2/3 of its past years
  where COT was against it (>= 3 such years)   -> calendar       "Calendar over COT"
  they contradict otherwise              -> no bias              "Conflict · COT relevant"
"""
SIDES = ("BULLISH", "BEARISH")


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
    return "STAND ASIDE", ("No side · groups disagree" if cot == "MIXED" else "No side")


def horizon(basis):
    """how long a verdict is held in the tests: COT-led verdicts 8 weeks, calendar-led ones to the window end"""
    return "window" if basis in ("Calendar only", "Calendar over COT") else "8w"
