#!/usr/bin/env python3
"""BTC and ETH: the board's COT rule and a seasonal window scan on the short crypto histories.

COT: CFTC legacy futures-only, CME Bitcoin (from Apr 2018) and CME Ether (from Apr 2021). The board's read: commercials
at an extreme on >= 2 of 5 lookbacks (6 mo, 1, 2, 3 yr, multi-yr = 5 yr; a lookback counts once it has enough history),
retail or funds at the opposite extreme, funds not on the commercials' side. One trade per lit run, entry at the first
close after the Friday release, held while lit + 1 week, and fixed 4 / 8 weeks; vs the coin's own drift (prior years).
Seasonality: windows of 5-30 trading days, at least 80% of the available past years (needs >= 5 years), walk-forward
every Saturday from 2023; outcome to the window end. Prices: LSE spot daily (weekday closes).
Args: price folder, CFTC folder. Output: data/research/crypto.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

COINS = {"BTC": "133741", "ETH": "146021"}


def prices(folder, k):
    raw = json.load(open(os.path.join(folder, k + ".json")))
    p = pd.Series([x[1] for x in raw], index=pd.to_datetime([x[0] for x in raw])).astype(float).groupby(level=0).last()
    return p[p.index.dayofweek < 5]


def cot(folder, code):
    d = pd.DataFrame(json.load(open(os.path.join(folder, f"cftc_{code}.json"))))
    d["date"] = pd.to_datetime(d.report_date_as_yyyy_mm_dd)
    d = d.set_index("date").sort_index()
    for c in d.columns:
        if c not in ("market_and_exchange_names", "report_date_as_yyyy_mm_dd"):
            d[c] = d[c].astype(float)
    x = pd.DataFrame({"comm": d.comm_positions_long_all - d.comm_positions_short_all,
                      "fund": d.noncomm_positions_long_all - d.noncomm_positions_short_all})
    x["retail"] = -(x.comm + x.fund)
    return x


def side(P, g, i):
    s = [("hi" if v >= C.HI else "lo") for v in (P[g][lb][i] for lb in P[g]) if np.isfinite(v) and (v >= C.HI or v <= C.LO)]
    return s[0] if len(s) >= 2 and len(set(s)) == 1 else None


def st(r, ex):
    r, ex = np.array(r), np.array(ex)
    if len(r) < 5:
        return {"n": len(r)}
    return {"n": len(r), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "vs_drift": round(float(ex.mean()), 2), "t": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(ex))), 2)}


if __name__ == "__main__":
    pdir, cdir = sys.argv[1], sys.argv[2]
    res = {}
    for k, code in COINS.items():
        p = prices(pdir, k)
        lc = np.log(p.to_numpy())
        x = cot(cdir, code)
        P = {g: {lb: C.pctile(x[g], L).to_numpy() for lb, L in C.LB.items()} for g in ("comm", "retail", "fund")}
        reads = []
        for i in range(len(x)):
            c = side(P, "comm", i)
            v = None
            if c and side(P, "fund", i) != c:
                opp = "lo" if c == "hi" else "hi"
                if side(P, "retail", i) == opp or side(P, "fund", i) == opp:
                    v = "BULLISH" if c == "hi" else "BEARISH"
            reads.append(v)
        out = {h: ([], []) for h in ("lit+1w", "4w", "8w")}
        cases = []
        for i in range(len(reads)):
            v = reads[i]
            if not v or (i and reads[i - 1] == v):
                continue
            j = i
            while j + 1 < len(reads) and reads[j + 1] == v:
                j += 1
            rel = x.index[i] + pd.Timedelta(days=3)
            a = p.index.searchsorted(rel)
            if a >= len(p) or a < 250:
                continue
            sg = 1 if v == "BULLISH" else -1
            for h, end in (("lit+1w", x.index[j] + pd.Timedelta(days=10) if j + 1 < len(reads) else None),
                           ("4w", rel + pd.Timedelta(weeks=4)), ("8w", rel + pd.Timedelta(weeks=8))):
                if end is None:
                    continue
                b = p.index.searchsorted(end)
                if b >= len(p) or b <= a:
                    continue
                L, lo = b - a, max(0, a - 1250)
                dr = float((lc[lo + L:a] - lc[lo:a - L]).mean())
                r = 100 * (np.exp(sg * (lc[b] - lc[a])) - 1)
                out[h][0].append(r)
                out[h][1].append(r - 100 * (np.exp(sg * dr) - 1))
                if h == "lit+1w":
                    cases.append({"report": str(x.index[i].date()), "side": v, "r": round(r, 2)})
        # seasonality: walk-forward window scan on the available years
        years = sorted(set(p.index.year))
        first = {y: int(np.nonzero(p.index.year == y)[0][0]) for y in years}
        sea_r, sea_ex = [], []
        LEN = np.arange(5, 31)
        busy = pd.Timestamp("1900-01-01")
        for t in pd.date_range("2023-01-07", p.index[-1] - pd.Timedelta(days=45), freq="W-SAT"):
            if t <= busy:
                continue
            Y = t.year
            ys = [y for y in years if y < Y and y >= years[0] + 1][-10:]
            if len(ys) < 5:
                continue
            now = int(p.index.searchsorted(t)) - first[Y]
            best = None
            for s0 in range(max(0, now - 10), now + 11):
                for L in LEN:
                    if s0 + L <= now + 2:
                        continue
                    rr = []
                    for y in ys:
                        a0 = first[y] + s0
                        if a0 + L >= len(p) or (y + 1 in first and a0 + L >= first[y + 1] + 10):
                            rr = None
                            break
                        rr.append(lc[a0 + L] - lc[a0])
                    if not rr:
                        continue
                    rr = np.array(rr)
                    w = max((rr > 0).sum(), (rr < 0).sum())
                    if w / len(ys) >= 0.8 and (best is None or (w, -abs(rr.mean())) > (best[0], -abs(best[3]))):
                        best = (w, s0, L, rr.mean())
            if not best:
                continue
            w, s0, L, mu = best
            sg = 1 if mu > 0 else -1
            a = first[Y] + max(s0, now)
            b = first[Y] + s0 + L
            if b >= len(p) or b <= a:
                continue
            Ln, lo = b - a, max(0, a - 1250)
            dr = float((lc[lo + Ln:a] - lc[lo:a - Ln]).mean())
            r = 100 * (np.exp(sg * (lc[b] - lc[a])) - 1)
            sea_r.append(r)
            sea_ex.append(r - 100 * (np.exp(sg * dr) - 1))
            busy = p.index[b]
        res[k] = {"cot": {h: st(*v) for h, v in out.items()}, "cot_cases": cases, "seasonal_2023_26": st(sea_r, sea_ex),
                  "cot_first": str(x.index[0].date()), "price_first": str(p.index[0].date())}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "crypto.json"), "w"), indent=1)
    for k, v in res.items():
        print(f"\n== {k} (COT from {v['cot_first']}, prices from {v['price_first']})")
        for h, o in v["cot"].items():
            print(f"   COT {h:7s}", o)
        print("   seasonal windows 2023-26 (5-30 days, >= 80% of the available years):", v["seasonal_2023_26"])
        print("   COT cases:", [(c["report"], c["side"][:4], c["r"]) for c in v["cot_cases"]])
