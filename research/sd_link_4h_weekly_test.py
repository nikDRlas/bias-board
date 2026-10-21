"""4h zones gated by the last weekly zone touched + the board's bias, 1:1.
Set before looking: one series per market (LSE 1h, NY-wall-clock bins as in the canonical pipeline); weekly and 4h zones =
canon (body40, mult OFF, base 1-6) on that series; a zone is usable from the bar after its leg-out closes; weekly zones up to
104 weeks old, 4h zones up to 26 weeks; FIRST touch only. Weekly state = side of the last weekly zone touched (demand -> longs,
supply -> shorts), flips on the next weekly touch. 4h trade: limit at the proximal line (gap -> open), stop 0.75 x ATR(4h)
from the fill (B) or zone distal + 0.1 ATR (A), target 1R, resolved on 1h bars, stop first, fill bar's TP only on its close,
30-day cap, 0.03R cost. Board = walk-forward verdict active on the fill day (data/research/sdlink_verdicts.json)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/Niklas/supply_demand_dynamic")
from backtest.sd_fx_legout_atr import canon_meta
D = "/Users/Niklas/supply_demand_intraday/data_cache/lse_1h"
MAP = {"6E": ("EURUSD", 0), "6B": ("GBPUSD", 0), "6A": ("AUDUSD", 0), "6N": ("NZDUSD", 0), "6C": ("USDCAD", 1),
       "6S": ("USDCHF", 1), "6J": ("USDJPY", 1), "ES": ("SP500", 0), "NQ": ("NAS100", 0), "YM": ("DOW", 0),
       "GC": ("GOLD", 0), "SI": ("SILVER", 0), "HG": ("COPPER", 0), "CL": ("USOIL", 0)}
SECT = {**{k: "FX" for k in ("6E", "6B", "6A", "6N", "6C", "6S", "6J")}, "ES": "Indices", "NQ": "Indices", "YM": "Indices",
        "GC": "Metals & energy", "SI": "Metals & energy", "HG": "Metals & energy", "CL": "Metals & energy"}
AGG = {"open": "first", "high": "max", "low": "min", "close": "last"}
v = pd.DataFrame(json.load(open("/Users/Niklas/bias-board/data/research/sdlink_verdicts.json"))["trades"])
v["t"] = pd.to_datetime(v.t); v["exit"] = pd.to_datetime(v.exit); v["ep"] = range(len(v))
def board(k, d):
    g = v[(v.m == k) & (v.t < d) & (v.exit >= d)]
    return (0, "", -1) if not len(g) else ((1 if g.iloc[-1].v == "BULLISH" else -1), g.iloc[-1].basis, int(g.iloc[-1].ep))
def zones(bars):
    out = []
    for (side, cb, top, bot, lo, a) in canon_meta(bars, mult_on=False, body_min=40.0, base_min=1):
        sg = 1 if str(side).lower().startswith("d") or side == 1 else -1
        out.append((sg, bars.index[cb], top, bot))
    return out
def first_touch(idx, H, L, t0, t1, sg, prox):
    a, b = idx.searchsorted(t0, "right"), idx.searchsorted(t1)
    if a >= b: return None
    hit = (L[a:b] <= prox) if sg > 0 else (H[a:b] >= prox)
    j = int(np.argmax(hit))
    return a + j if hit[j] else None
rows = []
for k, (f, inv) in MAP.items():
    h = pd.read_csv(f"{D}/{f}.csv", parse_dates=["ts"]).set_index("ts")[["open", "high", "low", "close"]].astype(float)
    h = h[~h.index.duplicated()].sort_index()
    if inv: h = pd.DataFrame({"open": 1 / h.open, "high": 1 / h.low, "low": 1 / h.high, "close": 1 / h.close}, index=h.index)
    ny = h.index.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
    hn = h.copy(); hn.index = ny                                # NY wall clock, day starts 17:00 NY
    h4 = hn.resample("4h").agg(AGG).dropna(); wk = hn.resample("W-FRI").agg(AGG).dropna()
    idx, O, H, L, Cc = hn.index, hn.open.to_numpy(), hn.high.to_numpy(), hn.low.to_numpy(), hn.close.to_numpy()
    # weekly state timeline
    ev = []
    for sg, cbt, top, bot in zones(wk):
        start = cbt + pd.Timedelta(days=1)                      # bin label = week end; usable after it
        prox = top if sg > 0 else bot
        i = first_touch(idx, H, L, start, start + pd.Timedelta(weeks=104), sg, prox)
        if i is not None: ev.append((idx[i], sg))
    ev = sorted(ev); evt = np.array([e[0] for e in ev], dtype="datetime64[ns]"); evs = np.array([e[1] for e in ev])
    tr = np.maximum(h4.high - h4.low, np.maximum(abs(h4.high - h4.close.shift()), abs(h4.low - h4.close.shift())))
    atr4 = pd.Series(tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy(), index=h4.index)
    for sg, cbt, top, bot in zones(h4):
        if cbt < pd.Timestamp("2018-06-01"): continue
        start = cbt + pd.Timedelta(hours=4)
        prox, dist = (top, bot) if sg > 0 else (bot, top)
        i = first_touch(idx, H, L, start - pd.Timedelta(seconds=1), start + pd.Timedelta(weeks=26), sg, prox)
        if i is None or idx[i] < pd.Timestamp("2019-01-07"): continue
        a4 = float(atr4.loc[cbt])
        fill = min(O[i], prox) if sg > 0 else max(O[i], prox)
        n = int(np.searchsorted(evt, np.datetime64(idx[i]), "right"))
        wstate = int(evs[n - 1]) if n else 0
        day = (idx[i] - pd.Timedelta(hours=7)).normalize()
        b, basis, ep = board(k, day)
        for lab, stop in (("B 0.75 ATR", fill - sg * 0.75 * a4), ("A zone stop", dist - sg * 0.1 * a4)):
            R = sg * (fill - stop)
            if not (R > 0): res = -1.0
            else:
                tp = fill + sg * R; e = min(len(idx), idx.searchsorted(idx[i] + pd.Timedelta(days=30)))
                if e >= len(idx) - 1 and idx[-1] < idx[i] + pd.Timedelta(days=30): continue
                hs = (L[i:e] <= stop) if sg > 0 else (H[i:e] >= stop)
                ht = (H[i:e] >= tp) if sg > 0 else (L[i:e] <= tp)
                ht[0] = (Cc[i] >= tp) if sg > 0 else (Cc[i] <= tp)
                js = int(np.argmax(hs)) if hs.any() else 10**9; jt = int(np.argmax(ht)) if ht.any() else 10**9
                res = -1.0 if js <= jt and js < 10**9 else 1.0 if jt < 10**9 else sg * (Cc[e - 1] - fill) / R
            rows.append({"k": k, "sector": SECT[k], "d": idx[i], "side": sg, "stop": lab, "r": res - 0.03,
                         "weekly": wstate * sg, "board": b * sg, "basis": basis, "ep": ep})
    print(k, sum(r["k"] == k for r in rows) // 2, flush=True)
T = pd.DataFrame(rows); T.to_csv("/Users/Niklas/bias-board/data/research/sd_link_4h_weekly.csv", index=False)
