"""Per-window check of the agricultural calendar windows on the board now (2026-10-27), with the board's own trading-day
windows (seasonal.Calendar: start = s-th trading day of the year, L trading days long):
  record 2011-25    how the board found it (15 years, needs 12)
  walk-forward      every year 2019-25: did the 15 years BEFORE that year already make it a 12-of-15 window (same s, L,
                    side), and what did it do in that year (out of sample)?
  each year 2019-25 the window's result in every recent year, qualified or not
  shifted +-5 days  wins of the same window started 5 trading days earlier / later (a real seasonal is not one date)
  pre-2011          years before the scan's 15-year lookback (never used to find it)"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C  # noqa: E402
import seasonal as SS  # noqa: E402

d = json.load(open(os.path.join(HERE, "..", "data", "live", "outlook.json")))["markets"]
for k in ("ZC", "ZW", "ZS", "SB", "KC", "LE"):
    p = C.load_px(k)
    cal = SS.Calendar(p)
    vol = cal.day_vol(p.index[-1])
    for w in d[k]["seas"]["table"]:
        s, L, side = int(w["s"]), int(w["len"]), w["side"]
        sg = 1 if side == "BUY" else -1
        def res(y, sh=0):
            if y not in cal.first:
                return None
            a = cal.first[y][0] + s + sh
            if a < 0 or a + L >= cal.n:
                return None
            return sg * 100 * (np.exp(cal.lc[a + L] - cal.lc[a]) - 1)
        ins = [res(y) for y in range(2011, 2026)]
        wf = []
        for y in range(2019, 2026):
            prior = [res(x) for x in range(y - 15, y)]
            if None not in prior and sum(v > 0 for v in prior) >= 12 and res(y) is not None:
                wf.append(res(y))
        post = [res(y) for y in range(2019, 2026)]
        pre = [v for v in (res(y) for y in range(2000, 2011)) if v is not None]
        sh = [sum((res(y, x) or 0) > 0 for y in range(2011, 2026)) for x in (-5, 5)]
        size = abs(np.mean(ins)) / 100 / vol
        print(f"{k} {side:4s} {w['start'][5:]}..{w['end'][5:]} ({size:.1f} days) | 2011-25 {sum(v>0 for v in ins)}/15 avg{np.mean(ins):+5.2f}% "
              f"| walk-fwd: qualified {len(wf)}/7 yrs, won {sum(v>0 for v in wf)}, avg {np.mean(wf) if wf else float('nan'):+5.2f}% "
              f"| 2019-25 {sum(v>0 for v in post)}/7 avg{np.mean(post):+5.2f}% | -5d {sh[0]}/15 +5d {sh[1]}/15 "
              f"| pre-2011 {sum(v>0 for v in pre)}/{len(pre)} avg{np.mean(pre) if pre else float('nan'):+5.2f}%")
