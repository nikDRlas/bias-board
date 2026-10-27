"""Swing yardstick (2026-10-27): the user times entries with S/D zones, so what counts is the move from the bottom to
the following top while a verdict is held (shorts: top to the following bottom), not the MFE from the signal day.
For every board verdict 2019-26 (data/research/verdict.json, walk-forward): on daily closes between entry and exit
  swing      biggest bottom->later-top move in the verdict's direction (%)
  opp_swing  the same against it (top->later-bottom for a long)
  mfe        the old yardstick, from the entry
  bottom_at  where in the hold the swing's bottom lay (0 = entry day, 1 = exit day), dip = how far below entry
Control: 200 random windows of the same market and length per verdict (direction-free swing size)."""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
import core as C  # noqa: E402

rng = np.random.default_rng(7)


def swing(x):
    """biggest rise from a low to a later high in x (as a fraction), with the low's and high's positions"""
    lo = np.minimum.accumulate(x)
    ilo = np.array([int(np.argmin(x[:j + 1])) for j in range(len(x))])
    r = x / lo - 1
    j = int(np.argmax(r))
    return float(r[j]), ilo[j], j


T = pd.DataFrame(json.load(open(os.path.join(HERE, "..", "data", "research", "verdict.json")))["trades"])
rows = []
for k, g in T.groupby("m"):
    p = C.load_px(k)
    px = p.to_numpy(float)
    lr = np.diff(np.log(px))
    for _, r in g.iterrows():
        a, b = p.index.searchsorted(pd.Timestamp(r.t) + pd.Timedelta(days=1)), p.index.searchsorted(pd.Timestamp(r.exit))
        b = min(b, len(px) - 1)
        if b - a < 3:
            continue
        sg = 1 if r.v == "BULLISH" else -1
        seg = px[a:b + 1] if sg > 0 else 1 / px[a:b + 1]          # a short's swing = the inverse price's rise
        sw, i0, i1 = swing(seg)
        osw, _, _ = swing(1 / seg)
        wk = 100 * lr[max(0, a - 253):a].std() * np.sqrt(5)
        L = b - a
        rs = rng.choice(np.arange(253, len(px) - L - 1), 200)
        rnd = np.mean([max(swing(px[s:s + L + 1])[0], swing(1 / px[s:s + L + 1])[0]) for s in rs[:60]])
        rnd_up = np.mean([swing(px[s:s + L + 1] if sg > 0 else 1 / px[s:s + L + 1])[0] for s in rs])
        rows.append({"m": k, "sector": r.sector, "basis": r.basis, "t": r.t, "v": r.v, "days": L, "end": r.r,
                     "mfe": 100 * float(seg.max() / seg[0] - 1), "swing": 100 * sw, "opp_swing": 100 * osw,
                     "rnd_swing": 100 * rnd_up, "dip": 100 * float(seg[i0] / seg[0] - 1),
                     "bottom_at": i0 / L, "top_at": i1 / L, "wk": wk})
R = pd.DataFrame(rows)
R.to_csv(os.path.join(HERE, "..", "data", "research", "swing_yardstick.csv"), index=False)


def show(g, lab):
    w = g.wk
    print(f"{lab:28s} n{len(g):4d} | swing {g.swing.mean():5.2f}% ({(g.swing/w).mean():3.1f} wk) opp {g.opp_swing.mean():5.2f}% "
          f"({(g.opp_swing/w).mean():3.1f} wk) rnd {g.rnd_swing.mean():5.2f}% | MFE {g.mfe.mean():5.2f}% ({(g.mfe/w).mean():3.1f} wk) "
          f"| swing>opp {100*(g.swing>g.opp_swing).mean():4.1f}% | dip {g.dip.mean():+5.2f}% bottom@{g.bottom_at.median():.2f} "
          f"| swing med {g.swing.median():5.2f}% p25 {g.swing.quantile(.25):5.2f}%")


show(R, "ALL 2019-26")
show(R[R.t < "2023"], "2019-22")
show(R[R.t >= "2023"], "2023-26")
for s, g in R.groupby("sector"):
    show(g, s)
for s, g in R.groupby("basis"):
    show(g, s)
show(R[R.end > 0], "winners")
show(R[R.end <= 0], "losers")
