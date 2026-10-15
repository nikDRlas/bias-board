#!/usr/bin/env python3
"""Walk-forward test of the board's FINAL verdict, the basis of the confidence dots.

Every Saturday since 2019 (the first year the 15-year seasonal scan has data for), for every market, the board's
verdict is rebuilt with only what was known that day: the COT report released by then, the seasonal windows from
the 15 years before, and the shared verdict rule (bias/verdict.py). One position per market at a time.
A COT-led verdict is held 8 weeks; a calendar-led verdict to the end of its window. Entry at the next close.

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

LB_CFG = {"15": [(15, 12)], "15,10": [(15, 12), (10, 8)]}[os.environ.get("SEAS_LB", "15")]
SKIP_SLOW = os.environ.get("SKIP_SLOW") == "1"
OUT = os.environ.get("OUT", "verdict.json")
SPEED = json.load(open(os.path.join(HERE, "..", "data", "research", "cot_speed.json")))["move4w"]["cutoffs"]


def speed_series(k):
    x = C.load_cot(k)
    d4 = x["comm"].diff(4)
    return (d4 / d4.rolling(156, min_periods=52).std().shift(1)).to_numpy()


def speed_of(sp, i, side):
    v = sp[i] * (1 if side == "BULLISH" else -1) if 0 <= i < len(sp) and np.isfinite(sp[i]) else np.nan
    if not np.isfinite(v):
        return None
    return "fast" if v > SPEED[1] else "slow" if v <= SPEED[0] else "medium"


if __name__ == "__main__":
    SS.LOOKBACKS = LB_CFG
    end = C.TODAY - pd.Timedelta(days=1)
    rows = []
    for k in C.M:
        p = C.load_px(k)
        cal, rd = SS.Calendar(p), C.CotReader(k)
        sp = speed_series(k)
        busy = pd.Timestamp("1900-01-01")
        for t in pd.date_range("2019-01-05", end, freq="W-SAT"):
            if t <= busy:
                continue
            ws, status = cal.windows(t)
            seas = ("BULLISH" if ws[0]["side"] == "BUY" else "BEARISH") if status == "driver" else None
            cot = rd.read(t)
            i_rep = rd.dates.searchsorted(t - pd.Timedelta(days=3), "right") - 1
            spd = speed_of(sp, i_rep, cot) if cot in VD.SIDES else None
            if SKIP_SLOW and spd == "slow":
                cot = "NEUTRAL"
            ag = None
            if seas and cot in VD.SIDES and cot != seas:
                ag = cal.past(t.year, ws[0], rd)["summary"]["against"]
            v, basis = VD.decide(cot, seas, ag)
            if v not in VD.SIDES:
                continue
            if VD.horizon(basis) == "window":
                x = ret(p, max(t, pd.Timestamp(ws[0]["start"])), pd.Timestamp(ws[0]["end"]), v)
            else:
                x = ret(p, t + pd.Timedelta(days=1), t + pd.Timedelta(weeks=8), v)
            if not x or pd.Timestamp(x["exit"]) > end:
                continue
            rows.append({"m": k, "t": str(t.date()), "v": v, "basis": basis, "sector": SECTOR(k),
                         "speed": spd if basis.startswith("COT") or basis == "Calendar over COT" else None, **x})
            busy = pd.Timestamp(x["exit"])
        print(k, sum(r["m"] == k for r in rows), flush=True)
    out = {"first": min(r["t"] for r in rows), "last": max(r["exit"] for r in rows),
           "all": summary([dict(r, a="all") for r in rows], "a")["all"],
           "by_basis": summary(rows, "basis"),
           "by_cell": summary([dict(r, c=r["basis"] + " | " + r["sector"]) for r in rows], "c"),
           "by_sector": summary(rows, "sector"),
           "by_basis_speed": summary([dict(r, bs=r["basis"] + " | " + r["speed"]) for r in rows if r["speed"]], "bs"),
           "config": {"seas_lb": os.environ.get("SEAS_LB", "15"), "skip_slow": SKIP_SLOW}}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump({**out, "trades": rows}, open(os.path.join(HERE, "..", "data", "research", OUT), "w"), indent=1)
    for key in ("first", "last", "all", "by_basis", "by_sector"):
        print(key, json.dumps(out[key]))
    for c, v in sorted(out["by_cell"].items()):
        print(f"  {c:45s} n {v['n']:4d} win {v['win']:5.1f} avg {v['avg']:+6.2f} t {v['t']}")
