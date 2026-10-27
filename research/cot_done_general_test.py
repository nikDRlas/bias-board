"""Generalising the COT 'move done' (2026-10-27). Every COT setup since 2003 (one per setup, core.cot_setups, held as
the board holds: lit + 1 week, at least 8 weeks outside currencies), checked on each weekly release while it runs.
Three yardsticks for 'how much of the move is done', pooled across all 24 markets:
  current   so far / average winning end move of the market's earlier same-side setups (>= 5), the board's rule
  vol       so far in NORMAL WEEKS of the market (daily vol over the year before entry x sqrt 5): no market record needed
  unwind    how much of their extreme the commercials have given back since the signal: (net at signal - net now) /
            (net at signal - 3-year median net at signal); < 0 = still adding, 1 = back to normal
rest = move from that release's close to the setup's exit, in % and in normal weeks (pooled t). Output: data/research/cot_done_general.json"""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C  # noqa: E402

rows = []
for k in C.M:
    p, rd = C.load_px(k), C.CotReader(k)
    px = p.to_numpy(float); lc = np.log(px)
    comm = C.load_cot(k)["comm"]
    med = comm.rolling(156, min_periods=52).median()
    lit = rd.lit; D = rd.dates
    done = []
    for i, rel, ex, v in C.cot_setups(rd, k):
        if rel < p.index[0]:
            continue
        a, b = p.index.searchsorted(rel), p.index.searchsorted(ex)
        if b >= len(p) or b <= a or a < 260:
            continue
        sg = 1 if v == "BULLISH" else -1
        wk = np.diff(lc[a - 252:a]).std() * np.sqrt(5)
        n0, m0 = comm.iloc[i], med.iloc[i]
        ext = (n0 - m0) * sg
        j = i + 1
        while j < len(D):
            c = p.index.searchsorted(D[j] + pd.Timedelta(days=3))
            if c >= b:
                break
            prior = [x for x in done if x["side"] == v and x["exit"] <= D[j]]
            wins = [x["end"] for x in prior if x["end"] > 0]
            so = sg * (lc[c] - lc[a])
            rows.append({"m": k, "sector": C.M[k][3], "d": D[j], "so_pct": 100 * (np.exp(so) - 1), "so_wk": so / wk,
                         "cur": (100 * (np.exp(so) - 1)) / np.mean(wins) if len(prior) >= 5 and wins else np.nan,
                         "unwind": (n0 - comm.iloc[j]) * sg / ext if ext > 0 else np.nan,
                         "rest_pct": 100 * sg * (px[b] / px[c] - 1), "rest_wk": sg * (lc[b] - lc[c]) / wk})
            j += 1
        done.append({"side": v, "exit": p.index[b], "end": 100 * sg * (px[b] / px[a] - 1)})
    print(k, flush=True)
df = pd.DataFrame(rows)
df.to_csv(os.path.join(HERE, "..", "data", "research", "cot_done_general.csv"), index=False)


def st(g):
    if len(g) < 20:
        return None
    t = g.rest_wk.mean() / g.rest_wk.std(ddof=1) * np.sqrt(len(g))
    h = lambda q: f"{q.rest_pct.mean():+.2f}% ({100*(q.rest_pct>0).mean():.0f}%, n{len(q)})" if len(q) >= 10 else "-"
    return {"n": len(g), "win": round(100 * float((g.rest_pct > 0).mean()), 1), "rest": round(float(g.rest_pct.mean()), 2),
            "rest_wk": round(float(g.rest_wk.mean()), 3), "t": round(float(t), 1), "2003-18": h(g[g.d < "2019"]), "2019-26": h(g[g.d >= "2019"])}


B = {"current (x usual winning move)": ("cur", [(-9, 0, "against so far"), (0, .5, "0-50%"), (.5, 1, "50-100%"), (1, 1.5, "100-150%"), (1.5, 99, "150%+")]),
     "vol (so far in normal weeks)": ("so_wk", [(-99, 0, "against so far"), (0, 1, "0-1 wk"), (1, 2, "1-2 wk"), (2, 3, "2-3 wk"), (3, 4, "3-4 wk"), (4, 99, "4+ wk")]),
     "unwind (commercials gave back)": ("unwind", [(-99, 0, "still adding"), (0, .25, "0-25%"), (.25, .5, "25-50%"), (.5, 1, "50-100%"), (1, 99, "100%+ (past normal)")])}
out = {}
for name, (col, bins) in B.items():
    x = df[df[col].notna()]
    out[name] = {lab: st(x[(x[col] > lo) & (x[col] <= hi)]) for lo, hi, lab in bins}
    print(f"\n{name}   (weekly checks n{len(x)})")
    for lo, hi, lab in bins:
        o = out[name][lab]
        print(f"   {lab:22s} rest {o['rest']:+.2f}% won {o['win']:4.1f}% t{o['t']:+5.1f} n{o['n']:5d} | 2003-18 {o['2003-18']:28s} 2019-26 {o['2019-26']}" if o else f"   {lab:22s} -")
json.dump(out, open(os.path.join(HERE, "..", "data", "research", "cot_done_general.json"), "w"), indent=1, default=str)
