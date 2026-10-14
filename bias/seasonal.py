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
    def _years(self, Y):
        ys = list(range(Y - NY, Y))
        return ys if all(y in self.first for y in ys) else None

    def scan(self, t):
        """win counts for every (start, length) around t, from the 15 years before t's year"""
        Y = t.year
        ys = self._years(Y)
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
        mu = s1 / NY
        sd = np.sqrt(np.maximum(s2 / NY - mu ** 2, 1e-18) * NY / (NY - 1))
        return {"Y": Y, "now": now, "S": S, "up": up, "wins": np.maximum(up, NY - up),
                "t": np.abs(mu) / sd * np.sqrt(NY)}

    def stats(self, Y, s, L, side):
        """Seasonax-style statistics of one window over the 15 years before Y"""
        sg = 1 if side == "BUY" else -1
        raw, res, yrs = [], [], []
        for y in range(Y - NY, Y):
            a = self.first[y][0] + s
            b = a + L
            r = self.lc[b] - self.lc[a]
            raw.append(100 * (np.exp(r) - 1))
            res.append(r - self.drift[a] * L)
            yrs.append(y)
        raw, res = np.array(raw), np.array(res)
        dirv = sg * raw
        avg = float(raw.mean())
        return {"wins": int((dirv > 0).sum()), "wins_true": int((sg * res > 0).sum()), "n": NY,
                "avg": round(avg, 2), "median": round(float(np.median(raw)), 2),
                "annual": round(100 * float(np.sign(1 + avg / 100) * (abs(1 + avg / 100) ** (252 / L) - 1)), 1),
                "best": round(float(dirv.max()), 2), "worst": round(float(dirv.min()), 2),
                "rec": int((dirv[-4:] > 0).sum()),
                "years": [{"y": y, "r": round(float(v), 2)} for y, v in zip(yrs, dirv)]}

    def windows(self, t, max_picks=4):
        """the board's windows: driver = best window open now, else best opening within 2 weeks; up to 3 more"""
        sc = self.scan(t)
        if sc is None:
            return [], "none"
        Y, now, S = sc["Y"], sc["now"], sc["S"]
        ok = (sc["wins"] >= GATE) & ((S[:, None] + LEN_TD[None, :]) > now + 2)
        if not ok.any():
            return [], "none"
        ii, jj = np.nonzero(ok)
        cand = sorted(({"side": "BUY" if sc["up"][i, j] >= 8 else "SELL", "wins": int(sc["wins"][i, j]),
                        "t": float(sc["t"][i, j]), "s": int(S[i]), "len": int(LEN_TD[j])} for i, j in zip(ii, jj)),
                      key=lambda w: (-w["wins"], -w["t"]))
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
            st = self.stats(Y, w["s"], w["len"], w["side"])
            out.append({**w, **{k: v for k, v in st.items() if k != "wins"}, "wins": w["wins"],
                        "start": str(self.date(Y, w["s"]).date()), "end": str(self.date(Y, w["s"] + w["len"]).date()),
                        "t": round(w["t"], 2)})
        if not near:                                     # windows later in the horizon, none to lead with
            return sorted(out, key=lambda w: w["s"]), "none"
        drv = out[0]
        cancel = any(w["side"] != drv["side"] and w["wins"] >= drv["wins"] - 1 and abs(w["s"] - drv["s"]) <= OPEN_AHEAD
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
        for sh in (-s2, -s1, s1, s2):
            r = [sg * (self.lc[self.first[y][0] + w["s"] + sh + L] - self.lc[self.first[y][0] + w["s"] + sh])
                 for y in range(Y - NY, Y)]
            out.append({"shift": sh, "win": round(100 * float(np.mean(np.array(r) > 0)))})
        return out

    def past(self, Y, w, reader):
        """the window in each of its 15 past years: COT read at its start, and whether it paid"""
        side = "BULLISH" if w["side"] == "BUY" else "BEARISH"
        sg = 1 if side == "BULLISH" else -1
        out = []
        for y in range(Y - NY, Y):
            a = self.first[y][0] + w["s"]
            r = sg * (np.exp(self.lc[a + w["len"]] - self.lc[a]) - 1)
            c = reader.read(self.dates[a]) if reader else "NEUTRAL"
            rel = "agree" if c == side else "against" if c in ("BULLISH", "BEARISH") else "none"
            out.append({"y": y, "cot": c, "rel": rel, "r": round(100 * float(r), 2), "win": bool(r > 0)})
        summ = {rel: {"n": sum(x["rel"] == rel for x in out), "w": sum(x["win"] for x in out if x["rel"] == rel)}
                for rel in ("agree", "against", "none")}
        return {"years": out, "summary": summ}
