#!/usr/bin/env python3
"""Weekly outlook (COT bias -> seasonality -> combined bias), zones left out.

COT   : LSE /vault/ref/cot + CFTC history (see outlook_recompile.load_cot).
Season: windows scored with the true-seasonality rule (each year's window return minus that
        year's trailing-252 drift known at entry), 15 prior years, windows of 5-90 days whose
        entry falls -2 to +8 weeks from the report date.
Run bias/pull.py first.  Output: data/live/outlook.json + site/outlook.html
"""
import json, os, sys, html
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core as R                                   # noqa: E402
from core import DRIFT_N                           # noqa: E402
import seasonal as SS                              # noqa: E402
import events as EV                                # noqa: E402
import verdict as VD                               # noqa: E402

ASOF, TODAY, M = R.ASOF, R.TODAY, R.M
LB, HIST = R.LB, R.HIST
HZ = {4: "4 weeks", 8: "8 weeks", 13: "3 months", 26: "6 months", 52: "1 year"}
YEARS = list(range(TODAY.year - 15, TODAY.year))
G = {"retail": "Retail", "comm": "Commercials", "fund": "Funds"}


# ------------------------------------------------------------------ COT, step 1
def fwd(p, d, h):
    """his convention: from the close of the report Tuesday to the close h calendar weeks later"""
    i = p.index.searchsorted(d)
    j = p.index.searchsorted(d + pd.Timedelta(weeks=h))
    return p.iloc[j] / p.iloc[i] - 1.0 if j < len(p) else np.nan


def cot_block(k, p):
    x = R.load_cot(k)
    out = {"net": {g: int(x[g].iloc[-1]) for g in G}, "chg": {g: int(x[g].iloc[-1] - x[g].iloc[-2]) for g in G},
           "groups": {}}
    for g, follow in (("retail", -1), ("comm", +1), ("fund", 0)):
        rows = []
        for lb, L in LB.items():
            P = R.pctile(x[g], L)
            cur = float(P.iloc[-1])
            side = "hi" if cur >= R.HI else "lo" if cur <= R.LO else None
            row = {"lb": lb, "pct": round(cur, 1), "side": side, "hist": HIST[lb]}
            if side and follow:
                lit = ((P >= R.HI) if side == "hi" else (P <= R.LO)).to_numpy()
                run = 0
                while run < len(lit) and lit[-1 - run]:
                    run += 1
                sgn = follow * (1 if side == "hi" else -1)
                row.update(weeks_in=run - 1, dir="BULLISH" if sgn > 0 else "BEARISH", h={})
                # his "comparable cases": the extreme counts as a new case only after the group
                # has been at the OPPOSITE extreme since the previous case (a full swing)
                v = P.to_numpy()
                opp = (v <= R.LO) if side == "hi" else (v >= R.HI)
                ons, armed = [], True
                for i in range(len(lit) - run):                 # the live episode has no result yet
                    if lit[i] and not (i and lit[i - 1]):
                        if armed:
                            ons.append(x.index[i])
                            armed = False
                    elif opp[i]:
                        armed = True
                t0 = ASOF - pd.DateOffset(years=HIST[lb])
                row["cases"] = [[str(d.date()), bool(sgn * fwd(p, d, 4) > 0)] for d in ons
                                if t0 <= d < ASOF and np.isfinite(fwd(p, d, 4))]
                for h in HZ:
                    r = np.array([sgn * fwd(p, d, h) for d in ons if t0 <= d < ASOF])
                    r = r[np.isfinite(r)]
                    c = {"n": len(r), "w": int((r > 0).sum()), "avg": round(100 * r.mean(), 2) if len(r) else None,
                         "past": run - 1 > h}
                    c["ok"] = bool(c["n"] >= R.BAR_N and 100 * c["w"] / c["n"] >= R.BAR_WIN and c["avg"] > 0)
                    row["h"][h] = c
            rows.append(row)
        out["groups"][g] = rows
    tail = x.tail(260)
    out["series"] = {"dates": [str(d.date()) for d in tail.index], **{g: [int(v) for v in tail[g]] for g in G}}
    out["bands"] = {g: {lb: [float(np.quantile(x[g].tail(L), .2)), float(np.quantile(x[g].tail(L), .8))]
                        for lb, L in LB.items()} for g in G}
    info = {}
    for g in ("retail", "comm"):
        lit = [r for r in out["groups"][g] if r.get("dir")]
        ds = {r["dir"] for r in lit}
        info[g] = {"lit": len(lit), "dir": ds.pop() if len(ds) == 1 else None,
                   "side": lit[0]["side"] if lit else None,
                   "q": sum(1 for r in lit if r["h"][4]["ok"] or r["h"][8]["ok"])}
    out["fund_lit"] = sum(1 for r in out["groups"]["fund"] if r["side"])
    act = [g for g in info if info[g]["lit"] >= 2 and info[g]["dir"]]      # one lit lookback is not a read
    if not act:
        read, conv, lead = "STAND ASIDE", "None", None
    elif len(act) == 1 or info["retail"]["dir"] == info["comm"]["dir"]:
        read, lead = info[act[0]]["dir"], act
        q = sum(info[g]["q"] for g in act)
        conv = ("High" if q else "Moderate") if len(act) == 2 else ("Moderate" if q else "Weak")
    elif info["retail"]["q"] != info["comm"]["q"]:                          # groups disagree: evidence decides
        w = max(act, key=lambda g: info[g]["q"])
        read, conv, lead = info[w]["dir"], "Weak", [w]
    else:
        read, conv, lead = "STAND ASIDE", "None", None
    best = None
    for g in lead or []:
        for r in out["groups"][g]:
            if r.get("dir") != read:
                continue
            for h, c in r["h"].items():
                if c["ok"]:
                    key = (c["w"] / c["n"], c["n"])
                    if best is None or key > best[0]:
                        best = (key, {"group": g, "lb": r["lb"], "h": h, **c})
    out.update(info=info, read=read, conv=conv, lead=lead, edge=best[1] if best else None)
    return out


# ------------------------------------------------------------------ seasonality
def paths(p):
    """average cumulative % path by trading-day index for the last 5/10/15 years, this year, analog years"""
    by = {y: g.to_numpy() for y, g in p[p.index <= TODAY].groupby(p[p.index <= TODAY].index.year)}
    n = 250
    def path(y):
        v = by[y]
        base = by[y - 1][-1] if y - 1 in by else v[0]
        return 100 * (v / base - 1)
    avg = {}
    for span in (5, 10, 15):
        ys = [path(y)[:n] for y in YEARS[-span:] if len(by[y]) >= n]
        avg[span] = np.mean(ys, axis=0)
    cur = path(TODAY.year)
    m = len(cur)
    def detr(v):
        t = np.arange(len(v))
        return v - np.polyval(np.polyfit(t, v, 1), t)
    shape = float(np.corrcoef(detr(cur), detr(avg[15][:m]))[0, 1])
    an = []
    for y in by:
        if y == TODAY.year or y - 1 not in by or len(by[y]) < n:
            continue
        py = path(y)
        an.append({"y": int(y), "match": round(float(np.corrcoef(detr(cur), detr(py[:m]))[0, 1]), 2),
                   "todate": round(float(py[m - 1]), 1),
                   "rest": round(float(100 * ((1 + py[-1] / 100) / (1 + py[m - 1] / 100) - 1)), 1)})
    an.sort(key=lambda a: -a["match"])
    return {"avg": {str(s): [round(float(v), 2) for v in a[::2]] for s, a in avg.items()},
            "cur": [round(float(v), 2) for v in cur[::2]], "m": m, "n": n, "shape": round(shape, 2), "analogs": an[:4],
            "base": float(by[TODAY.year - 1][-1]) if TODAY.year - 1 in by else float(by[TODAY.year][0]),
            "now": float(by[TODAY.year][-1])}


def season_block(p, cal, used):
    wins, status = used
    out = {"windows": wins, **paths(p), "_cal": cal, "upcoming": cal.upcoming(TODAY)}
    sh = out["shape"]
    out["shape_read"] = ("tracking closely" if sh >= .5 else "loosely tracking" if sh >= .3 else
                         "off-pattern" if sh >= 0 else "counter-seasonal")
    if status == "none":
        out.update(read="NO READ", strength=None)
        return out
    d = wins[0]
    nb = cal.neighbours(TODAY.year, d)
    na = float(np.mean([x["win"] for x in nb]))
    score = round(0.5 * 100 * d["wins"] / 15 + 0.2 * 25 * d["rec"] + 0.3 * na)
    kind = "sharp" if d["len"] <= 15 else "mid-length" if d["len"] <= 32 else "broad"
    timing = ("forgiving" if na >= 75 else "fairly forgiving" if na >= 65 else "tight" if na >= 58 else "very tight")
    out["remaining"] = cal.remaining(TODAY, d)
    out.update(driver=d, neigh=nb, neigh_avg=round(na), score=score, kind=kind, timing=timing,
               strength="STRONG" if score >= 80 else "MODERATE" if score >= 70 else "WEAK",
               read="SELF-CANCELLING" if status == "cancel" else ("BULLISH" if d["side"] == "BUY" else "BEARISH"))
    return out


RESEARCH = os.path.join(ROOT, "data", "research", "conflict.json")


def sector2(k):
    return {"FX": "FX", "Indices": "Indices", "Agriculture": "Agriculture"}.get(M[k][3], "Commodities")


def tested_cells():
    """walk-forward records (research/conflict_test.py) the verdicts are graded with"""
    if not os.path.exists(RESEARCH):
        return None
    r = json.load(open(RESEARCH))
    def agg(rows):
        z = np.array([x["z"] for x in rows])
        return {"n": len(rows), "win": round(100 * float(np.mean([x["r"] > 0 for x in rows])), 1),
                "avg": round(float(np.mean([x["r"] for x in rows])), 2),
                "t": round(float(z.mean() / z.std(ddof=1) * np.sqrt(len(z))), 2)} if len(rows) > 2 else None
    B, A = r["trades_cot"], r["trades_seasonal"]
    cot = {f"{sec}|{g}": agg([x for x in B if sector2(x["m"]) == sec and x["groups"] == g])
           for sec in ("FX", "Commodities", "Indices", "Agriculture") for g in (1, 2)}
    rp = os.path.join(ROOT, "data", "research", "conflict_relevance.json")
    rel = json.load(open(rp))["by_played_out"] if os.path.exists(rp) else {}
    per = {k: {"seas": agg([x for x in A if x["m"] == k]), "cot": agg([x for x in B if x["m"] == k])} for k in M}
    return {"per_asset": per, "relevance": rel, "first_cot": min(x["t"] for x in B), "first_seas": r["first"], "last": r["last"], "cot": cot,
            "cot_all": r["cot"]["all"], "cot_by_seasonal": r["cot"]["by_seasonal"],
            "seas_all": r["seasonal"]["all"], "seas_by_cot": r["seasonal"]["by_cot"],
            "seas_by_sector": r.get("seasonal_by_sector")}


def combine(k, reader, cal, speed=None):
    """the board's verdict (bias/verdict.py board_read). A COT signal the commercials crept into slowly counts as no
    side (tested: research/verdict_test.py with SKIP_SLOW=1 beat keeping them). A calendar window that carries the
    bias alone needs a usual move of at least 3 normal daily moves. Returns the calendar windows it used."""
    v = reader.read(TODAY)
    g = reader.last_groups
    if speed == "slow":
        v = "NEUTRAL"
    verdict, basis, used = VD.board_read(v, cal, TODAY, reader)
    return verdict, basis, g, used


VERDICT = os.path.join(ROOT, "data", "research", "verdict.json")
SECTOR_V = lambda k: {"FX": "Currencies", "Indices": "Indices", "Agriculture": "Agriculture"}.get(M[k][3], "Metals & energy")
MIN_CELL = 40


def confidence(k, basis, speed=None):
    """1-5 dots from the walk-forward record of this verdict type in this asset class (research/verdict_test.py):
    how many standard errors verdicts like this one beat a coin flip by. t < 0: 1, 0-1: 2, 1-2: 3, 2-3: 4, >= 3: 5.
    Falls back to the verdict type across all markets when the asset-class cell has fewer than 40 trades."""
    if basis not in ("COT + calendar", "COT only", "Calendar only", "Calendar over COT") or not os.path.exists(VERDICT):
        return None
    # graded by the verdict type across all markets: finer cells (by asset class or COT speed) did not keep their
    # ranking out of sample (graded on 2019-21, scored on 2022-26), the verdict types did
    r = json.load(open(VERDICT))
    cell, scope = r["by_basis"].get(basis), f"{basis} verdicts across all markets"
    if not cell:
        return None
    t = cell["t"]
    dots = 1 if t < 0 else 2 if t < 1 else 3 if t < 2 else 4 if t < 3 else 5
    return {"dots": dots, "n": cell["n"], "win": cell["win"], "avg": cell["avg"], "t": t, "scope": scope,
            "first": r["first"][:4], "last": r["last"][:4]}


def setup_profile(k, p, cal, reader, s, basis, verdict):
    """the current setup's own cases (as research/focus_test.py ranks them): hit rate, average end move, average best
    and worst move along the way, in % and in units of the market's normal volatility"""
    if verdict not in VD.SIDES:
        return None
    lc = np.log(p.to_numpy(float))
    sig = np.diff(lc)[-252:].std()
    cases = []
    if basis == "COT only":
        lit = R.lit_sides(reader, R.speed_series(k))         # slow signals count as no side, as on the board
        for i in range(len(reader.dates)):
            v = lit[i]
            if v != verdict or (i > 0 and lit[i - 1] == v):
                continue                                   # one case per lit run, from its first report
            ex = R.cot_exit(reader.dates, lit, i)
            if ex is None:
                continue
            rel = reader.dates[i] + pd.Timedelta(days=3)
            a, b = p.index.searchsorted(rel), p.index.searchsorted(ex)
            if b >= len(p) or a < 1 or b <= a:
                continue
            seg = (1 if v == "BULLISH" else -1) * (lc[a:b + 1] - lc[a])
            cases.append((seg[-1], seg.max(), seg.min(), R.COT_REF_DAYS))   # fixed scale: the length depends on the outcome
    else:
        d = s.get("driver")
        if not d:
            return None
        rel = {"COT + calendar": "agree", "Calendar over COT": "against"}.get(basis)
        sg = 1 if d["side"] == "BUY" else -1
        yrs = (s.get("past") or {}).get("years") or []
        for y, info in zip(range(TODAY.year - d.get("ny", 15), TODAY.year), yrs):
            if rel and info["rel"] != rel:
                continue
            a = cal.first[y][0] + d["s"]
            seg = sg * (lc[a:a + d["len"] + 1] - lc[a])
            cases.append((seg[-1], seg.max(), seg.min(), d["len"]))
    if len(cases) < 3:
        return None
    arr = np.array(cases)
    norm = sig * np.sqrt(np.maximum(arr[:, 3], 1))
    pc = lambda v: round(float(100 * (np.exp(v) - 1)), 2)
    return {"n": len(arr), "hit": round(100 * float((arr[:, 0] > 0).mean()), 1),
            "end": pc(arr[:, 0].mean()), "mfe": pc(arr[:, 1].mean()), "mae": pc(arr[:, 2].mean()),
            "end_z": round(float((arr[:, 0] / norm).mean()), 3)}


FOCUS = os.path.join(ROOT, "data", "research", "focus.json")


def focus_picks(res, n=3):
    """this week's focus: verdicts where both engines agree come first, then the biggest usual end move
    (research/focus_test.py: the best of the tested ways to pick a few setups a week)"""
    cand = [(k, m) for k, m in res.items() if m["verdict"] in VD.SIDES and m.get("profile")]
    cand.sort(key=lambda km: (km[1]["basis"] == "COT + calendar", km[1]["profile"]["end_z"]), reverse=True)
    rec = json.load(open(FOCUS)) if os.path.exists(FOCUS) else {}
    return {"keys": [k for k, _ in cand[:n]], "method": rec.get("end move · COT + calendar first"),
            "hit_method": rec.get("hit rate"), "all": rec.get("all verdicts")}


def setup_track(k, p, reader):
    """the current COT picture per lookback (which groups are at which extreme), and every past time since prices start
    that the same picture appeared on that lookback (after 8 weeks without it): result after 4 weeks, and held while the
    picture lasts, out one week after the last report showing it (as the board holds COT), from the first close after
    the Friday release. Direction: follow the commercials if they are at an extreme, else fade retail."""
    i0 = reader.dates.searchsorted(TODAY - pd.Timedelta(days=3), "right") - 1
    lc = np.log(p.to_numpy(float))
    word = {"comm": "Commercials", "retail": "Retail", "fund": "Funds"}
    rows = []
    for lb in R.LB:
        def pic(i):
            out = {}
            for g in ("comm", "retail", "fund"):
                v = reader.P[g][lb][i]
                out[g] = ("hi" if v >= R.HI else "lo" if v <= R.LO else None) if np.isfinite(v) else None
            return out
        now = pic(i0)
        if now["comm"]:
            sg = 1 if now["comm"] == "hi" else -1
        elif now["retail"]:
            sg = -1 if now["retail"] == "hi" else 1
        else:
            continue
        label = " · ".join(f'{word[g]} {"long" if s == "hi" else "short"}' for g, s in now.items() if s)
        res4, res8, last = [], [], -10 ** 6
        same = [pic(j) == now for j in range(len(reader.dates))]
        for j in range(1, i0):
            if pic(j) != now:
                continue
            if j - last <= 8:
                last = j
                continue
            last = j
            rel = reader.dates[j] + pd.Timedelta(days=3)
            a = p.index.searchsorted(rel)
            if rel < p.index[0] or a >= len(p):
                continue
            ex = R.cot_exit(reader.dates, same, j)
            for end, bucket in ((rel + pd.Timedelta(weeks=4), res4), (ex, res8)):
                if end is None:
                    continue
                b = p.index.searchsorted(end)
                if b < len(p) and p.index[b] <= TODAY:
                    bucket.append(100 * (np.exp(sg * (lc[b] - lc[a])) - 1))
        agg = lambda r: {"n": len(r), "w": int(sum(x > 0 for x in r)), "avg": round(float(np.mean(r)), 2)} if r else None
        rows.append({"lb": lb, "label": label, "dir": "BULLISH" if sg > 0 else "BEARISH", "board": bool(now["comm"]),
                     "r4": agg(res4), "r8": agg(res8)})
    return rows


PHASE = {0: "election year", 1: "post-election year", 2: "midterm year", 3: "pre-election year"}


def presidential_cycle(p):
    """context for US indices: where the 4-year presidential cycle stands, the documented 'sweet spot' (1 October of the
    midterm year to 30 June of the pre-election year) in every cycle since prices start, against the same months in all
    other years, and the current cycle year's calendar-year return against the others. Small sample by nature."""
    def stretch(y):
        a = p.index.searchsorted(pd.Timestamp(y, 10, 1))
        b = p.index.searchsorted(pd.Timestamp(y + 1, 6, 30), "right") - 1
        return 100 * float(p.iloc[b] / p.iloc[a] - 1) if 0 < a < b < len(p) and p.index[b] <= TODAY and p.index[b].month == 6 else None
    years = range(p.index[0].year, TODAY.year)
    mid = [(y, round(stretch(y), 1)) for y in years if y % 4 == 2 and stretch(y) is not None]
    other = [stretch(y) for y in years if y % 4 != 2 and stretch(y) is not None]
    cal = {}
    for y in range(p.index[0].year + 1, TODAY.year):
        a = p.index.searchsorted(pd.Timestamp(y, 1, 1)) - 1
        b = p.index.searchsorted(pd.Timestamp(y, 12, 31), "right") - 1
        if a >= 0:
            cal[y] = 100 * float(p.iloc[b] / p.iloc[a] - 1)
    ph = TODAY.year % 4
    same = [round(v, 1) for y, v in cal.items() if y % 4 == ph]
    rest = [v for y, v in cal.items() if y % 4 != ph]
    my = TODAY.year if ph == 2 else TODAY.year - 1 if ph == 3 else None
    status = None
    if my:
        s0, s1 = pd.Timestamp(my, 10, 1), pd.Timestamp(my + 1, 6, 30)
        status = "active" if s0 <= TODAY <= s1 else "upcoming" if TODAY < s0 else None
    return {"phase": PHASE[ph], "year": TODAY.year,
            "sweet": {"cases": mid, "avg": round(float(np.mean([r for _, r in mid])), 1) if mid else None,
                      "up": sum(1 for _, r in mid if r > 0), "other_avg": round(float(np.mean(other)), 1) if other else None,
                      "other_up": sum(1 for o in other if o > 0), "other_n": len(other), "status": status,
                      "start": f"{my}-10-01" if my else None, "end": f"{my + 1}-06-30" if my else None},
            "calendar": {"same": same, "same_avg": round(float(np.mean(same)), 1) if same else None,
                         "rest_avg": round(float(np.mean(rest)), 1) if rest else None}}


def setup_record(k, basis):
    """walk-forward record (research/verdict_test.py) of this verdict type on this market, and on all markets"""
    if basis not in ("COT + calendar", "COT only", "Calendar only", "Calendar over COT") or not os.path.exists(VERDICT):
        return None
    r = json.load(open(VERDICT))
    rows = [x for x in r["trades"] if x["m"] == k and x["basis"] == basis]
    rr = np.array([x["r"] for x in rows])
    here = {"n": len(rr), "w": int((rr > 0).sum()), "avg": round(float(rr.mean()), 2)} if len(rr) else {"n": 0, "w": 0, "avg": None}
    return {"here": here, "all": r["by_basis"].get(basis), "first": r["first"][:4], "last": r["last"][:4]}


def tested_for(k, basis, groups, tested):
    """the walk-forward record of this kind of verdict"""
    if not tested:
        return None
    rec = lambda o, label: dict(o, label=label) if o else None
    if basis == "COT + calendar":
        return rec(tested["cot_by_seasonal"].get("agree"), "COT reads while the calendar agreed won {win}%, held while lit + 1 week")
    if basis == "COT only":
        sec = {"FX": "currency", "Indices": "index", "Agriculture": "agricultural"}.get(sector2(k), "metal and energy")
        return rec(tested["cot"].get(f"{sector2(k)}|{groups}"),
                   f"{sec} COT reads with {'retail and funds' if groups == 2 else 'one group'} against the commercials won {{win}}%, held while lit + 1 week")
    if basis == "Calendar only":
        return rec(tested["seas_by_cot"].get("neutral"), "seasonal windows with no COT side won {win}% to the window end")
    rel = tested.get("relevance") or {}
    if basis == "Calendar over COT":
        return rec(rel.get("played out"), "contradictions where the window had already paid against COT: the calendar won {win}%")
    if basis.startswith("Conflict"):
        return rec(rel.get("did not play out"), "contradictions where the window had not paid against COT: the calendar won {win}%")
    return None


def basis(why):
    return why


CLOSING_DAYS, FLIP_GAP = 7, 15          # trading days


def timing(s):
    """how long the seasonal driver window still runs, and whether an opposite one follows"""
    if not s.get("driver") or s["read"] not in ("BULLISH", "BEARISH"):
        return None
    d = s["driver"]
    end = pd.Timestamp(d["end"])
    left = int(np.busday_count(TODAY.date(), end.date()))
    opp = sorted((w for w in s["windows"][1:] if w["side"] != d["side"]
                  and w["s"] <= d["s"] + d["len"] + FLIP_GAP), key=lambda w: w["start"])
    nxt = opp[0] if opp else None
    return {"end": d["end"], "left": left, "closing": left <= CLOSING_DAYS,
            "flip": {"side": nxt["side"], "start": nxt["start"], "end": nxt["end"], "wins": nxt["wins"]} if nxt else None,
            "only": False}


def cot_record(reader, p, side, k):
    """every past time this market's COT signal switched to `side` (since prices start; slow signals count as no side,
    as on the board), and whether price moved that way while the signal stayed lit, out one week after the last lit
    report (bias/core.py cot_exit), from the first close after the Friday release. The live episode is left out."""
    if side not in ("BULLISH", "BEARISH"):
        return None
    sg = 1 if side == "BULLISH" else -1
    reads = R.lit_sides(reader, R.speed_series(k))
    cases = []
    for i in range(len(reads)):
        if reads[i] == side and (i == 0 or reads[i - 1] != side):
            rel = reader.dates[i] + pd.Timedelta(days=3)
            ex = R.cot_exit(reader.dates, reads, i)
            if rel < p.index[0] or ex is None:
                continue
            a = p.index.searchsorted(rel)
            b = p.index.searchsorted(ex)
            if b >= len(p) or p.index[b] > TODAY or b <= a:
                continue                                   # result not known yet (includes the live episode)
            seg = sg * (p.iloc[a:b + 1].to_numpy() / p.iloc[a] - 1)
            cases.append({"d": str(reader.dates[i].date()), "r": round(100 * float(seg[-1]), 2), "weeks": round((b - a) / 5, 1),
                          "mfe": round(100 * float(seg.max()), 2), "mae": round(100 * float(seg.min()), 2)})
    if not cases:
        return None
    r = np.array([c["r"] for c in cases])
    # the live signal: when the read switched to `side`, and what price has done since the first close after its release
    i0 = reader.dates.searchsorted(TODAY - pd.Timedelta(days=3), "right") - 1
    live = None
    if 0 <= i0 < len(reads) and reads[i0] == side:
        j = R.lit_start(reads, i0)
        rel = reader.dates[j] + pd.Timedelta(days=3)
        a = p.index.searchsorted(rel)
        if a < len(p):
            live = {"since": str(reader.dates[j].date()), "entry": str(p.index[a].date()),
                    "move": round(100 * sg * float(p.iloc[-1] / p.iloc[a] - 1), 2),
                    "weeks": round(float((p.index[-1] - p.index[a]).days) / 7, 1)}
    return {"n": len(r), "w": int((r > 0).sum()), "avg": round(float(r.mean()), 2), "median": round(float(np.median(r)), 2),
            "mfe": round(float(np.mean([c["mfe"] for c in cases])), 2), "mae": round(float(np.mean([c["mae"] for c in cases])), 2),
            "weeks": round(float(np.mean([c["weeks"] for c in cases])), 1), "after": R.HOLD_AFTER,
            "rec": int((r[-4:] > 0).sum()), "first": cases[0]["d"][:4], "cases": cases, "live": live}


def move_done(c, s, basis):
    """has the running setup already made its usual move? COT: move since the signal's entry against the average end
    move of all past cases of this signal (in-sample record); calendar: move since the window start this year against
    the window's 15-year average move. Tested (research/move_done_test.py): calendar windows that had already made
    their usual move earned nothing from there on; COT setups still earned a little, less than ones not there yet."""
    out = {}
    rc = c.get("record") or {}
    lv = rc.get("live")
    if lv and rc.get("avg") is not None:
        out["cot"] = _done_state(lv["move"], rc["avg"], rc.get("mfe"))
    d, r = s.get("driver"), s.get("remaining")
    if d and r and r.get("started") and r.get("so_far") is not None:
        sg = 1 if d["side"] == "BUY" else -1
        out["seas"] = _done_state(sg * r["so_far"], sg * d["avg"], None)
    lead = {"COT only": ["cot"], "COT + calendar": ["cot", "seas"], "Calendar only": ["seas"],
            "Calendar over COT": ["seas"]}.get(basis, [])
    out["flag"] = any(out.get(e, {}).get("state") == "done" for e in lead)
    return out


def _done_state(so_far, usual, best):
    so_far, usual = round(float(so_far), 2), round(float(usual), 2)
    if usual <= 0:
        state = "no positive usual move"
    else:
        state = "done" if so_far >= usual else "against" if so_far < 0 else "not yet"
    return {"so_far": so_far, "usual": usual, "share": round(100 * so_far / usual) if usual > 0 else None,
            "beyond_best": bool(best is not None and best > 0 and so_far >= best), "state": state}


def cot_speed(k, reader, side):
    """how fast the commercials moved into their extreme: their 4-week net change before the latest released report,
    in units of a typical 4-week change (3-year standard deviation), with the tested record of that speed third
    (research/cot_speed_test.py)"""
    sp = os.path.join(ROOT, "data", "research", "cot_speed.json")
    if side not in ("BULLISH", "BEARISH") or not os.path.exists(sp):
        return None
    r = json.load(open(sp))["move4w"]
    x = R.load_cot(k)
    i = reader.dates.searchsorted(TODAY - pd.Timedelta(days=3), "right") - 1
    d4 = x["comm"].diff(4)
    sd = d4.rolling(156, min_periods=52).std().shift(1).iloc[i]
    if not np.isfinite(sd) or sd <= 0:
        return None
    mv = (1 if side == "BULLISH" else -1) * float(d4.iloc[i] / sd)
    lo, hi = r["cutoffs"]
    speed = "fast" if mv > hi else "slow" if mv <= lo else "medium"
    return {"move": round(mv, 2), "speed": speed, "all": r["2003-26"][speed], "recent": r["2016-26"][speed],
            "slow_all": r["2003-26"]["slow"], "fast_all": r["2003-26"]["fast"]}


def past_years(k, s, reader, p):
    """for the current driver window: each of its 15 past years, COT at its start and whether it paid.
    These are the years the window was picked from."""
    d = s.get("driver")
    if not d:
        return None
    return s["_cal"].past(TODAY.year, d, reader)


def R_YEARS():
    return YEARS


def timing_html(t, long=False):
    if not t:
        return ""
    txt = f'Window ends {dm(t["end"])}, {t["left"]} days left'
    if t["flip"]:
        f = t["flip"]
        txt += f'; {f["side"].lower()} window from {dm(f["start"])} ({f["wins"]} of 15)'
    cls = "warn hot" if t["closing"] and t["flip"] else "warn" if (t["closing"] or t["flip"]) else "warn calm"
    if long:
        msg = "Seasonal context: " + txt + "."
        if t["closing"] and t["flip"]:
            msg += " The window is about to close and the calendar then turns the other way."
        elif t["flip"]:
            msg += " An opposite window follows, so diarise the turn."
        elif t["closing"]:
            msg += " Little time is left on this window."
        return f'<p class="{cls} banner">{msg}</p>'
    return f'<span class="{cls}">{txt}</span>'


# ------------------------------------------------------------------ render
def tag(v, big=False):
    cls = {"BULLISH": "bull", "BEARISH": "bear", "BUY": "bull", "SELL": "bear"}.get(v, "flat")
    return f'<span class="tag {cls}{" big" if big else ""}">{html.escape(v.title())}</span>'


def dm(s):
    return pd.Timestamp(s).strftime("%d %b")


def ordn(x):
    return f"{x:.1f}"


def cot_html(m):
    c = m["cot"]
    I = c["info"]
    def panel(g, rule):
        i = I[g]
        if not i["lit"]:
            st, arrow = "not extreme", "no extreme"
        else:
            st = ("LONG" if i["side"] == "hi" else "SHORT") + " extreme"
            arrow = (i["dir"] or "mixed").lower()
        cells = "".join(f'<td class="p {r["side"] or ""}">{ordn(r["pct"])}</td>' for r in reversed(c["groups"][g]))
        return (f'<tr><th scope="row">{G[g]}<small>{i["lit"]} of 5 lookbacks · {st}</small></th>{cells}'
                f'<td class="rule">{rule} → {arrow}</td></tr>')
    fund = "".join(f'<td class="p {r["side"] or ""}">{ordn(r["pct"])}</td>' for r in reversed(c["groups"]["fund"]))
    grid = ('<div class="scroll"><table class="grid"><thead><tr><th>Percentile of net position</th>'
            + "".join(f"<th>{x}</th>" for x in reversed(list(LB))) + "<th>Rule</th></tr></thead><tbody>"
            + panel("retail", "Fade the crowd") + panel("comm", "Follow the smart money")
            + f'<tr><th scope="row">Funds<small>{c["fund_lit"]} of 5 lookbacks · context only</small></th>{fund}<td class="rule">counterparty</td></tr>'
            + "</tbody></table></div>")
    def track(h):
        rows = []
        for g, lab in (("retail", "Retail · fade"), ("comm", "Commercials · follow")):
            for r in c["groups"][g]:
                if not r.get("dir"):
                    continue
                x = r["h"][h]
                st = "past" if x["past"] else "live"
                res = (f'<td class="num">{round(100 * x["w"] / x["n"])}%</td><td class="num">{x["w"]} of {x["n"]}</td>'
                       f'<td class="num">{x["avg"]:+.2f}%</td>') if x["n"] else '<td colspan="3" class="mute">no comparable cases</td>'
                rows.append(f'<tr class="{"ok" if x["ok"] else ""}"><th scope="row">{lab} · {r["lb"]}</th>'
                            f'<td><span class="st {st}">{st}</span> {r["weeks_in"]}w</td>{res}<td class="num mute">{r["hist"]} yrs</td></tr>')
        if not rows:
            return ""
        return (f'<h4>Track record · {HZ[h]} result</h4><div class="scroll"><table class="track"><thead><tr><th>Lookback</th>'
                '<th>Weeks in</th><th>Win rate</th><th>Cases</th><th>Avg</th><th>History</th></tr></thead><tbody>'
                + "".join(rows) + "</tbody></table></div>")
    e = c["edge"]
    if c["read"] == "STAND ASIDE":
        lit = I["retail"]["lit"] + I["comm"]["lit"]
        lead = ("Nothing is at an extreme on either side, so there is no setup to measure." if not lit else
                "Retail and commercials point opposite ways on similar evidence. No side from positioning." if
                I["retail"]["lit"] >= 2 and I["comm"]["lit"] >= 2 else
                "Positioning is stretched on one lookback only. One lit lookback is not a read. No side from positioning.")
        ef = "The positioning read is neutral this week, so there is no direction to test."
    else:
        who = "commercials, with " + ("retail and funds" if m.get("groups") == 2 else "retail or funds") + " at the opposite extreme"
        act = "buy" if c["read"] == "BULLISH" else "sell"
        lead = (f'The read rests on {who}. '
                f'We are looking to {act}. Conviction: {c["conv"].lower()}.')
        ef = (f'The strongest read is the {e["lb"].lower()} lookback on {G[e["group"]].lower()}: {round(100 * e["w"] / e["n"])}% over '
              f'{HZ[e["h"]]}, {e["w"]} of {e["n"]} cases, {e["avg"]:+.2f}% average move.' if e else
              f'Nothing in {m["name"]} clears the bar this week (six cases, 60%, positive average). Treat the bias as directional context, not as a tested edge.')
    nets = " · ".join(f'{G[g]} {c["net"][g]:+,} ({c["chg"][g]:+,})' for g in G)
    return (f'<div class="step"><div class="sh"><h4>Step 1 · Bias from COT</h4>{tag(c["read"])}</div><p>{lead}</p>{grid}'
            f'<p class="cap">Net contracts and week change: {nets}. Lit at the 80th percentile and above or the 20th and below.</p>'
            f'{track(4)}{track(8)}<p class="ef"><b>Edge Finder.</b> {ef}</p></div>')


def svg_map(s):
    W, H, pad = 640, 190, 28
    series = [s["avg"]["15"], s["avg"]["10"], s["avg"]["5"], s["cur"]]
    lo = min(min(v) for v in series)
    hi = max(max(v) for v in series)
    n = len(s["avg"]["15"])
    X = lambda i: pad + (W - 2 * pad) * i / (n - 1)
    Y = lambda v: H - 18 - (H - 30) * (v - lo) / (hi - lo or 1)
    line = lambda v, cls: f'<polyline class="{cls}" fill="none" points="' + " ".join(f"{X(i):.1f},{Y(x):.1f}" for i, x in enumerate(v)) + '"/>'
    months = "".join(f'<text x="{X(i * (n - 1) / 12 + (n - 1) / 24):.0f}" y="{H - 3}" text-anchor="middle">{mm}</text>'
                     for i, mm in enumerate("JFMAMJJASOND"))
    band = ""
    if s.get("driver"):
        d = s["driver"]
        f = lambda t: X((pd.Timestamp(t).dayofyear - 1) / 365 * (n - 1))
        x0, x1 = f(d["start"]), min(f(d["end"]) if pd.Timestamp(d["end"]).year == TODAY.year else X(n - 1), X(n - 1))
        band = f'<rect class="band {"b" if d["side"] == "BUY" else "s"}" x="{x0:.1f}" y="6" width="{max(x1 - x0, 2):.1f}" height="{H - 24}"/>'
    xt = X(len(s["cur"]) - 1)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Seasonal map">{band}'
            f'<line class="zero" x1="{pad}" x2="{W - pad}" y1="{Y(0):.1f}" y2="{Y(0):.1f}"/>'
            f'<line class="now" x1="{xt:.1f}" x2="{xt:.1f}" y1="6" y2="{H - 18}"/>'
            + line(s["avg"]["15"], "a15") + line(s["avg"]["10"], "a10") + line(s["avg"]["5"], "a5") + line(s["cur"], "cur")
            + f'<g class="ax">{months}<text x="{pad - 4}" y="{Y(hi) + 4:.0f}" text-anchor="end">{hi:+.0f}%</text>'
              f'<text x="{pad - 4}" y="{Y(lo) + 4:.0f}" text-anchor="end">{lo:+.0f}%</text></g></svg>'
            '<p class="cap key"><i class="k a5"></i>5-year <i class="k a10"></i>10-year <i class="k a15"></i>15-year average path '
            f'<i class="k cur"></i>{TODAY.year} · shaded: driver window · dashed: today</p>')


def season_html(m):
    s = m["seas"]
    head = f'<div class="sh"><h4>Seasonality · add-on to the COT read</h4>{tag(s["read"])}</div>'
    shape = f'Whole-year shape match <span class="num">{s["shape"]:+.2f}</span>, {s["shape_read"]}.'
    an = "".join(f'<tr><th scope="row">{a["y"]}</th><td class="num">{a["match"]:+.2f}</td><td class="num">{a["todate"]:+.1f}%</td>'
                 f'<td class="num">{a["rest"]:+.1f}%</td></tr>' for a in s["analogs"])
    up = sum(1 for a in s["analogs"] if a["rest"] > 0)
    avg = np.mean([a["rest"] for a in s["analogs"]])
    analog = ('<h4>The years most like this one</h4><div class="scroll"><table class="track"><thead><tr><th>Year</th><th>Match</th>'
              f'<th>To date</th><th>Rest of year</th></tr></thead><tbody>{an}</tbody></table></div>'
              f'<p class="cap">{up} of {len(s["analogs"])} went higher from here, averaging {avg:+.1f}%. A cross-check on a small sample, not a forecast.</p>')
    if not s.get("driver"):
        return (f'<div class="step">{head}<p>No seasonal window opens in the −2 to +8 week horizon. Seasonality adds nothing this week, '
                f'the COT read carries the bias alone.</p>{svg_map(s)}<p class="cap">{shape}</p>{analog}</div>')
    d = s["driver"]
    rows = "".join(
        f'<tr><th scope="row">{dm(w["start"])}{" <span class=\"st live\">driver</span>" if i == 0 else ""}</th><td>{tag(w["side"])}</td>'
        f'<td>{dm(w["start"])} – {dm(w["end"])}</td><td class="num">{w["len"]} td</td><td class="num">{round(100 * w["wins"] / 15)}%</td>'
        f'<td class="num">{w["wins"]} of 15</td><td class="num">{w["avg"]:+.1f}%</td><td class="num">{w["rec"]}/4</td></tr>'
        for i, w in enumerate(s["windows"]))
    nb = "".join(f'<div><b>{x["win"]}%</b><span>{x["shift"]:+d}d</span></div>' for x in s["neigh"])
    if s["read"] == "SELF-CANCELLING":
        lead = "Two windows open within days of each other and point opposite ways on similar records. Seasonality has nothing to add this week."
    else:
        lead = (f'Seasonality points {s["read"].lower()} on a {s["kind"]} window ({dm(d["start"])} – {dm(d["end"])}). It closed in its direction '
                f'{round(100 * d["wins"] / 15)}% of the last 15 years and has hit {d["rec"]} of its last 4, for an average of {d["avg"]:+.1f}%. '
                f'Edge: {s["strength"]} · timing {s["timing"]}.')
    return (f'<div class="step">{head}<p>{lead}</p>{svg_map(s)}<p class="cap">{shape}</p>'
            '<h4>Windows in play · entry −2 to +8 weeks</h4><div class="scroll"><table class="track"><thead><tr><th>Entry</th><th>Trade</th>'
            f'<th>Window</th><th>Length</th><th>Win</th><th>Cases</th><th>Avg</th><th>Recent</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<h4>The neighbour test · same window, shifted</h4><div class="nb">{nb}<div class="tot"><b>{s["neigh_avg"]}%</b><span>average · {s["timing"]}</span></div></div>'
            f'<p class="cap">Seasonal score {s["score"]}. Win counts are measured after removing each year\'s trend, on spot prices.</p>{analog}</div>')


def combined_html(m):
    c, s = m["cot"], m["seas"]
    sc = (f'{s["strength"].title()} · {s["kind"]} window' if s["read"] in ("BULLISH", "BEARISH") else
          ("Windows disagree" if s["read"] == "SELF-CANCELLING" else "None"))
    act = {"BULLISH": "We look to buy in Demand only, and only when price reaches a fresh zone.",
           "BEARISH": "We look to sell in Supply only, and only when price reaches a fresh zone.",
           "STAND ASIDE": "No side this week. Wait."}[m["verdict"]]
    return (f'<div class="comb"><div class="eng"><div><small>COT positioning</small>{tag("NEUTRAL" if c["read"] == "STAND ASIDE" else c["read"])}'
            f'<small>Conviction: {c["conv"]}</small></div><div><small>Seasonality</small>{tag(s["read"])}<small>Conviction: {sc}</small></div>'
            f'<div class="v"><small>Combined verdict</small>{tag(m["verdict"], True)}<small>{m["basis"]}</small></div></div>'
            f'<p>{act} A bias is not a trade.</p>{tested_line(m)}</div>')


def tested_line(m):
    t = m.get("tested")
    if not t:
        return '<p class="cap">No side, so there is no tested record to quote.</p>'
    return (f'<p class="cap">Tested walk-forward: {t["label"].format(win=t["win"])}, {t["n"]} trades, '
            f'average {t["avg"]:+.2f}% (t {t["t"]:.1f}).</p>')


def render(res):
    order = sorted(res, key=lambda k: -(res[k]["seas"].get("score") or 0))
    best = "".join(
        (lambda m, d: f'<tr><th scope="row">{m["name"]}</th><td>{tag(d["side"])}</td><td>{dm(d["start"])} – {dm(d["end"])}</td>'
                      f'<td class="num">{d["len"]} td · {m["seas"]["kind"]}</td><td class="num">{round(100 * d["wins"] / 15)}%</td>'
                      f'<td class="num">{d["wins"]} of 15</td><td>{m["seas"]["strength"].title()}</td><td class="num">{m["seas"]["shape"]:+.2f} <span class="mute">{m["seas"]["shape_read"]}</span></td></tr>')(res[k], res[k]["seas"]["driver"])
        if res[k]["seas"].get("driver") else
        f'<tr><th scope="row">{res[k]["name"]}</th><td colspan="6" class="mute">no window in the −2/+8 week horizon</td>'
        f'<td class="num">{res[k]["seas"]["shape"]:+.2f} <span class="mute">{res[k]["seas"]["shape_read"]}</span></td></tr>' for k in order)
    over = "".join(
        f'<tr><th scope="row"><a href="#{k}">{m["name"]}</a><small>{k} · {m["sector"]}</small></th>'
        f'<td>{tag("NEUTRAL" if m["cot"]["read"] == "STAND ASIDE" else m["cot"]["read"])}<small>{m["cot"]["conv"]}</small></td>'
        f'<td class="num">{m["cot"]["info"]["retail"]["lit"]} · {m["cot"]["info"]["comm"]["lit"]} · {m["cot"]["fund_lit"]}</td>'
        f'<td>{tag(m["seas"]["read"])}<small>{(m["seas"]["strength"] or "–").title()}</small></td><td>{tag(m["verdict"])}<small>{m["basis"]}</small>{timing_html(m["timing"])}</td>'
        f'</tr>' for k, m in res.items())
    sheets = "".join(
        f'<section class="mkt" id="{k}"><header><h3>{m["name"]} <small>{k} · {m["sector"]}</small></h3><div class="hv"><small>{m["basis"]}</small>{tag(m["verdict"], True)}</div></header>{timing_html(m["timing"], True)}'
        f'<div class="cols">{cot_html(m)}{season_html(m)}</div>{combined_html(m)}</section>' for k, m in res.items())
    return f"""<title>Weekly Market Outlook</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Serif:wght@500&display=swap">
<style>
/* layout: overview ledgers on top, then one sheet per market: COT left, seasonality right, verdict bar below */
:root {{
  --bg:#f6f7f5; --panel:#ffffff; --ink:#1b2422; --mute:#66706c; --line:#d9ddd8;
  --bull:#1f6f4f; --bull-bg:#dcefe4; --bear:#a2362e; --bear-bg:#f6dedb; --flat-bg:#e9ebe7; --mark:#8a6a12; --mark-bg:#f3e8c4;
  --c5:#b9c2be; --c10:#8d9994; --c15:#5c6a65;
  --sans:"IBM Plex Sans",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,monospace; --serif:"IBM Plex Serif",Georgia,serif;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#131817; --panel:#1b2221; --ink:#e4e9e6; --mute:#95a09b; --line:#2e3836;
  --bull:#7fd0a6; --bull-bg:#1d3a2e; --bear:#f09a90; --bear-bg:#442320; --flat-bg:#2a3231; --mark:#e2c56a; --mark-bg:#3d3414;
  --c5:#4a5753; --c10:#6d7b76; --c15:#9aa7a2; color-scheme:dark }} }}
:root[data-theme="dark"] {{
  --bg:#131817; --panel:#1b2221; --ink:#e4e9e6; --mute:#95a09b; --line:#2e3836;
  --bull:#7fd0a6; --bull-bg:#1d3a2e; --bear:#f09a90; --bear-bg:#442320; --flat-bg:#2a3231; --mark:#e2c56a; --mark-bg:#3d3414;
  --c5:#4a5753; --c10:#6d7b76; --c15:#9aa7a2; color-scheme:dark }}
body {{ background:var(--bg); color:var(--ink); font:15px/1.55 var(--sans); padding-inline:20px; padding-block:36px 64px }}
main {{ max-width:1240px; margin-inline:auto; display:flex; flex-direction:column; gap:36px }}
h1 {{ font:500 30px/1.2 var(--serif); margin:0 }} h2 {{ font:500 21px/1.3 var(--serif); margin:0 0 12px }}
h3 {{ font:600 18px/1.3 var(--sans); margin:0 }} h3 small {{ display:inline; margin-left:6px }}
h4 {{ font:600 11px/1.3 var(--sans); letter-spacing:.07em; text-transform:uppercase; color:var(--mute); margin:18px 0 8px }}
p {{ margin:0 0 10px }} .lede {{ max-width:70ch; color:var(--mute); margin-top:8px }}
a {{ color:inherit }} a:focus-visible {{ outline:2px solid var(--mark); outline-offset:2px }}
small {{ display:block; font-size:11.5px; color:var(--mute); font-weight:400 }}
.num, td.p {{ font-family:var(--mono); font-variant-numeric:tabular-nums; font-size:13px }}
.mute {{ color:var(--mute) }} .cap {{ font-size:12px; color:var(--mute) }}
.ledger .num, .track .num {{ white-space:nowrap }}
.scroll {{ overflow-x:auto }}
table {{ border-collapse:collapse; width:100% }}
th, td {{ text-align:left; padding:6px 9px; border-bottom:1px solid var(--line); vertical-align:top }}
thead th {{ font:600 11px/1.3 var(--sans); letter-spacing:.05em; text-transform:uppercase; color:var(--mute); white-space:nowrap }}
tbody th {{ font-weight:500 }}
.ledger {{ background:var(--panel); border:1px solid var(--line); min-width:720px }}
.pair {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.25fr); gap:24px }} .pair > div {{ min-width:0 }}
.tag {{ display:inline-block; font:500 12px/1 var(--sans); padding:4px 7px; border-radius:3px; white-space:nowrap }}
.tag.big {{ font-size:14px; padding:7px 11px; font-weight:600 }}
.tag.bull {{ background:var(--bull-bg); color:var(--bull) }} .tag.bear {{ background:var(--bear-bg); color:var(--bear) }}
.tag.flat {{ background:var(--flat-bg); color:var(--mute) }}
.st {{ font:500 10.5px/1 var(--sans); padding:2px 5px; border-radius:2px; background:var(--flat-bg); color:var(--mute) }}
.st.live {{ background:var(--mark-bg); color:var(--mark) }}
.mkt {{ background:var(--panel); border:1px solid var(--line); padding:20px 22px }}
.mkt > header {{ display:flex; flex-wrap:wrap; justify-content:space-between; gap:10px; align-items:center; padding-bottom:12px; border-bottom:1px solid var(--line) }}
.cols {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:32px; margin-top:16px }} .cols > div {{ min-width:0 }}
@media (max-width:900px) {{ .cols, .pair {{ grid-template-columns:minmax(0,1fr) }} }}
.sh {{ display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:8px }} .sh h4 {{ margin:0 }}
.grid td.p {{ text-align:right }} .grid thead th:not(:first-child) {{ text-align:right }} .grid td.rule {{ font-size:12px; color:var(--mute); text-align:right }}
td.p.hi {{ background:var(--bull-bg); color:var(--bull) }} td.p.lo {{ background:var(--bear-bg); color:var(--bear) }}
.track tr.ok td, .track tr.ok th {{ background:var(--mark-bg) }}
.ef {{ border-left:3px solid var(--mark); padding-left:10px; margin-top:14px }}
svg {{ width:100%; height:auto; display:block; margin-top:6px }}
svg polyline {{ stroke-width:1.5 }} .a5 {{ stroke:var(--c5) }} .a10 {{ stroke:var(--c10) }} .a15 {{ stroke:var(--c15) }}
svg .cur {{ stroke:var(--ink); stroke-width:2.2 }} svg .zero {{ stroke:var(--line) }} svg .now {{ stroke:var(--mute); stroke-dasharray:3 3 }}
svg .band.b {{ fill:var(--bull-bg) }} svg .band.s {{ fill:var(--bear-bg) }} svg .ax text {{ fill:var(--mute); font:10px var(--mono) }}
.key .k {{ display:inline-block; width:14px; height:3px; vertical-align:middle; margin:0 4px 0 8px }} .key .k:first-child {{ margin-left:0 }}
.k.a5 {{ background:var(--c5) }} .k.a10 {{ background:var(--c10) }} .k.a15 {{ background:var(--c15) }} .k.cur {{ background:var(--ink) }}
.nb {{ display:flex; flex-wrap:wrap; gap:1px; background:var(--line); border:1px solid var(--line) }}
.nb div {{ background:var(--panel); padding:8px 12px; flex:1 1 70px }} .nb b {{ display:block; font:500 16px var(--mono) }} .nb span {{ font-size:11.5px; color:var(--mute) }}
.nb .tot {{ flex:2 1 150px; background:var(--flat-bg) }}
.comb {{ margin-top:20px; padding-top:16px; border-top:1px solid var(--line) }}
.eng {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:16px; margin-bottom:12px }}
.eng small {{ margin:4px 0 }} .eng .v {{ border-left:3px solid var(--ink); padding-left:14px }}
.sheets {{ display:flex; flex-direction:column; gap:18px }}
.warn {{ display:block; margin-top:5px; font-size:11.5px; line-height:1.35; padding:3px 6px; border-radius:3px; background:var(--flat-bg); color:var(--mute) }}
.warn.calm {{ background:transparent; padding-left:0 }}
.warn:not(.calm) {{ background:var(--mark-bg); color:var(--mark) }}
.warn.hot {{ background:var(--bear-bg); color:var(--bear); font-weight:500 }}
.warn.banner {{ font-size:13.5px; padding:9px 12px; margin:14px 0 0 }}
.hv {{ display:flex; align-items:center; gap:10px }} .hv small {{ font-size:12.5px }}
</style>
<main>
<header>
  <p class="cap"><a href="index.html">← Bias Board</a></p>
  <h1>Weekly Market Outlook</h1>
  <p class="lede">Commodities and currencies · week of {TODAY.strftime("%d %B %Y")} · COT as of Tuesday {ASOF.date()} · bias from positioning, seasonality as the add-on. Zones are not part of this edition.</p>
</header>
<section class="pair">
  <div><h2>Combined bias</h2><div class="scroll"><table class="ledger" style="min-width:520px"><thead><tr><th>Market</th><th>COT</th><th>Lit R · C · F</th><th>Seasonality</th><th>Verdict</th></tr></thead><tbody>{over}</tbody></table></div>
  <p class="cap">Each engine can carry the bias alone. When COT and the calendar contradict each other, the calendar stands if the window already paid in past years when COT was against it; otherwise there is no bias. Under each verdict: what it rests on and, where a seasonal window is open, when it ends. Amber: the window ends within {CLOSING_DAYS} trading days or an opposite window follows within {FLIP_GAP} trading days; red: both. Lit R · C · F: how many of the five lookbacks are at an extreme for retail, commercials and funds.</p></div>
  <div><h2>Best seasonal windows in play</h2><div class="scroll"><table class="ledger" style="min-width:640px"><thead><tr><th>Market</th><th>Trade</th><th>Window</th><th>Length</th><th>Win</th><th>Cases</th><th>Strength</th><th>Shape scan</th></tr></thead><tbody>{best}</tbody></table></div>
  <p class="cap">Entry within −2 to +8 weeks, 15-year basis, windows of 5 to 30 trading days. Shape scan: how closely {TODAY.year} tracks the market's own seasonal path.</p></div>
</section>
<section><h2>Market by market</h2><div class="sheets">{sheets}</div></section>
<p class="cap">Positioning: CFTC legacy report via LSE, CFTC history before 2015 and for WTI and natural gas. Prices: LSE daily spot; yen, franc and Canadian dollar shown in futures direction; dollar index rebuilt from its six legs. A track-record case is an extreme reached after the group was last at the opposite extreme, measured from the report Tuesday's close. Educational content, not advice.</p>
</main>
"""


if __name__ == "__main__":
    res = {}
    tested = tested_cells()
    for k, m in M.items():
        p = R.load_px(k)
        c = cot_block(k, p)
        reader = R.CotReader(k)
        cal0 = SS.Calendar(p)
        spd0 = cot_speed(k, reader, reader.read(TODAY))
        v, why, groups, used = combine(k, reader, cal0, spd0["speed"] if spd0 else None)
        s = season_block(p, cal0, used)
        s["past"] = past_years(k, s, reader, p)
        cr = reader.read(TODAY)
        c["index_short_skipped"] = reader.skipped_short     # bearish index COT, not used (research/cot_indices_test.py)
        c["read"] = cr if cr in ("BULLISH", "BEARISH") else "STAND ASIDE"   # the tested read, not the untested tie-breaks
        c["record"] = cot_record(reader, p, cr, k)
        c["speed"] = cot_speed(k, reader, cr)
        c["track"] = setup_track(k, p, reader)
        c["conv"] = {2: "vs retail & funds", 1: "vs one group"}.get(groups, "None") if c["read"] != "STAND ASIDE" else "None"
        cal_obj = s.pop("_cal", None)
        res[k] = {"name": m[0], "sector": m[3], "cot": c, "seas": s, "verdict": v, "lineup": why,

                  "basis": why, "groups": groups, "timing": timing(s),
                  "confidence": None, "setup": setup_record(k, why),
                  "profile": setup_profile(k, p, cal_obj, reader, s, why, v),
                  "cycle": presidential_cycle(p) if k in ("ES", "NQ", "YM") else None,
                  "done": move_done(c, s, why),
                  "tested": tested_for(k, why, groups, tested)}
        d = s.get("driver")
        print(f"{k:3s} COT {c['read']:11s} {c['conv']:8s} | seas {s['read']:15s} "
              + (f"{d['side']} {d['start'][5:]}..{d['end'][5:]} {d['wins']}/15 {d['avg']:+.1f}% {s['strength']} nb{s['neigh_avg']}" if d else "")
              + f" shape {s['shape']:+.2f} | {v}")
    focus = focus_picks(res)
    quant = []
    for kind, ks in EV.MARKETS.items():
        for k in ks:
            if k in M:
                quant.append({"id": f"{kind}-{k}", "market": k, "market_name": M[k][0], **EV.strategy(R.load_px(k), kind, TODAY)})
    vt = json.load(open(VERDICT)) if os.path.exists(VERDICT) else None
    vsum = {k2: vt[k2] for k2 in ("first", "last", "all", "by_basis", "by_cell", "by_sector")} if vt else None
    mdp = os.path.join(ROOT, "data", "research", "move_done.json")
    md_test = json.load(open(mdp)) if os.path.exists(mdp) else None
    json.dump({"asof": str(ASOF.date()), "today": str(TODAY.date()), "tested": tested, "verdict_test": vsum, "focus": focus,
               "move_done_test": md_test,
               "markets": res, "quant": quant},
              open(f"{ROOT}/data/live/outlook.json", "w"), indent=1, default=float)
    os.makedirs(f"{ROOT}/site", exist_ok=True)
    out = f"{ROOT}/site/outlook.html"
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">')
    open(out, "w").write(head + render(res) + "</html>")
    print(out)
