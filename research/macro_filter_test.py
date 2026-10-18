#!/usr/bin/env python3
"""Does the EdgeFinder-replica macro score improve the board's verdicts?

Board verdicts from the walk-forward test (research/verdict_test.py, current rules), 2019 to the end of the replica
(16 Sep 2026). For each verdict the replica's score on that Saturday (last value on or before it) for the market:
agrees (same sign as the verdict), against, or neutral (0). Scores: macro_score (growth + inflation + labour),
its parts, and the total ef_score. The replica: ~/Downloads/scores_taeglich_gesamt_und_macro.csv (user's rebuild).
Output: data/research/macro_filter.json"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Downloads/scores_taeglich_gesamt_und_macro.csv")
MAP = {"GC": "GOLD", "SI": "SILVER", "PL": "PLATINUM", "HG": "COPPER", "CL": "USOIL", "NG": "NATGAS",
       "6E": "EURO", "6B": "GB-POUND", "6J": "JP-YEN", "6S": "CH-FRANC", "6A": "AU-DOLLAR", "6C": "CA-DOLLAR",
       "6N": "NZ-DOLLAR", "DX": "US-DOLLAR", "ES": "SPX500", "NQ": "NASDAQ", "YM": "DOW"}
COLS = ["macro_score", "macro_wachstum", "macro_inflation", "macro_arbeitsmarkt", "ef_score"]


def st(g):
    if len(g) < 8:
        return None
    return {"n": len(g), "win": round(100 * float((g.r > 0).mean()), 1), "avg": round(float(g.r.mean()), 2),
            "t": round(float(g.r.mean() / g.r.std(ddof=1) * np.sqrt(len(g))), 2),
            "2019-22": round(float(g[g.t < "2023"].r.mean()), 2) if (g.t < "2023").sum() else None,
            "2023-26": round(float(g[g.t >= "2023"].r.mean()), 2) if (g.t >= "2023").sum() else None}


if __name__ == "__main__":
    ef = pd.read_csv(SRC, usecols=["date", "symbol"] + COLS, parse_dates=["date"])
    T = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
    T = T[T.m.isin(MAP) & (pd.to_datetime(T.t) <= ef.date.max())].copy()
    for col in COLS:
        lab = []
        for _, r in T.iterrows():
            s = ef[(ef.symbol == MAP[r.m]) & (ef.date <= pd.Timestamp(r.t))]
            v = s[col].iloc[-1] if len(s) else np.nan
            sg = 1 if r.v == "BULLISH" else -1
            lab.append("no data" if not np.isfinite(v) else "neutral" if v == 0 else "agrees" if np.sign(v) == sg else "against")
        T["lab_" + col] = lab
    res = {"verdicts covered": len(T), "all": st(T)}
    for col in COLS:
        res[col] = {k: st(g) for k, g in T.groupby("lab_" + col)}
        res[col + " by sector"] = {f"{s} · {k}": st(g) for (s, k), g in T.groupby(["sector", "lab_" + col])}
    json.dump(res, open(os.path.join(HERE, "..", "data", "research", "macro_filter.json"), "w"), indent=1)
    f = lambda o: f"n{o['n']:4d} {o['win']:4.1f}% avg {o['avg']:+.2f}% t{o['t']:+.1f} | 19-22 {o['2019-22']:+.2f} 23-26 {o['2023-26']:+.2f}" if o else "-"
    print("verdicts:", res["verdicts covered"], f(res["all"]))
    for col in COLS:
        print(f"\n{col}")
        for k, o in res[col].items():
            print(f"   {k:8s} {f(o)}")
        for k, o in res[col + " by sector"].items():
            if o and col in ("macro_score", "ef_score"):
                print(f"      {k:28s} {f(o)}")
