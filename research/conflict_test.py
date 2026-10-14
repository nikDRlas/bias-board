#!/usr/bin/env python3
"""When the seasonal window and COT disagree, which one was right?

Walk-forward over every Saturday since the seasonal engine has 15 prior years of data, running the
board's own rules as of that day (no later data):
  seasonal driver = the board's window scan (true seasonality, 15 prior years, >=12/15, 5-90 days)
  COT read        = lit lookbacks (>=2 of 5 per group), retail faded, commercials followed,
                    from the latest report RELEASED by that Saturday
Trades are sequential per market (one at a time, the next can only start after the last one exits),
so overlapping weeks of the same window are not counted twice.

A) Seasonal trades: entry at the first close on/after max(Saturday, window start), exit at window end.
   Split by what COT said at entry: agree / against / neutral / groups disagree.
B) COT trades: entry at the first close after the Saturday, held 8 weeks.
   Split by what the seasonal driver said at entry.
Output: data/research/conflict.json
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                     # noqa: E402

STARTS = np.arange(-14, 57)
LENS = np.arange(5, 91)
GATE, NY = 12, 15
COT_HOLD = 8


class Seas:
    def __init__(self, p):
        self.p = p
        self.dv = p.index.values.astype("datetime64[D]")
        lr = np.log(p).diff().fillna(0.0)
        self.cum = lr.cumsum().to_numpy()
        self.drift = lr.rolling(C.DRIFT_N).mean().shift(1).to_numpy()
        self.n = len(p)

    def driver(self, t):
        """the board's driver window as of day t, or None / 'cancel'"""
        starts = pd.DatetimeIndex(t + pd.to_timedelta(STARTS, "D"))
        up = np.zeros((len(STARTS), len(LENS)))
        mean = np.zeros_like(up)
        sq = np.zeros_like(up)
        for k in range(1, NY + 1):
            s = (starts - pd.DateOffset(years=k)).values.astype("datetime64[D]")
            a = np.searchsorted(self.dv, s)
            b = np.searchsorted(self.dv, s[:, None] + LENS[None, :].astype("timedelta64[D]"))
            if a.min() < C.DRIFT_N + 1 or b.max() >= self.n:
                return None
            d = self.drift[a]
            if not np.isfinite(d).all():
                return None
            res = (self.cum[b] - self.cum[a][:, None]) - d[:, None] * (b - a[:, None])
            up += res > 0
            mean += res
            sq += res ** 2
        wins = np.maximum(up, NY - up)
        mu = mean / NY
        sd = np.sqrt(np.maximum(sq / NY - mu ** 2, 1e-18) * NY / (NY - 1))
        tt = np.abs(mu) / sd * np.sqrt(NY)
        end = starts.values[:, None] + LENS[None, :].astype("timedelta64[D]")
        ok = (wins >= GATE) & (end > np.datetime64(t + pd.Timedelta(days=3)))
        if not ok.any():
            return None
        ii, jj = np.nonzero(ok)
        cand = sorted(({"side": "BUY" if up[i, j] >= 8 else "SELL", "wins": int(wins[i, j]), "t": float(tt[i, j]),
                        "start": starts[i], "end": starts[i] + pd.Timedelta(days=int(LENS[j])), "len": int(LENS[j])}
                       for i, j in zip(ii, jj)), key=lambda w: (-w["wins"], -w["t"]))
        near = [w for w in cand if w["start"] <= t] or [w for w in cand if w["start"] <= t + pd.Timedelta(days=14)]
        picks = near[:1]
        for w in cand:                                   # same greedy pick as the board
            clash = False
            for q in picks:
                ov = (min(w["end"], q["end"]) - max(w["start"], q["start"])).days
                if ov > 0 and (q["side"] == w["side"] or ov > 0.5 * min(w["len"], q["len"])):
                    clash = True
            if not clash:
                picks.append(w)
            if len(picks) == 4:
                break
        if not near:
            return None
        d = picks[0]
        if any(w["side"] != d["side"] and w["wins"] >= d["wins"] - 1 and abs((w["start"] - d["start"]).days) <= 14
               for w in picks[1:]):
            return "cancel"
        return d


Cot = C.CotReader


def ret(p, d0, d1, side):
    i = p.index.searchsorted(d0)
    j = p.index.searchsorted(d1)
    if j >= len(p) or j <= i:
        return None
    r = p.iloc[j] / p.iloc[i] - 1
    vol = np.log(p).diff().iloc[max(0, i - 60):i].std() * np.sqrt(j - i)      # scale for pooling markets
    s = 1 if side in ("BUY", "BULLISH") else -1
    return {"r": float(100 * s * r), "z": float(s * np.log(1 + r) / vol), "entry": str(p.index[i].date()),
            "exit": str(p.index[j].date())}


def rel(a, b):
    if a in ("NEUTRAL", "MIXED") or b is None:
        return a.lower() if a in ("NEUTRAL", "MIXED") else "none"
    return "agree" if a == b else "against"


def summary(rows, key):
    out = {}
    for cat in sorted({r[key] for r in rows}):
        rr = [r for r in rows if r[key] == cat]
        z = np.array([r["z"] for r in rr])
        out[cat] = {"n": len(rr), "win": round(100 * float(np.mean([r["r"] > 0 for r in rr])), 1),
                    "avg": round(float(np.mean([r["r"] for r in rr])), 2),
                    "z": round(float(z.mean()), 3), "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2) if len(z) > 2 else None}
    return out


if __name__ == "__main__":
    end = C.TODAY - pd.Timedelta(days=1)
    sats = pd.date_range("2016-01-02", end, freq="W-SAT")
    A, B = [], []
    for k in C.M:
        p = C.load_px(k)
        S, Q = Seas(p), Cot(k)
        busy_s = busy_c = pd.Timestamp("1900-01-01")
        for t in sats:
            if t <= busy_s and t <= busy_c:
                continue
            d = S.driver(t)
            sd = None if d in (None, "cancel") else ("BULLISH" if d["side"] == "BUY" else "BEARISH")
            cr = Q.read(t)
            if d not in (None, "cancel") and t > busy_s:
                x = ret(p, max(t, d["start"]), d["end"], d["side"])
                if x and pd.Timestamp(x["exit"]) <= end:
                    A.append({"m": k, "t": str(t.date()), "side": d["side"], "wins": d["wins"], "len": d["len"],
                              "start": str(d["start"].date()), "end": str(d["end"].date()), "cot": cr,
                              "rel": rel(cr, sd), **x})
                    busy_s = pd.Timestamp(x["exit"])
            if cr in ("BULLISH", "BEARISH") and t > busy_c:
                x = ret(p, t + pd.Timedelta(days=1), t + pd.Timedelta(weeks=COT_HOLD), cr)
                if x and pd.Timestamp(x["exit"]) <= end:
                    B.append({"m": k, "t": str(t.date()), "cot": cr, "groups": Q.last_groups, "seas": sd or ("cancel" if d == "cancel" else "none"),
                              "rel": "none" if sd is None else ("agree" if sd == cr else "against"), **x})
                    busy_c = pd.Timestamp(x["exit"])
        print(k, "seasonal trades", sum(r["m"] == k for r in A), "cot trades", sum(r["m"] == k for r in B), flush=True)
    res = {"built": str(C.TODAY.date()), "first": min(r["t"] for r in A), "last": max(r["exit"] for r in A),
           "seasonal": {"all": summary([dict(r, all="all") for r in A], "all")["all"], "by_cot": summary(A, "rel")},
           "cot": {"all": summary([dict(r, all="all") for r in B], "all")["all"], "by_seasonal": summary(B, "rel"),
                   "by_groups": summary(B, "groups"),
                   "by_sector": summary([dict(r, sec={"FX": "FX", "Indices": "Indices"}.get(C.M[r["m"]][3], "Commodities")) for r in B], "sec"),
                   "by_sector_seasonal": summary([dict(r, ss={"FX": "FX", "Indices": "Indices"}.get(C.M[r["m"]][3], "Commodities") + " · " + r["rel"]) for r in B], "ss")},
           "seasonal_by_sector": summary([dict(r, sec={"FX": "FX", "Indices": "Indices"}.get(C.M[r["m"]][3], "Commodities")) for r in A], "sec"),
           "per_market": {k: summary([r for r in A if r["m"] == k], "rel") for k in C.M},
           "trades_seasonal": A, "trades_cot": B}
    os.makedirs(os.path.join(HERE, "..", "data", "research"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "conflict.json"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("first", "last", "seasonal", "cot")}, indent=1))
