"""Live track record: the board's verdicts as they were given, scored once their exit has passed.

record()  on the scheduled Saturday run (TRACK=1): every market with a bias and no open tracked verdict gets a new
          entry, the way the walk-forward test trades (one position per market): entry at the first close after
          that Saturday (calendar-led: not before the window start), exit at the window end (calendar-led) or one
          week after the COT signal goes dark (COT-led, known only later).
score()   on every build: results from the saved entries and current prices; nothing but the entries is stored.
Saved in data/track/verdicts.json (in the repo, committed by the weekly workflow)."""
import json, os
import numpy as np, pandas as pd

import core as R
import verdict as VD

FILE = os.environ.get("TRACK_FILE") or os.path.join(R.ROOT, "data", "track", "verdicts.json")


def load():
    return json.load(open(FILE)) if os.path.exists(FILE) else []


def _exit(e):
    """planned exit date of an entry, or None if not known yet"""
    if VD.horizon(e["basis"]) == "window":
        return pd.Timestamp(e["window_end"])
    rd = R.CotReader(e["m"])
    lit = R.lit_sides(rd, R.speed_series(e["m"]))
    i = rd.dates.searchsorted(pd.Timestamp(e["report"]), "right") - 1
    if i < 0 or lit[i] != e["verdict"]:
        # the signal on the report the verdict used is not in the board's list (rule changed since): hold 1 week
        return pd.Timestamp(e["report"]) + pd.Timedelta(days=10)
    return R.cot_exit(rd.dates, lit, i)


def score(entries, today):
    """each entry with its status (open / done) and price move so far or at the exit"""
    out, px = [], {}
    for e in entries:
        p = px.setdefault(e["m"], R.load_px(e["m"]))
        p = p[p.index <= today]
        a = p.index.searchsorted(pd.Timestamp(e["entry_from"]))
        row = dict(e)
        if a >= len(p):
            row.update(status="waiting")
            out.append(row)
            continue
        ex = _exit(e)
        b = p.index.searchsorted(ex) if ex is not None else len(p)
        done = ex is not None and b < len(p)
        j = b if done else len(p) - 1
        move = 100 * float(p.iloc[j] / p.iloc[a] - 1)
        sg = 1 if e["verdict"] == "BULLISH" else -1
        # as a technical trader would hold it (research/cot_hold_test.py): best point along the way, and the result
        # in R with a stop one normal week against the entry (one week's usual move before the entry), else the exit
        x = p.to_numpy(float)
        path = sg * (x[a:j + 1] / x[a] - 1) * 100
        wk = float(np.std(np.diff(np.log(x[max(0, a - 252):a]))) * 100 * np.sqrt(5)) if a > 20 else None
        stopped = bool(wk and (path <= -wk).any())
        row.update(status="done" if done else "open", entry=str(p.index[a].date()), exit=str(p.index[j].date()),
                   move=round(move, 2), right=bool(sg * move > 0), best=round(float(path.max()), 2),
                   week_pct=round(wk, 2) if wk else None, stopped=stopped,
                   R=(-1.0 if stopped else round(float(path[-1]) / wk, 2)) if wk else None)
        out.append(row)
    return out


def record(res, today, asof):
    """add this Saturday's new verdicts (one open entry per market at a time)"""
    entries = load()
    open_m = {r["m"] for r in score(entries, today) if r["status"] in ("open", "waiting")}
    week = str(today.date())
    have = {(e["week"], e["m"]) for e in entries}
    for k, m in res.items():
        v = m["verdict"]
        if v not in VD.SIDES or k in open_m or (week, k) in have:
            continue
        d = m["seas"].get("driver") or {}
        cal = VD.horizon(m["basis"]) == "window"
        start = max(today, pd.Timestamp(d["start"])) if cal and d.get("start") else today
        entries.append({"week": week, "m": k, "name": m["name"], "verdict": v, "basis": m["basis"],
                        "macro": (m.get("macro") or {}).get("rel"),
                        "report": str(asof.date()), "entry_from": str((start + pd.Timedelta(days=1 if start == today else 0)).date()),
                        "window_end": d.get("end") if cal else None})
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    json.dump(entries, open(FILE, "w"), indent=1)
    return entries


def summary(today):
    """the live record for the page"""
    rows = score(load(), today)
    done = [r for r in rows if r["status"] == "done"]
    def agg(rs):
        if not rs:
            return None
        sg = [1 if r["verdict"] == "BULLISH" else -1 for r in rs]
        Rs = [r["R"] for r in rs if r.get("R") is not None]
        return {"n": len(rs), "right": sum(r["right"] for r in rs),
                "avg_dir": round(float(np.mean([s * r["move"] for s, r in zip(sg, rs)])), 2),
                "avg_R": round(float(np.mean(Rs)), 2) if Rs else None,
                "avg_best": round(float(np.mean([r["best"] for r in rs if r.get("best") is not None])), 2)}
    return {"since": min((r["week"] for r in rows), default=None), "done": agg(done),
            "by_basis": {b: agg([r for r in done if r["basis"] == b]) for b in sorted({r["basis"] for r in done})},
            "by_macro": {x: agg([r for r in done if r.get("macro") == x]) for x in ("agrees", "against", "flat")},
            "open": [r for r in rows if r["status"] in ("open", "waiting")],
            "recent": sorted(done, key=lambda r: r["exit"], reverse=True)[:12]}
