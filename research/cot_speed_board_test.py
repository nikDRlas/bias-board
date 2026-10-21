#!/usr/bin/env python3
"""The board with COT signals the commercials crept into slowly skipped (current) vs kept: the walk-forward replay
(research/verdict_test.py) run both ways, every Saturday 2019-26, one position per market.
Run: SKIP_SLOW=1 OUT=speed_skip.json python3 research/verdict_test.py; SKIP_SLOW=0 OUT=speed_keep.json python3 research/verdict_test.py;
then this script. Output: data/research/cot_speed_board.json"""
import json, os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "data", "research")


def agg(g):
    per = g.groupby(g.t.dt.to_period("M")).r.mean()
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "total": round(float(g.r.sum()), 0), "t": round(float(per.mean() / per.std(ddof=1) * np.sqrt(len(per))), 1),
            "2019-22": round(float(g[g.t < "2023"].r.mean()), 2), "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2)}


if __name__ == "__main__":
    out = {}
    for lab, f in (("skip", "speed_skip.json"), ("keep", "speed_keep.json")):
        v = pd.DataFrame(json.load(open(os.path.join(D, f)))["trades"])
        v["t"] = pd.to_datetime(v.t)
        out[lab] = {"board": agg(v)}
        if lab == "keep":
            out[lab]["slow_verdicts"] = agg(v[v.speed == "slow"])
    json.dump(out, open(os.path.join(D, "cot_speed_board.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
