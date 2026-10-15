#!/usr/bin/env python3
"""Self-cancelling calendars: stand aside, or trade the two windows in sequence?

Walk-forward every Saturday since 2019 with the board's window scan. When the calendar cancels itself out (an opposite
window with a similar record starts within 10 trading days of the leading one), instead of standing aside:
  part 1  trade the leading window from max(Saturday, its start) until the opposite window starts (or its own end)
  part 2  then trade the opposite window from its start to its end
One position per market at a time. For comparison: ordinary (non-cancelling) leading windows over the same period.
Output: data/research/cancel.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402
from conflict_test import ret, summary                 # noqa: E402

if __name__ == "__main__":
    end = C.TODAY - pd.Timedelta(days=1)
    rows = []
    for k in C.M:
        p = C.load_px(k)
        cal = SS.Calendar(p)
        busy = pd.Timestamp("1900-01-01")
        for t in pd.date_range("2019-01-05", end, freq="W-SAT"):
            if t <= busy:
                continue
            ws, status = cal.windows(t)
            if status == "driver":
                d = ws[0]
                x = ret(p, max(t, pd.Timestamp(d["start"])), pd.Timestamp(d["end"]), d["side"])
                if x and pd.Timestamp(x["exit"]) <= end:
                    rows.append({"m": k, "t": str(t.date()), "kind": "ordinary window", **x})
                    busy = pd.Timestamp(x["exit"])
                continue
            if status != "cancel":
                continue
            d = ws[0]
            opp = [w for w in ws[1:] if w["side"] != d["side"] and abs(w["s"] - d["s"]) <= SS.OPEN_AHEAD
                   and w["share"] >= d["share"] - 0.07]
            if not opp:
                continue
            o = opp[0]
            first_end = min(pd.Timestamp(d["end"]), pd.Timestamp(o["start"]))
            last_exit = None
            x1 = ret(p, max(t, pd.Timestamp(d["start"])), first_end, d["side"]) if first_end > max(t, pd.Timestamp(d["start"])) else None
            if x1 and pd.Timestamp(x1["exit"]) <= end:
                rows.append({"m": k, "t": str(t.date()), "kind": "part 1: leading window until the turn", **x1})
                last_exit = pd.Timestamp(x1["exit"])
            x2 = ret(p, max(t, pd.Timestamp(o["start"])), pd.Timestamp(o["end"]), o["side"])
            if x2 and pd.Timestamp(x2["exit"]) <= end:
                rows.append({"m": k, "t": str(t.date()), "kind": "part 2: opposite window after the turn", **x2})
                last_exit = pd.Timestamp(x2["exit"])
            if last_exit is not None:
                busy = last_exit
        print(k, flush=True)
    res = {"by_kind": summary(rows, "kind"),
           "by_kind_half": summary([dict(r, kh=r["kind"] + " | " + ("2019-22" if r["t"] < "2023" else "2023-26")) for r in rows], "kh")}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump({**res, "trades": rows}, open(os.path.join(HERE, "..", "data", "research", "cancel.json"), "w"), indent=1)
    for k2, v in res.items():
        print(k2)
        for g, o in v.items(): print(f"   {g:50s} n {o['n']:4d} won {o['win']:5.1f}% avg {o['avg']:+.2f}% t {o['t']}")
