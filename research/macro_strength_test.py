"""RESULT 2026-10-30: the size of the score does not matter, and neither does its sign - the gate was cancelling the
BETTER verdicts. US indices + gold/silver, walk-forward without the gate: macro against 64 verdicts 76.6% won +3.50%
(+2.61% vs drift, t 3.4, both halves +3.47 / +3.53), clearly against (<= -3) 78.9% +4.03%, weakly (-1) 81.8% +2.75%,
flat 73.3% +2.82%, agreeing 38 verdicts 63.2% +2.31% (19-22 -0.41). Gold + silver against 77.4% +4.44% vs agreeing
41.7% +2.13%; silver against 84.2% (16/19). Whole board without the gate: 571 verdicts 61.1% +1.82% (19-22 +1.66, 23-26
+2.00, t 5.2) vs 538 58.9% +1.66% (+1.43 / +1.93, t 4.5). Gate switched off (verdict.MACRO_GATE).
Does the SIZE of the macro score matter, or only its sign? (2026-10-30)
Walk-forward 2019-26 without the macro gate (SKIP_SLOW=1 GATES=done OUT=verdict_nomacro.json), the five US-driven
markets (ES NQ YM GC SI). Each verdict tagged with the macro total score (bias/macro.py) at its Saturday, signed to the
verdict's side (+ = agrees). Result = % to the verdict exit (verdict_test 'r'), and vs holding the market long over the
same days (drift, as in tools_macro_align)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/bias-board/bias")
import core as C, macro as MC
BB = "/Users/Niklas/bias-board"
V = pd.DataFrame(json.load(open(f"{BB}/data/research/verdict_nomacro.json"))["trades"])
B = pd.DataFrame(json.load(open(f"{BB}/data/research/verdict.json"))["trades"])
for D in (V, B):
    for c in ("t", "entry", "exit"):
        D[c] = pd.to_datetime(D[c])
cal = MC.load_calendar()
days = pd.date_range("2015-06-01", C.TODAY)
V = V[V.m.isin(["ES", "NQ", "YM", "GC", "SI"])].copy()
sc = {k: MC.market_scores(cal, k, days)["total"] for k in V.m.unique()}
V["sg"] = np.where(V.v == "BULLISH", 1, -1)
V["score"] = [sc[r.m][sc[r.m].index <= r.t].iloc[-1] for r in V.itertuples()]
V["al"] = V.score * V.sg
px = {k: C.load_px(k) for k in V.m.unique()}


def drift(k, a_t, b_t, sg):
    """the market's usual move in the verdict's direction over the same number of days, from the 10 years before
    (tools_macro_align's 'drift' footing)"""
    p = px[k]; lc = np.log(p.to_numpy(float))
    a, b = p.index.searchsorted(a_t), p.index.searchsorted(b_t)
    L, lo = b - a, max(0, a - 2520)
    d = float((lc[lo + L:a] - lc[lo:a - L]).mean())
    return 100 * (np.exp(sg * d) - 1)


V["drift"] = [drift(r.m, r.entry, r.exit, r.sg) for r in V.itertuples()]
V["vs"] = V.r - V.drift
V.to_csv(f"{BB}/data/research/macro_strength.csv", index=False)


def line(g, lab):
    if len(g) < 3:
        print(f"  {lab:34s} n {len(g):3d}"); return
    t = g.vs.mean() / g.vs.std(ddof=1) * np.sqrt(len(g))
    e, l = g[g.t < "2023"], g[g.t >= "2023"]
    print(f"  {lab:34s} n {len(g):3d} won {100*(g.r>0).mean():5.1f}% avg {g.r.mean():+6.2f}% vs-hold {g.vs.mean():+6.2f} t {t:+5.1f} | "
          f"19-22 {e.r.mean() if len(e) else np.nan:+6.2f} ({len(e)})  23-26 {l.r.mean() if len(l) else np.nan:+6.2f} ({len(l)})")


print(f"score distribution at verdicts: {V.score.describe()[['min','25%','50%','75%','max']].to_dict()}")
for name, G in (("ALL 5 (ES NQ YM GC SI)", V), ("GOLD + SILVER", V[V.m.isin(["GC", "SI"])]), ("US INDICES", V[V.m.isin(["ES", "NQ", "YM"])]),
                ("SILVER", V[V.m == "SI"]), ("GOLD", V[V.m == "GC"])):
    print(f"\n=== {name}: signed macro score at the verdict (+ = agrees with the side) ===")
    for lab, m in (("<= -3 (clearly against)", G.al <= -3), ("-2", G.al == -2), ("-1 (weakly against)", G.al == -1),
                   ("0 (flat)", G.al == 0), ("+1", G.al == 1), ("+2", G.al == 2), (">= +3 (clearly agrees)", G.al >= 3)):
        line(G[m], lab)
    print("  --")
    line(G[G.al < 0], "against (any) = board stands aside")
    line(G[G.al == 0], "flat = board stands aside")
    line(G[G.al > 0], "agrees = board shows it")
    line(G, "no macro gate at all")
    line(G[G.al >= -1], "gate only at <= -2")
def st(g):
    if len(g) < 5:
        return None
    t = g.vs.mean() / g.vs.std(ddof=1) * np.sqrt(len(g))
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "vs_drift": round(float(g.vs.mean()), 2), "t": round(float(t), 2),
            "2019-22": round(float(g[g.t < "2023"].r.mean()), 2), "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2)}


json.dump({"Board verdict": {"macro against": st(V[V.al < 0]), "macro agrees": st(V[V.al > 0]), "macro flat": st(V[V.al == 0]),
                             "clearly against (<= -3)": st(V[V.al <= -3])},
           "note": "walk-forward 2019-26 without the macro gate, ES NQ YM GC SI, result to the verdict exit"},
          open(f"{BB}/data/research/macro_strength.json", "w"), indent=1)
print("\nsilver verdicts without the macro gate:")
print(V[V.m == "SI"][["t", "v", "basis", "score", "r", "drift", "vs"]].round(2).to_string(index=False))
