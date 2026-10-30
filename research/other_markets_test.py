"""RESULT 2026-10-30: DAILY canon (own zone stop) on the 10 extra markets (6N CL HG NG PL SB YM ZC ZS ZW; PA has no
verdicts) +0.86 R/setup, t 3.4, 19-22 +0.99 / 23-26 +0.70, 285/300 setups entered, 641 trades, ratio 0.87 (core 10:
+1.09, ratio 1.58). Per market n 19-50, noisy: ZW +1.43, ZC +1.00, SB +0.97, CL +0.82 (23-26 +0.16), YM +2.62, PL +2.08;
NG -0.39, HG -0.57, ZS +0.05, 6N -0.04 - no single market is significant, do not drop any on this. Verdict entry on the
extras ratio 0.77, so the zone adds R there but little smoothness. 4h (CFD feed 2023-07+, CL/HG/YM only, 22 setups):
canon >=0.25 wk +2.57 vs core +1.59 same window, V4 +2.27 vs +1.41, three-tier +0.35 vs +1.09, Nested W->4h +1.05 on 7
setups - one half only, too few to validate; CL itself weak on 4h canon (+0.57, t 0.4). No 4h natgas / wheat anywhere.
Board entries on the markets outside the 10-market 4h set (2026-10-30). Daily side: read from
daily_stop_grid.csv.gz (canon / V4 / three-tier / prev-day on all 21 markets). 4h side: the only extra 4h history is
the LSE CFD feed from 2023-06 for oil (USOIL = CL), copper (COPPER = HG) and the Dow (DOW = YM) - no 4h natgas or
wheat. Those three run through the same 4h entries as nested_bigbrother_test.py (canon / V4 / three-tier B / Nested
weekly->4h), compared with the 10 core markets on the same window (verdicts from 2023-07, after a month of zone
warm-up). Same rules: verdict direction, re-enter after a stop, hold to the verdict exit, 0.02 wk-ATR cost."""
import sys, os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nested_bigbrother_test as NB                   # noqa: E402
import core as C                                      # noqa: E402
BB = "/Users/Niklas/bias-board/data/research"
TEN = NB.MK
FEED = {k: k for k in TEN} | {"CL": "USOIL", "HG": "COPPER", "YM": "DOW"}
START = "2023-07-01"
STOPS = (("own/zone", 0, False), ("zone, >=0.25 wk", 0.25, False), ("zone, >=0.5 wk", 0.5, False), ("fixed 0.75 wk", 0.75, True))


def tstat(x):
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan


def stats(g, yrs):
    g = g.assign(rc=g.r - np.where(g.took, 0.02 / g.stop_wk.clip(lower=0.1), 0.0))
    pv = g.groupby("vid").agg(r=("r", "sum"), n=("took", "sum"), t=("t", "first"))
    tk = g[g.took].sort_values("d")
    eq = tk.rc.groupby(tk.d).sum().cumsum(); dd = (eq - eq.cummax()).min() if len(eq) else np.nan
    ry = tk.rc.sum() / yrs
    e, l = pv[pv.t < "2023"], pv[pv.t >= "2023"]
    return {"setups": len(pv), "entered": int((pv.n > 0).sum()), "trades": int(g.took.sum()), "won%": 100 * (tk.r > 0).mean(),
            "R/setup": pv.r.mean(), "t": tstat(pv.r), "19-22": e.r.mean(), "23-26": l.r.mean(),
            "R/yr": ry, "maxDD": dd, "ratio": ry / abs(dd) if dd else np.nan}


if __name__ == "__main__":
    pd.set_option("display.width", 200); pd.set_option("display.float_format", lambda v: f"{v:+.2f}")
    # ---- daily side, all 21 markets
    D = pd.read_csv(f"{BB}/daily_stop_grid.csv.gz", parse_dates=["t", "d"])
    out = []
    for (s, sp), g in D.groupby(["set", "stop"]):
        for grp, x in (("10 core", g[g.k.isin(TEN)]), ("11 others", g[~g.k.isin(TEN)])):
            out.append({"entry": s, "stop": sp, "markets": grp, **stats(x, 7.8)})
    print("=== DAILY entries, 2019-26 ===\n", pd.DataFrame(out).to_string(index=False))
    g = D[(D.set == "canon D") & (D.stop == "own/zone") & ~D.k.isin(TEN)]
    print("\n=== canon daily, own zone stop, per extra market ===")
    print(pd.DataFrame([{"k": k, **stats(x, 7.8)} for k, x in g.groupby("k")]).to_string(index=False))

    # ---- 4h side, 2023-07+
    rows = []
    for k, f in FEED.items():
        meta = C.M[k]
        hb = pd.read_csv(f"{NB.H4}/{f}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
        hb = hb[~hb.index.duplicated()].sort_index(); hb = hb[(hb.high > hb.low) & (hb.index >= "2016-01-01") & (hb.index.dayofweek < 5)]
        if meta[2]:
            hb = NB.inv(hb)
        db = hb.groupby(hb.index.normalize()).agg(NB.AGG)
        O, H, L, Cc, idx = hb.open.to_numpy(), hb.high.to_numpy(), hb.low.to_numpy(), hb.close.to_numpy(), hb.index
        wk = hb.resample("W-FRI").agg(NB.AGG).dropna()
        wtr = np.maximum(wk.high - wk.low, np.maximum(abs(wk.high - wk.close.shift()), abs(wk.low - wk.close.shift())))
        wa = wtr.ewm(alpha=1 / 14, adjust=False).mean().reindex(idx, method="ffill").shift(1).bfill().to_numpy()
        atr = NB.wilder(H, L, Cc)
        reg_w = idx.searchsorted(wk.index + pd.Timedelta(days=1))
        E = {"canon 4h": NB.canon_entries(hb, O, H, L), "V4 4h": NB.v4_entries(hb, O, H, L),
             "three-tier B 4h": NB.tier_b_entries(hb, O, H, L),
             "Nested W->4h": NB.nested_entries(hb, wk, reg_w, O, H, L, Cc, atr)}
        Vk = NB.V[(NB.V.m == k) & (NB.V.t >= START)]
        for r in Vk.itertuples():
            a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit + pd.Timedelta(days=1)) - 1
            if b >= len(idx) or b <= a or idx[a] < r.entry:
                continue
            sg = r.sg
            res = {("verdict entry", "fixed 0.75 wk"): NB.run([(a, Cc[a], Cc[a] - sg * 0.75 * wa[a])], a, b, sg, O, H, L, Cc, wa)}
            for nm, ev in E.items():
                own = [(i, fl, st) for (i, s_, fl, st, top, bot) in ev if s_ == sg]
                for lab, kk, fixed in STOPS:
                    if fixed:
                        evs = [(i, fl, fl - sg * kk * wa[i]) for (i, fl, st) in own]
                    else:
                        evs = [(i, fl, st if sg * (fl - st) >= kk * wa[i] else fl - sg * kk * wa[i]) for (i, fl, st) in own]
                    res[(nm, lab)] = NB.run(evs, a, b, sg, O, H, L, Cc, wa)
            for (nm, lab), rr in res.items():
                for x in (rr or [None]):
                    rows.append({"k": k, "t": r.t, "vid": r.Index, "set": nm, "stop": lab, "took": x is not None,
                                 "r": x[0] if x else 0.0, "stop_wk": x[2] if x else np.nan, "d": idx[x[3]] if x else pd.NaT})
        print(k, end=" ", flush=True)
    print()
    T = pd.DataFrame(rows); T.to_csv(f"{BB}/other_markets_4h.csv.gz", index=False)
    yrs = (pd.Timestamp("2026-10-01") - pd.Timestamp(START)).days / 365.25
    out = []
    for (s, sp), g in T.groupby(["set", "stop"], sort=False):
        for grp, x in (("10 core", g[g.k.isin(TEN)]), ("CL+HG+YM", g[~g.k.isin(TEN)])):
            out.append({"entry": s, "stop": sp, "markets": grp, **{c: v for c, v in stats(x, yrs).items() if c not in ("19-22", "23-26")}})
    print(f"\n=== 4h entries, verdicts from {START} ===\n", pd.DataFrame(out).to_string(index=False))
    g = T[~T.k.isin(TEN) & (T.stop.isin(["zone, >=0.25 wk", "own/zone", "fixed 0.75 wk"]))]
    print("\n=== per extra market ===")
    print(pd.DataFrame([{"k": k, "entry": s, "stop": sp, **{c: v for c, v in stats(x, yrs).items() if c not in ("19-22", "23-26")}}
                        for (k, s, sp), x in g.groupby(["k", "set", "stop"])]).to_string(index=False))
