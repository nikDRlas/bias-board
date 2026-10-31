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
KEEP_SLOW_IN = set(os.environ.get("KEEP_SLOW_IN", "").split(",")) - {""}   # sectors (core.M) where slow signals are kept anyway
OUT = os.environ.get("OUT", "verdict.json")
GATES = os.environ.get("GATES", "macro,done")
FX_COT = os.environ.get("FX_COT", "bernd")              # currency COT rule: min (board) / none / bernd (his evidence gate)          # the final 'nothing left' rules (bias/verdict.py final_read)
# research switches (2026-10-31, Bernd's commodity outlook): NONFX_COT = min (board: COT minimum record) / bernd (his
# evidence gate instead) / both (minimum AND his gate) outside currencies; RETAIL_SAME=drop = no side when retail sits
# at an extreme on the commercials' own side (his natural-gas case: crowd faded against commercials followed)
# TESTED 2026-10-31, all REJECTED (walk-forward 2019-26, data/research/bernd31_*.json; % per verdict, total %):
#   board          572 verdicts 61.2% +1.84% total +1052 (19-22 +510, 23-26 +542); metals & energy +3.20% total +426
#   bernd          648 59.0% +1.05% +679 (+291 / +388), metals & energy +0.62% (19-22 negative)
#   both           522 61.3% +1.62% +845 (+373 / +472), metals & energy +2.54% total +259
#   retail drop    543 61.3% +1.74% +945 (+431 / +514)
# and his "seasonal against COT -> stand aside" outside agriculture would drop 132 COT-only verdicts: 19-22 -0.86%
# (-53) but 23-26 +2.77% (+194) -> fails a half, the board keeps COT over a contrary calendar outside agriculture
NONFX_COT = os.environ.get("NONFX_COT", "min")
RETAIL_SAME = os.environ.get("RETAIL_SAME", "keep")
speed_series, speed_of = C.speed_series, C.speed_of
LONG_LENS = np.arange(31, 64)


if __name__ == "__main__":
    SS.LOOKBACKS = LB_CFG
    MACRO = {}
    BERND = {}
    if FX_COT == "bernd":
        from qualify_test import Market
        BERND = {k: Market(k) for k in C.M if C.M[k][3] == "FX" or NONFX_COT != "min"}
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
        skip_k = SKIP_SLOW and C.M[k][3] not in KEEP_SLOW_IN
        lit = C.lit_sides(rd, sp, skip_slow=skip_k)
        busy = pd.Timestamp("1900-01-01")
        for t in pd.date_range("2019-01-05", end, freq="W-SAT"):
            if t <= busy:
                continue
            cot = rd.read(t)
            i_rep = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
            spd = speed_of(sp, i_rep, cot) if cot in VD.SIDES else None
            if skip_k and spd == "slow" and not (C.SPEED_AT_START and 0 <= i_rep < len(lit) and lit[i_rep] == cot):
                cot = "NEUTRAL"                        # COT_SPEED_AT_START=1: a run judged fast/medium at its start stays
            held_q = None
            if cot not in VD.SIDES:                    # outside currencies a COT verdict is held at least 8 weeks
                hs, held_q = C.held_side(rd.dates, lit, i_rep, t, k)
                if hs:
                    cot = hs
            fx = C.M[k][3] == "FX"
            if cot in VD.SIDES and RETAIL_SAME == "drop" and 0 <= i_rep and rd.side("retail", i_rep) == ("hi" if cot == "BULLISH" else "lo"):
                cot = "NEUTRAL"
            if cot in VD.SIDES and fx and FX_COT == "bernd":
                if BERND[k].read(t, "gated") != cot:
                    cot = "NEUTRAL"
            elif cot in VD.SIDES and not fx and NONFX_COT != "min":
                if BERND[k].read(t, "gated") != cot or (NONFX_COT == "both" and not C.cot_big_enough(k, cot, t)):
                    cot = "NEUTRAL"
            elif cot in VD.SIDES and not (fx and FX_COT == "none") and not C.cot_big_enough(k, cot, t):
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
                q = held_q if held_q is not None else i_rep
                ex = C.cot_exit(rd.dates, lit, q, k=k) if 0 <= q and lit[q] == cot else None
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
           "config": {"seas_lb": os.environ.get("SEAS_LB", "15"), "skip_slow": SKIP_SLOW, "solo_min_move": SS.SOLO_MIN_MOVE, "gates": GATES, "fx_cot": FX_COT,
                      "nonfx_cot": NONFX_COT, "retail_same": RETAIL_SAME}}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump({**out, "trades": rows}, open(os.path.join(HERE, "..", "data", "research", OUT), "w"), indent=1)
    for key in ("first", "last", "all", "by_basis", "by_sector"):
        print(key, json.dumps(out[key]))
    for c, v in sorted(out["by_cell"].items()):
        print(f"  {c:45s} n {v['n']:4d} win {v['win']:5.1f} avg {v['avg']:+6.2f} t {v['t']}")
