#!/usr/bin/env python3
"""Pick, per country and indicator, the LSE calendar event that best reproduces the EdgeFinder replica's single-currency
group scores (growth / inflation / labour), by coordinate ascent on the share of days with the exact same group value.
Output: data/macro/events.json"""
import json, os, re, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import macro as MC                                     # noqa: E402

SRC = os.path.expanduser("~/Downloads/scores_taeglich_gesamt_und_macro.csv")
REP = {"USD": "US-DOLLAR", "EUR": "EURO", "GBP": "GB-POUND", "JPY": "JP-YEN", "AUD": "AU-DOLLAR", "CAD": "CA-DOLLAR"}
# Switzerland and New Zealand are on the LSE calendar only from Feb 2026 (the replica used TradingView there)
GCOL = {"growth": "macro_wachstum", "inflation": "macro_inflation", "labour": "macro_arbeitsmarkt"}
PAT = {"GDP": r"^gdp growth rate (qoq|annualized)|^gdp (qoq|yoy|growth)", "Retail": r"^retail sales (mom|yoy)|^household spending (mom|yoy)",
       "MfgPMI": r"^(s&p global |ism |procure\.ch |caixin )?manufacturing pmi", "SvcPMI": r"^(s&p global |ism )?(uk )?(services|non-manufacturing) pmi",
       "ConsConf": r"consumer confidence|consumer sentiment|consumer climate",
       "CPI": r"^(inflation rate|cpi) (yoy|mom)$", "PPI": r"^(ppi|producer price index|ppi output)( yoy| mom)?$|^ppi output (yoy|mom)$", "PCE": r"pce price index",
       "NFP": r"^non farm payrolls$|^employment change$", "ADP": r"^adp employment change$", "Claims": r"^initial jobless claims$|^claimant count change$",
       "JOLTS": r"^jolts job openings$", "Unemp": r"^unemployment rate$"}
E_OK = re.compile(r"")


if __name__ == "__main__":
    cal = MC.load_calendar()
    rep = pd.read_csv(SRC, parse_dates=["date"])
    days = pd.date_range("2016-01-01", "2026-09-16")
    events, report = {}, {}
    for cur, sym in REP.items():
        r = rep[rep.symbol == sym].set_index("date")
        reg = MC.REGION[cur]
        evs = cal[cal.region_code == reg].event.value_counts()
        evs = evs[evs >= 15].index
        cand = {ind: [None] + [e for e in evs if re.search(p, re.sub(r"^ALL ", "", e), re.I)] for ind, p in PAT.items()}
        pick = {ind: None for ind in PAT}
        cache = {}
        def cell(ind, e):
            if (ind, e) not in cache:
                cache[(ind, e)] = MC.cell_series(cal, reg, e, days, ind in MC.INVERT) if e else pd.Series(0.0, index=days)
            return cache[(ind, e)]
        for g, inds in MC.GROUPS.items():
            target = r[GCOL[g]].reindex(days)
            ok = target.notna()
            tot = lambda pk: sum(cell(i, pk[i]) for i in inds)
            err = lambda pk: float((tot(pk)[ok] - target[ok]).abs().mean())
            for _ in range(4):
                for ind in inds:
                    pick[ind] = min(cand[ind], key=lambda e: err({**pick, ind: e}))
            t = tot(pick)
            report[f"{cur} {g}"] = {"exact": round(float((t[ok] == target[ok]).mean()), 3), "mean_abs_err": round(err(pick), 2),
                                    "corr": round(float(np.corrcoef(t[ok], target[ok])[0, 1]), 2)}
        events[cur] = {k: v for k, v in pick.items() if v}
        print(cur, {g: report[f"{cur} {g}"] for g in MC.GROUPS}, flush=True)
        print("    ", events[cur], flush=True)
    json.dump({"events": events, "match": report}, open(os.path.join(HERE, "..", "data", "macro", "events.json"), "w"), indent=1)
