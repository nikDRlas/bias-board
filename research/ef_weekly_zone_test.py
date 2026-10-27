"""RESULT 2026-10-27 (B 0.75 ATR, ~7900 trades): no overall with-score effect (agrees>=5 +0.078R, neutral +0.018R, against<=-7 +0.111R). Post-hoc pockets (of ~40 cells): Indices zone WITH score>=5 +0.19R 60% n161; USD pairs zone AGAINST score<=-7 +0.24R 62% n142, all 3 periods + both sides. Crosses nothing. Forward test only (replica static).
Weekly S/D zones (same rules as bias-board research/sd_link_weekly_zones_test.py) gated by the EdgeFinder replica score.
Score = value on the last replica day BEFORE the fill day (no same-day info). Fills 2015-06 .. 2026-08."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic")
from backtest.sd_fx_legout_atr import canon_meta
LD = "/Users/Niklas/supply_demand_intraday/data_cache/lse_daily/"; BB = "/Users/Niklas/bias-board/data/history/lse/"
FX = ['EURUSD','GBPUSD','AUDUSD','NZDUSD','USDCAD','USDCHF','USDJPY','EURGBP','EURAUD','EURCAD','EURNZD','EURJPY','EURCHF',
      'GBPAUD','GBPCAD','GBPNZD','GBPJPY','GBPCHF','AUDCAD','AUDNZD','AUDJPY','AUDCHF','NZDCAD','NZDJPY','NZDCHF','CADJPY','CADCHF','CHFJPY']
OTHER = {'SPX500':LD+'SP500.csv','NASDAQ':LD+'NAS100.csv','DOW':LD+'DOW.csv','RUSSELL':LD+'RUSSELL.csv','DAX':LD+'DAX.csv',
         'GOLD':LD+'GOLD.csv','SILVER':LD+'SILVER.csv','PLATINUM':BB+'PL.csv.gz','COPPER':LD+'COPPER.csv','USOIL':LD+'USOIL.csv',
         'NATGAS':BB+'NG.csv.gz','USDZAR':LD+'USDZAR.csv'}
USD = {'EURUSD','GBPUSD','AUDUSD','NZDUSD','USDCAD','USDCHF','USDJPY','USDZAR'}
def grp(s): return "USD pairs" if s in USD else ("Crosses" if s in FX else ("Indices" if s in ('SPX500','NASDAQ','DOW','RUSSELL','DAX') else "Commodities"))
def load(f, sym):
    df = pd.read_csv(f, parse_dates=["ts"]).set_index("ts")[["open","high","low","close"]].astype(float).sort_index()
    df = df[(df.index.dayofweek < 5) & (df.index >= "2012-01-01")]
    if sym == 'DAX': df = df[df.close > 5000]
    med = df.close.rolling(5, center=True, min_periods=3).median(); lim = 10*np.log(df.close).diff().abs().median()
    bad = np.log(df.close/med).abs() > lim
    for c in ("open","high","low"): bad |= np.log(df[c]/med).abs() > 2*lim
    return df[~bad]
ef = pd.read_csv("/Users/Niklas/Downloads/scores_taeglich_gesamt_und_macro.csv", usecols=["date","symbol","ef_score"], parse_dates=["date"])
rows = []
for sym, f in [(p, LD+p+".csv") for p in FX] + list(OTHER.items()):
    d = load(f, sym); s = ef[ef.symbol == sym].set_index("date").ef_score.sort_index()
    w = d.resample("W-FRI").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
    tr = np.maximum(w.high-w.low, np.maximum(abs(w.high-w.close.shift()), abs(w.low-w.close.shift())))
    atr = tr.ewm(alpha=1/14, adjust=False).mean().to_numpy()
    O, H, L, Cc, idx = d.open.to_numpy(), d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), d.index
    for (side, cb, top, bot, lo, a) in canon_meta(w, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith(("d","1")) or side == 1 else -1
        live = w.index[cb] + pd.Timedelta(days=3); a0 = idx.searchsorted(live); dead = live + pd.Timedelta(weeks=104)
        prox, dist = (top, bot) if sg > 0 else (bot, top); aw = atr[cb]
        for i in range(a0, len(idx)):
            if idx[i] > dead: break
            if not (L[i] <= prox if sg > 0 else H[i] >= prox): continue
            if idx[i] < pd.Timestamp("2015-06-01"): break
            fill = min(O[i], prox) if sg > 0 else max(O[i], prox)
            ss = s[s.index < idx[i]]; sc = float(ss.iloc[-1]) if len(ss) else np.nan
            for lab, stop in (("A zone stop", dist - sg*0.1*aw), ("B 0.75 ATR", fill - sg*0.75*aw)):
                R = sg*(fill - stop)
                if not np.isfinite(R) or R <= 0: res = -1.0
                else:
                    tp = fill + sg*R; res = None
                    for j in range(i, min(len(idx), i+130)):
                        hs = L[j] <= stop if sg > 0 else H[j] >= stop
                        ht = H[j] >= tp if sg > 0 else L[j] <= tp
                        if j == i: ht = ht and (Cc[j] >= tp if sg > 0 else Cc[j] <= tp)
                        if hs: res = -1.0; break
                        if ht: res = 1.0; break
                    if res is None:
                        if i + 129 >= len(idx): continue
                        res = sg*(Cc[i+129] - fill)/R
                rows.append(dict(sym=sym, g=grp(sym), d=idx[i], side=sg, stop=lab, r=res, sc=sc*sg))   # sc>0 = score agrees
            break
T = pd.DataFrame(rows).dropna(subset=["sc"]); T.to_csv("ef_wzone.csv", index=False)
def line(g, lab):
    if len(g) < 5: return
    t = g.r.mean()/g.r.std(ddof=1)*np.sqrt(len(g))
    print(f"   {lab:22s} n{len(g):4d} won{100*(g.r>0).mean():5.1f}% exp{g.r.mean():+.3f}R t{t:+5.1f} | 15-18 {g[g.d<'2019'].r.mean():+.3f}  19-23 {g[(g.d>='2019')&(g.d<'2024')].r.mean():+.3f}  24-26 {g[g.d>='2024'].r.mean():+.3f} (n{(g.d>='2024').sum()})")
for st, G in T.groupby("stop"):
    for gname, GG in [("ALL", G)] + list(G.groupby("g")):
        print(f"=== {st} | {gname}")
        line(GG, "all zones")
        line(GG[GG.sc >= 5], "score agrees >=5"); line(GG[GG.sc >= 7], "score agrees >=7")
        line(GG[GG.sc.abs() < 5], "score neutral"); line(GG[GG.sc <= -5], "score against <=-5"); line(GG[GG.sc <= -7], "score against <=-7")
