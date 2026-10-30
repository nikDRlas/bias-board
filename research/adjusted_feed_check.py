"""RESULT 2026-10-30: the board's LSE daily bars for CL/NG/ZW/ZC/ZS/PL are UNADJUSTED (level within ~1% of TV
unadjusted, 15-52% off the back-adjusted series; roll gaps land on weekends -> Monday gaps). It does not matter for the
daily canon result: pooled over the 6 markets LSE +0.92 R/setup (19-22 +1.24 / 23-26 +0.56), TV back-adjusted +0.91
(+1.26 / +0.46, t 3.1), TV unadjusted +1.04. Per market only natgas depends on the feed (-0.39 LSE, -0.31 adjusted,
+0.87 unadjusted) = NG has no stable read either way. TV covers 173 of the 189 setups (calendar mismatches).
Adjusted vs unadjusted futures for the extra markets (2026-10-30). The board's daily bars for oil / natgas / grains /
platinum / Dow come from LSE CFDs. Question: are they roll-adjusted? Then the daily canon test (daily_stop_grid_test.py
rules: zone stop, re-enter, hold to the verdict exit, 0.02 wk-ATR cost) is re-run on the same verdicts with the user's
TradingView continuous files, back-adjusted (additive, TV default) and unadjusted, to see if the result depends on it."""
import sys, os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import daily_stop_grid_test as DG                     # noqa: E402
import core as C                                      # noqa: E402
TV = "/Users/Niklas/Downloads/Backtest CSV/"
FILES = {"CL": ("Adjsuted/NYMEX_CL1!, 1D_a72cb.csv", "Energies/NYMEX_CL1!, 1D_76418.csv"),
         "NG": ("Adjsuted/NYMEX_NG1!, 1D_9028f.csv", "Energies/NYMEX_NG1!, 1D_dedc1.csv"),
         "ZW": ("Adjsuted/CBOT_DL_ZW1!, 1D_a13d2.csv", "Agris/CBOT_DL_ZW1!, 1D_03c29.csv"),
         "ZC": ("Adjsuted/CBOT_DL_ZC1!, 1D_97e27.csv", "Agris/CBOT_DL_ZC1!, 1D_ac011.csv"),
         "ZS": ("Adjsuted/CBOT_DL_ZS1!, 1D_846e5.csv", "Agris/CBOT_DL_ZS1!, 1D_0d628.csv"),
         "PL": ("Adjsuted/NYMEX_PL1!, 1D_d0a67.csv", "Metals/NYMEX_PL1!, 1D_fc41b.csv")}


def tv(p):
    d = pd.read_csv(TV + p)
    d["ts"] = (pd.to_datetime(d.time, unit="s") + pd.Timedelta(hours=6)).dt.normalize()   # TV daily stamp = session open
    return d.set_index("ts")[["open", "high", "low", "close"]].astype(float)


def lse(k):
    return pd.read_csv(f"{DG.BB}/data/live/{k}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]]


def test(k, d):
    d = d[(d.index.dayofweek < 5) & (d.high > d.low) & (d.index >= "2012-01-01")]
    d = d[~d.index.duplicated()].sort_index()
    w = d.resample("W-FRI").agg(DG.AGG).dropna()
    tr = np.maximum(w.high - w.low, np.maximum(abs(w.high - w.close.shift()), abs(w.low - w.close.shift())))
    O, H, L, Cc, idx = d.open.to_numpy(), d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), d.index
    wa = tr.ewm(alpha=1 / 14, adjust=False).mean().reindex(idx, method="ffill").shift(1).bfill().to_numpy()
    E = DG.entries(d, w, O, H, L, Cc, idx)
    rows = []
    for r in DG.V[DG.V.m == k].itertuples():
        a, b = idx.searchsorted(r.entry), idx.searchsorted(r.exit)
        if b >= len(idx) or b <= a or idx[a] != r.entry:
            continue
        sg = r.sg
        for nm in ("canon D", "verdict"):
            if nm == "verdict":
                evs = [(a, Cc[a], Cc[a] - sg * 0.75 * wa[a], "c")]
            else:
                evs = [(i, f, st, kd) for (i, s_, f, st, kd) in E[nm] if s_ == sg]
            for x in (DG.run(evs, a, b, sg, O, H, L, Cc, wa) or [None]):
                rows.append({"k": k, "t": r.t, "vid": r.Index, "set": nm, "took": x is not None, "r": x[0] if x else 0.0,
                             "stop_wk": x[2] if x else np.nan, "d": idx[x[3]] if x else pd.NaT})
    return pd.DataFrame(rows)


def summ(g):
    g = g.assign(rc=g.r - np.where(g.took, 0.02 / g.stop_wk.clip(lower=0.1), 0.0))
    pv = g.groupby("vid").agg(r=("r", "sum"), n=("took", "sum"), t=("t", "first"))
    tk = g[g.took].sort_values("d"); eq = tk.rc.groupby(tk.d).sum().cumsum(); dd = (eq - eq.cummax()).min()
    e, l = pv[pv.t < "2023"], pv[pv.t >= "2023"]
    return {"setups": len(pv), "trades": int(g.took.sum()), "R/setup": pv.r.mean(),
            "t": pv.r.mean() / pv.r.std(ddof=1) * np.sqrt(len(pv)), "19-22": e.r.mean(), "23-26": l.r.mean(),
            "ratio": tk.rc.sum() / 7.8 / abs(dd)}


if __name__ == "__main__":
    pd.set_option("display.width", 200); pd.set_option("display.float_format", lambda v: f"{v:+.2f}")
    print("=== is the LSE series adjusted? (2018+, daily closes) ===")
    for k, (fa, fu) in FILES.items():
        a, u, l = tv(fa).close, tv(fu).close, lse(k).close
        l.index = l.index.normalize()
        df = pd.concat({"lse": l, "adj": a, "unadj": u}, axis=1, sort=True).dropna(); df = df[df.index >= "2018-01-01"]
        sc = np.median(df.unadj / df.lse); df["lse"] *= sc                      # units (wheat $ vs cents)
        off = (df.adj - df.unadj).diff(); roll = off.abs() > 0.5 * df.unadj.diff().abs().median()
        dev_u = np.median(np.abs(np.log(df.lse / df.unadj))) * 100
        dev_a = np.median(np.abs(np.log(df.lse / df.adj.where(df.adj > 0)))) * 100
        print(f"{k}: LSE level vs unadjusted median off {dev_u:4.1f}%, vs adjusted {dev_a:5.1f}%; TV rolls/yr {roll.sum()/8.8:.1f}")
    out, T = [], []
    for k in FILES:
        for feed, d in (("LSE (board)", lse(k)), ("TV adjusted", tv(FILES[k][0])), ("TV unadjusted", tv(FILES[k][1]))):
            if C.M[k][2]:
                d = 1 / d
            t = test(k, d).assign(feed=feed); T.append(t)
    T = pd.concat(T)
    for (feed, s), g in T.groupby(["feed", "set"]):
        out.append({"entry": s, "feed": feed, **summ(g)})
    print("\n=== daily canon (own zone stop) and verdict entry, CL NG ZW ZC ZS PL pooled ===")
    print(pd.DataFrame(out).sort_values(["entry", "feed"]).to_string(index=False))
    print("\n=== canon D per market ===")
    print(T[T.set == "canon D"].groupby(["k", "feed"]).apply(lambda g: pd.Series(summ(g)), include_groups=False).unstack("feed")["R/setup"].to_string())
