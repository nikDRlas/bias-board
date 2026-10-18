#!/usr/bin/env python3
"""Running calendar windows: does what the window usually still does from today to its end predict the rest?

Walk-forward 2019-26, every Saturday on which the board's driver window was already running (only data known then).
  rest_usual = the window's average move from today's trading day to its end over its 15 past years, in its direction
  share_done = this year's move so far / the window's usual whole move
Outcome = from the next close to the window end, in the window's direction. One observation per market, window and
year (the first Saturday it falls in a group). Output: data/research/window_remaining.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402


def st(g):
    if len(g) < 5:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "t": round(float(g.r.mean() / g.r.std(ddof=1) * np.sqrt(len(g))), 2)}


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p = C.load_px(k)
        px = p.to_numpy(float)
        cal = SS.Calendar(p)
        for t in pd.date_range("2019-01-05", C.TODAY - pd.Timedelta(days=1), freq="W-SAT"):
            ws, status = cal.windows(t)
            if status != "driver":
                continue
            d = ws[0]
            r = cal.remaining(t, d)
            if not r or not r["started"]:
                continue
            sg = 1 if d["side"] == "BUY" else -1
            c, e = p.index.searchsorted(t), p.index.searchsorted(pd.Timestamp(d["end"]))
            if e >= len(p) or e <= c or p.index[e] > C.TODAY:
                continue
            rest_usual = sg * r["avg"]
            done = (sg * r["so_far"]) / (sg * d["avg"]) if r["so_far"] is not None and sg * d["avg"] > 0 else None
            rows.append({"m": k, "d": str(t.date()), "start": str(d["start"]), "rest_usual": rest_usual,
                         "done": done, "r": 100 * sg * (px[e] / px[c] - 1)})
        print(k, flush=True)
    df = pd.DataFrame(rows)
    df["g_rest"] = np.where(df.rest_usual <= 0, "nothing left (usual rest <= 0)", "something left (usual rest > 0)")
    df["g_done"] = pd.cut(df.done, [-99, 0, 0.5, 0.8, 1.0, 99], labels=["against so far", "0-50%", "50-80%", "80-100%", "100%+"])
    one = df.sort_values("d").groupby(["m", "start", "g_rest"]).head(1)
    res = {"by_rest": {g: {"all": st(x), "2019-22": st(x[x.d < "2023"]), "2023-26": st(x[x.d >= "2023"])} for g, x in one.groupby("g_rest")},
           "by_done": {str(g): st(x) for g, x in df.sort_values("d").groupby(["m", "start", "g_done"], observed=True).head(1).groupby("g_done", observed=True)}}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "window_remaining.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
