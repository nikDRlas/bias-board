#!/usr/bin/env python3
"""COT on the 21 currency crosses, built from the two legs with the board's current rule.

Each leg (EUR 6E, GBP 6B, JPY 6J, CHF 6S, AUD 6A, CAD 6C, NZD 6N; futures direction vs USD) is read with the board's
COT reader (commercials at an extreme with retail or funds at the opposite extreme); a leg the commercials crept into
slowly counts as no side. Cross BASE/QUOTE: base bullish & quote bearish = bullish (both legs); one leg with a side and
the other neutral = that leg decides (one leg); both legs the same way = no side.
One position per cross at a time, 8 weeks from the first close after the Friday release, since 2003.
Prices: LSE daily spot crosses. Output: data/research/cross_cot.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
sys.path.insert(0, HERE)
import core as C                                       # noqa: E402
from verdict_test import speed_series, speed_of       # noqa: E402

PX = os.environ.get("CROSS_PX", "/Users/Niklas/supply_demand_intraday/data_cache/lse_daily")
LEG = {"EUR": "6E", "GBP": "6B", "JPY": "6J", "CHF": "6S", "AUD": "6A", "CAD": "6C", "NZD": "6N"}
CROSSES = ["EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD", "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD",
           "GBPNZD", "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD", "CADJPY", "CADCHF", "NZDJPY", "NZDCHF", "NZDCAD", "CHFJPY"]


def leg_reads():
    out = {}
    for cur, k in LEG.items():
        rd, sp = C.CotReader(k), speed_series(k)
        rows = []
        for i in range(len(rd.dates)):
            v = rd.read_at(i)
            if v in ("BULLISH", "BEARISH") and speed_of(sp, i, v) == "slow":
                v = "NEUTRAL"
            rows.append(v if v in ("BULLISH", "BEARISH") else None)
        out[cur] = pd.Series(rows, index=rd.dates)
    return out


def cross_read(rb, rq):
    vb = {"BULLISH": 1, "BEARISH": -1}.get(rb, 0)
    vq = {"BULLISH": 1, "BEARISH": -1}.get(rq, 0)
    if vb and vq and vb == vq:
        return None, 0
    v = vb - vq
    return ("BULLISH" if v > 0 else "BEARISH" if v < 0 else None), (2 if vb and vq else 1 if v else 0)


def agg(rows):
    if len(rows) < 3:
        return None
    r, z = np.array([x["r"] for x in rows]), np.array([x["z"] for x in rows])
    z = z[np.isfinite(z)]
    return {"n": len(rows), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)}


if __name__ == "__main__":
    L = leg_reads()
    dates = L["EUR"].index
    rows = []
    for pair in CROSSES:
        p = pd.read_csv(f"{PX}/{pair}.csv", parse_dates=["ts"]).set_index("ts").close
        p = p[p.index.dayofweek < 5]
        lp = np.log(p)
        b_, q_ = L[pair[:3]].reindex(dates), L[pair[3:]].reindex(dates)
        busy = pd.Timestamp("1900-01-01")
        for d in dates:
            v, legs = cross_read(b_[d], q_[d])
            if not v:
                continue
            rel = d + pd.Timedelta(days=3)
            if rel < p.index[0] or rel <= busy:
                continue
            a, b = p.index.searchsorted(rel), p.index.searchsorted(rel + pd.Timedelta(weeks=8))
            if b >= len(p) or a < 61:
                continue
            sg = 1 if v == "BULLISH" else -1
            vol = lp.diff().iloc[a - 60:a].std() * np.sqrt(b - a)
            rows.append({"m": pair, "d": str(d.date()), "legs": legs, "r": 100 * sg * float(p.iloc[b] / p.iloc[a] - 1),
                         "z": float(sg * (lp.iloc[b] - lp.iloc[a]) / vol)})
            busy = p.index[b]
    res = {"all": agg(rows), "by_legs": {str(g): agg([r for r in rows if r["legs"] == g]) for g in (1, 2)},
           "by_period": {per: {str(g): agg([r for r in rows if r["legs"] == g and (r["d"] >= "2016") == (per == "2016-26")]) for g in (1, 2)}
                         for per in ("2003-15", "2016-26")},
           "by_cross": {pair: {str(g): agg([r for r in rows if r["m"] == pair and r["legs"] == g]) for g in (1, 2)} for pair in CROSSES}}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump({**res, "trades": rows}, open(os.path.join(HERE, "..", "data", "research", "cross_cot.json"), "w"), indent=1)
    print("all", res["all"]); print("by legs", res["by_legs"]); print("by period", json.dumps(res["by_period"]))
    for pair, v in res["by_cross"].items():
        print(f"  {pair} both {v['2']} | one {v['1']}")
