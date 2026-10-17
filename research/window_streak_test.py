#!/usr/bin/env python3
"""Stable seasonal windows: does a window that already qualified in earlier years pay better than a new one?

Walk-forward 2021-26, every Saturday the board's driver window (only data known that day). For each earlier year Y-k
the same window (same direction, start within +-3 trading days, length within +-3) is re-counted over ITS 15 years
before Y-k; streak = how many years in a row (k = 1, 2, 3) it already reached 12 of 15. 2021 is the first test year that
can look back 3 full years (the first year with 15 years of prices before it is 2018).
One observation per market, window and year. Outcome from the next close (or window start) to the window end.
Also split by the minimum-move gate (usual move >= 3 normal days). Output: data/research/window_streak.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C                                       # noqa: E402
import seasonal as SS                                  # noqa: E402

SHIFT, MAXK, FIRST_TEST = 3, 3, 2021


def qualified(cal, Yk, s, L, side):
    """did a window like (s, L, side) reach 12 of 15 over the 15 years before Yk?"""
    ys = list(range(Yk - SS.NY, Yk))
    if not all(y in cal.first for y in ys):
        return None
    sg = 1 if side == "BUY" else -1
    best = 0
    for s2 in range(s - SHIFT, s + SHIFT + 1):
        for L2 in range(max(5, L - SHIFT), L + SHIFT + 1):
            w = 0
            for y in ys:
                a = cal.first[y][0] + s2
                if a < 0 or a + L2 >= cal.n:
                    w = -99
                    break
                w += sg * (cal.lc[a + L2] - cal.lc[a]) > 0
            best = max(best, w)
            if best >= SS.GATE:
                return True
    return False


def st(g):
    if len(g) < 5:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "t": round(float(g.z.mean() / g.z.std(ddof=1) * np.sqrt(len(g))), 2)}


if __name__ == "__main__":
    rows = []
    for k in C.M:
        p = C.load_px(k)
        lc = np.log(p.to_numpy(float))
        dl = np.diff(lc, prepend=lc[0])
        cal = SS.Calendar(p)
        seen = set()
        for t in pd.date_range(f"{FIRST_TEST}-01-02", C.TODAY - pd.Timedelta(days=1), freq="W-SAT"):
            ws, status = cal.windows(t)
            if status != "driver":
                continue
            d = ws[0]
            key = (t.year, d["s"], d["len"], d["side"])
            if key in seen:
                continue
            seen.add(key)
            streak = 0
            for kk in range(1, MAXK + 1):
                q = qualified(cal, t.year - kk, d["s"], d["len"], d["side"])
                if not q:
                    break
                streak += 1
            ti = p.index.searchsorted(t)
            sig = dl[max(1, ti - 252):ti].std()
            a = p.index.searchsorted(max(t, pd.Timestamp(d["start"])))
            b = p.index.searchsorted(pd.Timestamp(d["end"]))
            if b >= len(p) or b <= a or p.index[b] > C.TODAY:
                continue
            sg = 1 if d["side"] == "BUY" else -1
            r = sg * (lc[b] - lc[a])
            rows.append({"m": k, "d": str(t.date()), "streak": streak, "move_days": abs(d["avg"]) / 100 / sig,
                         "r": 100 * (np.exp(r) - 1), "z": float(r / (sig * np.sqrt(b - a)))})
        print(k, flush=True)
    df = pd.DataFrame(rows)
    lab = {0: "new (not qualified last year)", 1: "1 year in a row", 2: "2 years in a row", 3: "3+ years in a row"}
    res = {"by_streak": {}, "by_streak_min3": {}, "stable_vs_new": {}}
    for s_, g in df.groupby("streak"):
        res["by_streak"][lab[s_]] = {"all": st(g), "2021-23": st(g[g.d < "2024"]), "2024-26": st(g[g.d >= "2024"])}
        g3 = g[g.move_days >= 3]
        res["by_streak_min3"][lab[s_]] = st(g3)
    for nm, g in (("new (0)", df[df.streak == 0]), ("stable (>= 2)", df[df.streak >= 2]),
                  ("new, move >= 3 days", df[(df.streak == 0) & (df.move_days >= 3)]),
                  ("stable, move >= 3 days", df[(df.streak >= 2) & (df.move_days >= 3)])):
        res["stable_vs_new"][nm] = {"all": st(g), "2021-23": st(g[g.d < "2024"]), "2024-26": st(g[g.d >= "2024"])}
    res["share"] = {lab[s_]: round(100 * float((df.streak == s_).mean()), 1) for s_ in sorted(df.streak.unique())}
    json.dump({**res, "rows": rows}, open(os.path.join(HERE, "..", "data", "research", "window_streak.json"), "w"), indent=1)
    f = lambda o: f"{o['win']:4.1f}% {o['avg']:+.2f}% t {o['t']:+.2f} n{o['n']}" if o else "-"
    print("share of windows by streak:", res["share"])
    for nm, v in res["by_streak"].items():
        print(f"{nm:32s} all {f(v['all'])} | 21-23 {f(v['2021-23'])} | 24-26 {f(v['2024-26'])} | with move>=3d {f(res['by_streak_min3'][nm])}")
    for nm, v in res["stable_vs_new"].items():
        print(f"{nm:32s} all {f(v['all'])} | 21-23 {f(v['2021-23'])} | 24-26 {f(v['2024-26'])}")
