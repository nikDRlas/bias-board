"""Seasonal window engine, counted in TRADING DAYS. Shared by the board (build.py) and the tests (research/).

A window is "the s-th to the (s+L)-th trading day of the year". Each past year is measured on its own
trading days, so weekends and holidays never stretch or shrink a window. Seasonax-style statistics:
win ratio = years in which price moved the trade's way over the window (raw, no trend removal); the
trend-removed count is reported alongside.
"""
import numpy as np, pandas as pd

DRIFT_N = 252
START_TD = np.arange(-10, 41)        # entry from 2 weeks ago to 8 weeks ahead
LEN_TD = np.arange(5, 64)            # 5 trading days to about 3 months
NY, GATE = 15, 12                    # 15 past years, at least 12 in the trade's direction
# lookbacks a window may qualify on: (years, wins needed). (15, 12) and (10, 8) are both an 80% win ratio.
LOOKBACKS = [(15, 12)]
OPEN_AHEAD = 10                      # a window may start up to 10 trading days ahead to be the driver


class Calendar:
    def __init__(self, p):
        self.p = p
        self.dates = p.index
        self.lc = np.log(p.to_numpy(float))
        d = np.diff(self.lc, prepend=self.lc[0])
        self.drift = pd.Series(d).rolling(DRIFT_N).mean().shift(1).to_numpy()
        yrs = self.dates.year.to_numpy()
        self.first = {}
        for y in np.unique(yrs):
            idx = np.nonzero(yrs == y)[0]
            self.first[int(y)] = (int(idx[0]), len(idx))
        self.n = len(p)

    # ---------------------------------------------------------------- trading-day arithmetic
    def td(self, t):
        """trading-day number (0-based) within t's year of the last bar on or before t"""
        f = self.first.get(t.year)
        if not f:
            return -1
        return int(self.dates.searchsorted(t, "right") - 1 - f[0])

    def date(self, y, s):
        """calendar date of the s-th trading day of year y (weekdays projected beyond the data)"""
        f = self.first[y][0]
        i = f + s
        if i < self.n:
            return self.dates[i]
        extra = i - (self.n - 1)
        return pd.Timestamp(np.busday_offset(self.dates[-1].date(), extra, roll="forward"))

    # ---------------------------------------------------------------- scanning
    def _years(self, Y, ny=NY):
        ys = list(range(Y - ny, Y))
        return ys if all(y in self.first for y in ys) else None

    def scan(self, t, ny=NY):
        """win counts for every (start, length) around t, from the `ny` years before t's year"""
        Y = t.year
        ys = self._years(Y, ny)
        now = self.td(t)
        if ys is None or now < 0:
            return None
        S = now + START_TD
        up = np.zeros((len(S), len(LEN_TD)))
        s1 = np.zeros_like(up)
        s2 = np.zeros_like(up)
        for y in ys:
            a = self.first[y][0] + S
            if a.min() < DRIFT_N + 1:
                return None
            b = a[:, None] + LEN_TD[None, :]
            if b.max() >= self.n:
                return None
            r = self.lc[b] - self.lc[a][:, None]
            up += r > 0
            s1 += r
            s2 += r * r
        mu = s1 / ny
        sd = np.sqrt(np.maximum(s2 / ny - mu ** 2, 1e-18) * ny / (ny - 1))
        return {"Y": Y, "now": now, "S": S, "up": up, "wins": np.maximum(up, ny - up), "ny": ny,
                "t": np.abs(mu) / sd * np.sqrt(ny)}

    def stats(self, Y, s, L, side, ny=NY):
        """Seasonax-style statistics of one window over the `ny` years before Y"""
        sg = 1 if side == "BUY" else -1
        raw, res, yrs = [], [], []
        for y in range(Y - ny, Y):
            a = self.first[y][0] + s
            b = a + L
            r = self.lc[b] - self.lc[a]
            raw.append(100 * (np.exp(r) - 1))
            res.append(r - self.drift[a] * L)
            yrs.append(y)
        raw, res = np.array(raw), np.array(res)
        dirv = sg * raw
        avg = float(raw.mean())
        return {"wins": int((dirv > 0).sum()), "wins_true": int((sg * res > 0).sum()), "n": ny,
                "avg": round(avg, 2), "median": round(float(np.median(raw)), 2),
                "annual": round(100 * float(np.sign(1 + avg / 100) * (abs(1 + avg / 100) ** (252 / L) - 1)), 1),
                "best": round(float(dirv.max()), 2), "worst": round(float(dirv.min()), 2),
                "rec": int((dirv[-4:] > 0).sum()),
                "years": [{"y": y, "r": round(float(v), 2)} for y, v in zip(yrs, dirv)]}

    def windows(self, t, max_picks=4):
        """the board's windows: driver = best window open now, else best opening within 2 weeks; up to 3 more"""
        cand, seen, Y, now = [], set(), t.year, self.td(t)
        for ny, gate in LOOKBACKS:
            sc = self.scan(t, ny)
            if sc is None:
                continue
            S = sc["S"]
            ok = (sc["wins"] >= gate) & ((S[:, None] + LEN_TD[None, :]) > now + 2)
            for i, j in zip(*np.nonzero(ok)):
                cand.append({"side": "BUY" if sc["up"][i, j] > ny / 2 else "SELL", "wins": int(sc["wins"][i, j]),
                             "ny": ny, "share": float(sc["wins"][i, j]) / ny,
                             "t": float(sc["t"][i, j]), "s": int(S[i]), "len": int(LEN_TD[j])})
        if not cand:
            return [], "none"
        cand.sort(key=lambda w: (-w["share"], -w["t"], -w["ny"]))
        uniq = []
        for w in cand:                                   # the same window found on both lookbacks counts once
            key = (w["s"], w["len"], w["side"])
            if key not in seen:
                seen.add(key)
                uniq.append(w)
        cand = uniq
        near = [w for w in cand if w["s"] <= now] or [w for w in cand if w["s"] <= now + OPEN_AHEAD]
        picks = near[:1]
        for w in cand:
            clash = False
            for q in picks:
                ov = min(w["s"] + w["len"], q["s"] + q["len"]) - max(w["s"], q["s"])
                if ov > 0 and (q["side"] == w["side"] or ov > 0.5 * min(w["len"], q["len"])):
                    clash = True
            if not clash:
                picks.append(w)
            if len(picks) == max_picks:
                break
        out = []
        for w in picks:
            st = self.stats(Y, w["s"], w["len"], w["side"], w["ny"])
            out.append({**w, **{k: v for k, v in st.items() if k != "wins"}, "wins": w["wins"],
                        "start": str(self.date(Y, w["s"]).date()), "end": str(self.date(Y, w["s"] + w["len"]).date()),
                        "t": round(w["t"], 2)})
        if not near:                                     # windows later in the horizon, none to lead with
            return sorted(out, key=lambda w: w["s"]), "none"
        drv = out[0]
        cancel = any(w["side"] != drv["side"] and w["share"] >= drv["share"] - 0.07 and abs(w["s"] - drv["s"]) <= OPEN_AHEAD
                     for w in out[1:])
        return [drv] + sorted(out[1:], key=lambda w: w["s"]), ("cancel" if cancel else "driver")

    def driver(self, t):
        """for the tests: the driver window as of t, 'cancel', or None"""
        ws, status = self.windows(t)
        if status != "driver":
            return "cancel" if status == "cancel" else None
        d = dict(ws[0])
        d["start"], d["end"] = pd.Timestamp(d["start"]), pd.Timestamp(d["end"])
        return d

    def neighbours(self, Y, w):
        sg = 1 if w["side"] == "BUY" else -1
        L = w["len"]
        s1, s2 = max(2, round(L / 4)), min(10, max(4, round(L / 2)))
        out = []
        ny = w.get("ny", NY)
        for sh in (-s2, -s1, s1, s2):
            r = [sg * (self.lc[self.first[y][0] + w["s"] + sh + L] - self.lc[self.first[y][0] + w["s"] + sh])
                 for y in range(Y - ny, Y)]
            out.append({"shift": sh, "win": round(100 * float(np.mean(np.array(r) > 0)))})
        return out

    def remaining(self, t, w):
        """what the window usually still does from t (or its start, if later) to its end, over the 15 past years,
        and what it has done so far this year"""
        Y, now = t.year, self.td(t)
        s0, e = max(now, w["s"]), w["s"] + w["len"]
        if e <= s0:
            return None
        sg = 1 if w["side"] == "BUY" else -1
        ny = w.get("ny", NY)
        r = np.array([np.exp(self.lc[self.first[y][0] + e] - self.lc[self.first[y][0] + s0]) - 1 for y in range(Y - ny, Y)])
        so_far = None
        if now > w["s"] and self.first[Y][0] + now < self.n:
            so_far = round(100 * float(np.exp(self.lc[self.first[Y][0] + now] - self.lc[self.first[Y][0] + w["s"]]) - 1), 2)
        return {"days": int(e - s0), "avg": round(100 * float(r.mean()), 2), "median": round(100 * float(np.median(r)), 2),
                "wins": int((sg * r > 0).sum()), "n": ny, "so_far": so_far, "started": bool(now >= w["s"])}

    def past(self, Y, w, reader):
        """the window in each of its 15 past years: COT read at its start, and whether it paid"""
        side = "BULLISH" if w["side"] == "BUY" else "BEARISH"
        sg = 1 if side == "BULLISH" else -1
        out = []
        for y in range(Y - w.get("ny", NY), Y):
            a = self.first[y][0] + w["s"]
            r = sg * (np.exp(self.lc[a + w["len"]] - self.lc[a]) - 1)
            c = reader.read(self.dates[a]) if reader else "NEUTRAL"
            rel = "agree" if c == side else "against" if c in ("BULLISH", "BEARISH") else "none"
            out.append({"y": y, "cot": c, "rel": rel, "r": round(100 * float(r), 2), "win": bool(r > 0)})
        summ = {rel: {"n": sum(x["rel"] == rel for x in out), "w": sum(x["win"] for x in out if x["rel"] == rel)}
                for rel in ("agree", "against", "none")}
        return {"years": out, "summary": summ}
