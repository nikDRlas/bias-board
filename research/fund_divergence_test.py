#!/usr/bin/env python3
"""Bernd's 'fund divergence': price and the large speculators (non-commercial net) disagreeing at their lows.

  bullish  price makes a LOWER low while funds make a HIGHER low   ("selling exhaustion, potential bottom")
  bearish  price makes a HIGHER low while funds make a LOWER low   ("buying not backed, potential top")
Only lows are used, as on his pages. Weekly points on the COT report Tuesdays: price = lowest daily close of the week
ending that Tuesday (our spot prices), funds = non-commercial net. Two versions, fixed before looking at results:
  A confirmed  a low is a week lower than the week before and the week after (known one week later); the newest low is
               compared with the previous low, at most 12 weeks earlier; signal on the release that confirms it
  B live       the newest week counts as a low when it is lower than the week before (as on his pages, where the
               latest report is the second low); compared with the previous confirmed low within 12 weeks
Entry at the first close after the release; results after 4 and 8 weeks in the signal's direction, against the
market's own drift (same length, same direction, prior 10 years). One signal per market and direction per 4 weeks.
His claim (pooled, last ten years): bullish 72% won over 4 weeks (+4.4%), 64% over 8; bearish 36% / 39%.
Output: data/research/fund_divergence.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402

GAP = 12


def lows_confirmed(v):
    """indices j that are a low: lower than j-1 and j+1 (known at j+1)"""
    return [j for j in range(1, len(v) - 1) if np.isfinite(v[j - 1:j + 2]).all() and v[j] < v[j - 1] and v[j] < v[j + 1]]


def signals(px_w, fu, mode):
    """(report index of the signal, side) for one market"""
    out = []
    pl, fl = lows_confirmed(px_w), lows_confirmed(fu)
    n = len(px_w)
    for i in range(2, n):
        # lows known at report i
        if mode == "A":
            pk = [j for j in pl if j + 1 <= i]
            fk = [j for j in fl if j + 1 <= i]
            if len(pk) < 2 or len(fk) < 2:
                continue
            p2, p1, f2, f1 = pk[-1], pk[-2], fk[-1], fk[-2]
            if max(p2, f2) + 1 != i:                    # act only on the release that confirms the newer low
                continue
        else:
            if not (px_w[i] < px_w[i - 1] or fu[i] < fu[i - 1]):
                continue
            pk = [j for j in pl if j + 1 <= i - 1]
            fk = [j for j in fl if j + 1 <= i - 1]
            if not pk or not fk:
                continue
            p2 = i if px_w[i] < px_w[i - 1] else pk[-1]
            f2 = i if fu[i] < fu[i - 1] else fk[-1]
            p1 = pk[-1] if p2 == i else (pk[-2] if len(pk) > 1 else None)
            f1 = fk[-1] if f2 == i else (fk[-2] if len(fk) > 1 else None)
            if p1 is None or f1 is None or (p2 != i and f2 != i):
                continue
        if p2 - p1 > GAP or f2 - f1 > GAP or p2 <= p1 or f2 <= f1:
            continue
        if px_w[p2] < px_w[p1] and fu[f2] > fu[f1]:
            out.append((i, "BULLISH"))
        elif px_w[p2] > px_w[p1] and fu[f2] < fu[f1]:
            out.append((i, "BEARISH"))
    return out


def st(g, h):
    r = g[f"r{h}"].dropna()
    ex = (g[f"r{h}"] - g[f"b{h}"]).dropna()
    if len(r) < 5:
        return None
    return {"n": len(r), "win": round(100 * float((r > 0).mean()), 1), "avg": round(float(r.mean()), 2),
            "t": round(float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))), 2),
            "vs_drift": round(float(ex.mean()), 2), "vs_drift_t": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(ex))), 2)}


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p, x = C.load_px(k), C.load_cot(k)
        lc = np.log(p.to_numpy(float))
        D = x.index
        px_w = np.array([p[(p.index > d - pd.Timedelta(days=7)) & (p.index <= d)].min() if ((p.index > d - pd.Timedelta(days=7)) & (p.index <= d)).any() else np.nan for d in D], float)
        fu = x["fund"].to_numpy(float)
        for mode in ("A", "B"):
            last = {}
            for i, side in signals(px_w, fu, mode):
                rel = D[i] + pd.Timedelta(days=3)
                if rel < p.index[0] or (side in last and (D[i] - last[side]).days < 28):
                    continue
                last[side] = D[i]
                a = p.index.searchsorted(rel)
                if a < 300 or a >= len(p):
                    continue
                sg = 1 if side == "BULLISH" else -1
                rec = {"mode": mode, "m": k, "sector": C.M[k][3], "d": str(D[i].date()), "side": side}
                for h in (4, 8):
                    b = p.index.searchsorted(rel + pd.Timedelta(weeks=h))
                    if b >= len(p):
                        rec[f"r{h}"] = rec[f"b{h}"] = None
                        continue
                    L = b - a
                    lo = max(0, a - 2520)
                    rec[f"r{h}"] = 100 * (np.exp(sg * (lc[b] - lc[a])) - 1)
                    rec[f"b{h}"] = float(100 * (np.exp(sg * (lc[lo + L:a] - lc[lo:a - L])) - 1).mean())
                rows.append(rec)
        print(k, flush=True)
    df = pd.DataFrame(rows).astype({"r4": float, "r8": float, "b4": float, "b8": float})
    res = {}
    for mode, g in df.groupby("mode"):
        res[mode] = {}
        for side, x in g.groupby("side"):
            res[mode][side] = {per: {f"{h}w": st(y, h) for h in (4, 8)} for per, y in
                               (("2003-26", x), ("last 10 years (2016-26)", x[x.d >= "2016"]), ("2003-15", x[x.d < "2016"]))}
            res[mode][side]["by_sector_8w"] = {s: st(y, 8) for s, y in x.groupby("sector")}
    json.dump({**res, "signals": rows}, open(os.path.join(HERE, "..", "data", "research", "fund_divergence.json"), "w"), indent=1, default=float)
    f = lambda o: f"{o['win']:5.1f}% avg {o['avg']:+.2f}% t {o['t']:+.2f} | vs drift {o['vs_drift']:+.2f}% t {o['vs_drift_t']:+.2f} n{o['n']}" if o else "-"
    for mode, v in res.items():
        for side, w in v.items():
            print(f"\n=== version {mode} · {side}")
            for per in ("2003-26", "last 10 years (2016-26)", "2003-15"):
                print(f"  {per:24s} 4w {f(w[per]['4w'])}\n  {'':24s} 8w {f(w[per]['8w'])}")
            print("  8w by sector:", {s: (o['win'], o['avg'], o['vs_drift'], o['n']) for s, o in w["by_sector_8w"].items() if o})
