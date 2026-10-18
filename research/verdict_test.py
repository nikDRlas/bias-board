#!/usr/bin/env python3
"""Walk-forward test of the board's FINAL verdict, the basis of the confidence dots.

Every Saturday since 2019 (the first year the 15-year seasonal scan has data for), for every market, the board's
verdict is rebuilt with only what was known that day: the COT report released by then, the seasonal windows from
the 15 years before, and the shared verdict rule (bias/verdict.py). One position per market at a time.
A COT-led verdict is held while the COT signal stays lit, out one week after the last lit report (bias/core.py cot_exit); a calendar-led verdict to the end of its window. Entry at the next close.

Results by verdict type x asset class -> data/research/verdict.json
Options (environment): SEAS_LB=15 or 15,10 (seasonal lookbacks a window may qualify on), SKIP_SLOW=1 (COT signals the
commercials crept into slowly count as no side), OUT=file name. Every trade records the COT signal's speed.
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
import verdict as VD                                   # noqa: E402
from conflict_test import ret, summary                 # noqa: E402

SECTOR = lambda k: {"FX": "Currencies", "Indices": "Indices", "Agriculture": "Agriculture"}.get(C.M[k][3], "Metals & energy")

LB_CFG = {"15": [(15, 12)], "10": [(10, 8)], "15,10": [(15, 12), (10, 8)]}[os.environ.get("SEAS_LB", os.environ.get("SEAS_YEARS", "15"))]
SKIP_SLOW = os.environ.get("SKIP_SLOW") == "1"
OUT = os.environ.get("OUT", "verdict.json")
GATES = os.environ.get("GATES", "macro,done")          # the final 'nothing left' rules (bias/verdict.py final_read)
speed_series, speed_of = C.speed_series, C.speed_of
LONG_LENS = np.arange(31, 64)


if __name__ == "__main__":
    SS.LOOKBACKS = LB_CFG
    MACRO = {}
    if "macro" in GATES:
        import macro as MC
        _cal = MC.load_calendar()
        _days = pd.date_range("2015-06-01", C.TODAY)
        MACRO = {k: MC.market_scores(_cal, k, _days)["total"] for k in VD.US_DRIVEN}
    end = C.TODAY - pd.Timedelta(days=1)
    rows = []
    for k in C.M:
        p = C.load_px(k)
        cal, rd = SS.Calendar(p), C.CotReader(k)
        sp = speed_series(k)
        lit = C.lit_sides(rd, sp, skip_slow=SKIP_SLOW)
        busy = pd.Timestamp("1900-01-01")
        for t in pd.date_range("2019-01-05", end, freq="W-SAT"):
            if t <= busy:
                continue
            cot = rd.read(t)
            i_rep = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
            spd = speed_of(sp, i_rep, cot) if cot in VD.SIDES else None
            if SKIP_SLOW and spd == "slow":
                cot = "NEUTRAL"
            if cot in VD.SIDES and not C.cot_big_enough(k, cot, t):
                cot = "NEUTRAL"
            v, basis, (ws, status) = VD.board_read(cot, cal, t, rd)
            if v in VD.SIDES and GATES:
                ms = None
                if "macro" in GATES and k in MACRO:
                    s_ = MACRO[k][MACRO[k].index <= t]
                    ms = int(np.sign(s_.iloc[-1])) if len(s_) else None
                v2, b2 = VD.final_read(k, v, basis, t, p, cal, ws, rd, lit, ms)
                if b2 == "Move done" and "done" not in GATES:
                    v2, b2 = v, basis
                v, basis = v2, b2
            if v not in VD.SIDES:
                continue
            if VD.horizon(basis) == "window":
                x = ret(p, max(t, pd.Timestamp(ws[0]["start"])), pd.Timestamp(ws[0]["end"]), v)
            else:
                ex = C.cot_exit(rd.dates, lit, i_rep) if 0 <= i_rep and lit[i_rep] == cot else None
                if ex is None:
                    continue
                x = ret(p, t + pd.Timedelta(days=1), ex, v, C.COT_REF_DAYS)
            if not x or pd.Timestamp(x["exit"]) > end:
                continue
            opp = {}
            if basis == "COT only":
                # calendar windows pointing against COT that the rule ignored: up to 30 days but too small to stand alone,
                # and longer ones (31-63 days) the board does not scan
                for nm, lens in (("opp_short", None), ("opp_long", LONG_LENS)):
                    w2, st2 = cal.windows(t, min_move=0, lens=lens)
                    opp[nm] = bool(st2 == "driver" and ("BULLISH" if w2[0]["side"] == "BUY" else "BEARISH") != v)
                    if opp[nm]:
                        opp[nm + "_move"] = round(abs(w2[0]["avg"]) / 100 / cal.day_vol(t), 2)
            rows.append({"m": k, "t": str(t.date()), "v": v, "basis": basis, "sector": SECTOR(k),
                         "speed": spd if basis.startswith("COT") or basis == "Calendar over COT" else None, **opp, **x})
            busy = pd.Timestamp(x["exit"])
        print(k, sum(r["m"] == k for r in rows), flush=True)
    out = {"first": min(r["t"] for r in rows), "last": max(r["exit"] for r in rows),
           "all": summary([dict(r, a="all") for r in rows], "a")["all"],
           "by_basis": summary(rows, "basis"),
           "by_cell": summary([dict(r, c=r["basis"] + " | " + r["sector"]) for r in rows], "c"),
           "by_sector": summary(rows, "sector"),
           "by_basis_speed": summary([dict(r, bs=r["basis"] + " | " + r["speed"]) for r in rows if r["speed"]], "bs"),
           "config": {"seas_lb": os.environ.get("SEAS_LB", "15"), "skip_slow": SKIP_SLOW, "solo_min_move": SS.SOLO_MIN_MOVE, "gates": GATES}}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump({**out, "trades": rows}, open(os.path.join(HERE, "..", "data", "research", OUT), "w"), indent=1)
    for key in ("first", "last", "all", "by_basis", "by_sector"):
        print(key, json.dumps(out[key]))
    for c, v in sorted(out["by_cell"].items()):
        print(f"  {c:45s} n {v['n']:4d} win {v['win']:5.1f} avg {v['avg']:+6.2f} t {v['t']}")
