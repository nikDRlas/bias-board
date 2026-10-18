"""Seasonal window engine, counted in TRADING DAYS. Shared by the board (build.py) and the tests (research/).

A window is "the s-th to the (s+L)-th trading day of the year". Each past year is measured on its own
trading days, so weekends and holidays never stretch or shrink a window. Seasonax-style statistics:
win ratio = years in which price moved the trade's way over the window (raw, no trend removal); the
trend-removed count is reported alongside.
"""
import os
import numpy as np, pandas as pd

DRIFT_N = 252
START_TD = np.arange(-10, 41)        # entry from 2 weeks ago to 8 weeks ahead
LEN_TD = np.arange(5, int(os.environ.get("SEAS_MAXLEN", "30")) + 1)   # 5 to 30 trading days (about 6 weeks; 63 tested equal per week)
NY, GATE = 15, 12                    # 15 past years, at least 12 in the trade's direction
# lookbacks a window may qualify on: (years, wins needed). (15, 12) and (10, 8) are both an 80% win ratio.
LOOKBACKS = {"15": [(15, 12)], "10": [(10, 8)]}[os.environ.get("SEAS_YEARS", "15")]
OPEN_AHEAD = 10                      # a window may start up to 10 trading days ahead to be the driver
# minimum usual move, in units of the market's normal daily move (daily volatility over the past year), for a window
# that has to carry the bias ALONE (calendar only, calendar over COT): it has to be worth trading. A window that agrees
# with COT needs no minimum. Tested: research/verdict_test.py, research/seasonal_config.json (3 = best of 0/1.5/2/3).
SOLO_MIN_MOVE = float(os.environ.get("SEAS_MIN_MOVE", "3"))
# how windows are found: "scan" = every start and length (Seasonax-style screener), "swing" = from a turning point of
# the 15-year average path to the next one (low to high = buy, high to low = sell); research/swing_windows_test.py
MODE = os.environ.get("SEAS_MODE", "scan")
SWING = float(os.environ.get("SEAS_SWING", "1.5"))           # a turn = the average path reverses this many normal days
GATE_OVERRIDE = os.environ.get("SEAS_GATE")
SWING_DETREND = os.environ.get("SEAS_SWING_DETREND", "0") == "1"   # find turns on the path without its average drift


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

    def scan(self, t, ny=NY, lens=None, starts=None):
        """win counts for every (start, length) around t, from the `ny` years before t's year"""
        lens = LEN_TD if lens is None else lens
        Y = t.year
        ys = self._years(Y, ny)
        now = self.td(t)
        if ys is None or now < 0:
            return None
        S = now + START_TD if starts is None else starts
        up = np.zeros((len(S), len(lens)))
        s1 = np.zeros_like(up)
        s2 = np.zeros_like(up)
        for y in ys:
            a = self.first[y][0] + S
            if a.min() < DRIFT_N + 1:
                return None
            b = a[:, None] + lens[None, :]
            if b.max() >= self.n:
                return None
            r = self.lc[b] - self.lc[a][:, None]
            up += r > 0
            s1 += r
            s2 += r * r
        mu = s1 / ny
        sd = np.sqrt(np.maximum(s2 / ny - mu ** 2, 1e-18) * ny / (ny - 1))
        return {"Y": Y, "now": now, "S": S, "up": up, "lens": lens, "wins": np.maximum(up, ny - up), "ny": ny,
                "t": np.abs(mu) / sd * np.sqrt(ny), "mu": mu}

    def day_vol(self, t):
        """normal daily move (standard deviation of daily log returns over the past year) up to t"""
        i = int(self.dates.searchsorted(t, "right"))
        d = np.diff(self.lc[max(0, i - 253):i])
        return float(d.std()) if len(d) > 20 else np.nan

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

    def swing_cands(self, t, ny, gate, min_move=0.0, lens=None):
        """windows from one turning point of the average path of the `ny` past years to the next"""
        lens = LEN_TD if lens is None else lens
        Y, now = t.year, self.td(t)
        ys = self._years(Y, ny)
        if ys is None or now < 0:
            return []
        lo = max(0, now + int(START_TD.min()) - 60)
        hi = now + int(START_TD.max()) + int(lens.max()) + 60
        if any(self.first[y][0] + hi >= self.n for y in ys):
            return []
        P = np.mean([self.lc[self.first[y][0] + lo:self.first[y][0] + hi] - self.lc[self.first[y][0] + lo] for y in ys], axis=0)
        vol = self.day_vol(t)
        if SWING_DETREND:                                # remove the 15 years' average daily drift
            drift = np.mean([self.lc[self.first[y][0] + self.first[y][1] - 1] - self.lc[self.first[y][0]] for y in ys]) / 252
            P = P - drift * np.arange(len(P))
        thr = SWING * vol
        piv, trend, ext, lo_i, hi_i = [], 0, 0, 0, 0
        for i in range(1, len(P)):
            if trend == 0:
                lo_i = i if P[i] < P[lo_i] else lo_i
                hi_i = i if P[i] > P[hi_i] else hi_i
                if P[i] - P[lo_i] >= thr:
                    piv, trend, ext = [lo_i], 1, i
                elif P[hi_i] - P[i] >= thr:
                    piv, trend, ext = [hi_i], -1, i
            elif trend == 1:
                if P[i] > P[ext]:
                    ext = i
                elif P[ext] - P[i] >= thr:
                    piv.append(ext)
                    trend, ext = -1, i
            else:
                if P[i] < P[ext]:
                    ext = i
                elif P[i] - P[ext] >= thr:
                    piv.append(ext)
                    trend, ext = 1, i
        out = []
        for a, b in zip(piv[:-1], piv[1:]):
            s0, L = lo + a, b - a
            if L < lens.min() or L > lens.max() or not (now + START_TD.min() <= s0 <= now + START_TD.max()) or s0 + L <= now + 2:
                continue
            r = np.array([self.lc[self.first[y][0] + s0 + L] - self.lc[self.first[y][0] + s0] for y in ys])
            side = "BUY" if P[b] > P[a] else "SELL"
            sg = 1 if side == "BUY" else -1
            w = int((sg * r > 0).sum())
            mu, sd = float(r.mean()), float(r.std(ddof=1)) or 1e-9
            if w < gate or (min_move > 0 and abs(mu) < min_move * vol):
                continue
            out.append({"side": side, "wins": w, "ny": ny, "share": w / ny, "t": abs(mu) / sd * np.sqrt(ny),
                        "s": int(s0), "len": int(L)})
        return out

    def windows(self, t, max_picks=4, min_move=0.0, lens=None):
        """the board's windows: driver = best window open now, else best opening within 2 weeks; up to 3 more.
        min_move: only windows whose usual move is at least this many normal daily moves"""
        cand, seen, Y, now = [], set(), t.year, self.td(t)
        for ny, gate in LOOKBACKS:
            gate = int(GATE_OVERRIDE) if GATE_OVERRIDE else gate
            if MODE == "swing":
                cand += self.swing_cands(t, ny, gate, min_move, lens)
                continue
            sc = self.scan(t, ny, lens)
            if sc is None:
                continue
            S, LL = sc["S"], sc["lens"]
            ok = (sc["wins"] >= gate) & ((S[:, None] + LL[None, :]) > now + 2)
            if min_move > 0:
                ok &= np.abs(sc["mu"]) >= min_move * self.day_vol(t)
            for i, j in zip(*np.nonzero(ok)):
                cand.append({"side": "BUY" if sc["up"][i, j] > ny / 2 else "SELL", "wins": int(sc["wins"][i, j]),
                             "ny": ny, "share": float(sc["wins"][i, j]) / ny,
                             "t": float(sc["t"][i, j]), "s": int(S[i]), "len": int(LL[j])})
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
        opp = [w for w in out[1:] if w["side"] != drv["side"] and w["share"] >= drv["share"] - 0.07
               and abs(w["s"] - drv["s"]) <= OPEN_AHEAD]
        rest = sorted(out[1:], key=lambda w: w["s"])
        if opp:
            # two valid windows that turn: trade them in sequence (research/cancel_test.py). Before the turn the leading
            # window runs until the opposite one starts; from the turn on, the opposite window leads.
            o = opp[0]
            first, second = (drv, o) if drv["s"] <= o["s"] else (o, drv)
            others = sorted([w for w in out if w is not first and w is not second], key=lambda w: w["s"])
            if now < second["s"] - 1 and second["s"] > first["s"]:
                cut = second["s"] - first["s"]
                st = self.stats(Y, first["s"], cut, first["side"], first["ny"])
                part = {**first, **{k: v for k, v in st.items() if k != "wins"}, "wins": st["wins"], "len": cut,
                        "end": str(self.date(Y, second["s"]).date()), "full_end": first["end"], "full_wins": first["wins"],
                        "turn": {"side": second["side"], "start": second["start"], "end": second["end"],
                                 "wins": second["wins"], "ny": second["ny"]}}
                return [part, second] + others, "driver"
            lead = {**second, "after_turn": {"side": first["side"], "start": first["start"], "end": first["end"],
                                             "wins": first["wins"]}}
            return [lead, first] + others, "driver"
        return [drv] + rest, "driver"

    def upcoming(self, t, n=50, ahead=90):
        """for the chart and table: every window starting within `ahead` trading days after t (as far as all 15 past
        years cover it), strongest first (most years, then most consistent), skipping windows that overlap one
        already listed in the same direction or by more than half. Display only, not part of the verdict."""
        Y, now = t.year, self.td(t)
        ny, gate = LOOKBACKS[0]
        if Y - 1 not in self.first or now < 0:
            return []
        last = self.n - 1 - self.first[Y - 1][0] - int(LEN_TD.max())   # the latest past year must cover the window
        starts = np.arange(now + 1, max(now + 2, min(last, now + ahead + 1)))
        sc = self.scan(t, ny, starts=starts)
        if sc is None:
            return []
        vol = self.day_vol(t)
        ok = sc["wins"] >= gate
        cand = [{"s": int(starts[i]), "len": int(LEN_TD[j]), "side": "BUY" if sc["up"][i, j] > ny / 2 else "SELL",
                 "wins": int(sc["wins"][i, j]), "t": float(sc["t"][i, j]), "mu": float(sc["mu"][i, j])}
                for i, j in zip(*np.nonzero(ok))]
        cand.sort(key=lambda w: (-w["wins"], -w["t"]))
        picks = []
        for w in cand:
            if any(min(w["s"] + w["len"], q["s"] + q["len"]) - max(w["s"], q["s"]) > 0 and
                   (q["side"] == w["side"] or min(w["s"] + w["len"], q["s"] + q["len"]) - max(w["s"], q["s"]) > 0.5 * min(w["len"], q["len"]))
                   for q in picks):
                continue
            picks.append(w)
            if len(picks) == n:
                break
        out = []
        for best in sorted(picks, key=lambda w: w["s"]):
            st = self.stats(Y, best["s"], best["len"], best["side"], ny)
            move = abs(best["mu"]) / vol if vol else None
            out.append({**{k2: v2 for k2, v2 in st.items() if k2 not in ("wins", "n")},
                        "side": best["side"], "wins": best["wins"], "n": ny, "ny": ny, "s": best["s"], "len": best["len"],
                        "t": round(best["t"], 2), "avg": st["avg"], "start": str(self.date(Y, best["s"]).date()),
                        "end": str(self.date(Y, best["s"] + best["len"]).date()),
                        "move_days": round(move, 1) if move else None,
                        "small": bool(move is not None and move < SOLO_MIN_MOVE)})
        return out

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
