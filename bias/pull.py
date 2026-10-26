#!/usr/bin/env python3
"""Refresh the data behind the board from LSE Data 3.0 (https://download.londonstrategicedge.com/v3, since 24 Oct 2026;
the old /vault API answers 410) and the CFTC.

Daily -> data/live/<NAME>.csv  the stored history (data/history/lse, the old LSE feed up to Oct 2026) with the newest
                               weeks from /v3/export appended. A daily bar is stamped with its session start in UTC;
                               its trading day is that time + 6 hours (FX and metals open the evening before), which
                               matches the old calendar-day bars. Where an instrument changed (index CFDs -> cash
                               indices, cattle CFD -> futures), the new rows are scaled onto the old level by the
                               median ratio over the overlapping days.
COT   -> data/live/cot.json    LSE's COT archive (/v3/reference, dataset cot); the newest reports, which LSE's archive
                               may not have yet, come straight from the CFTC and are appended to data/cftc/*_legacy.json.
Macro -> data/macro/           economic calendar (last months re-pulled and merged) and the US 2-year yield.
The API key comes from the LSE_KEY environment variable, or a local .lse_key file.
Uses curl (this machine's Python has no usable CA bundle for the host).
"""
import csv, io, json, os, subprocess, sys, time, urllib.parse, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.environ.get("LSE_KEY") or open(os.path.join(ROOT, ".lse_key")).read().strip()
OUT = os.path.join(ROOT, "data", "live")
HIST = os.path.join(ROOT, "data", "history", "lse")
CFTC_DIR = os.path.join(ROOT, "data", "cftc")
MACRO = os.path.join(ROOT, "data", "macro")
BASE = "https://download.londonstrategicedge.com/v3"
END = (dt.date.today() + dt.timedelta(days=1)).isoformat()

# report name -> (LSE 3.0 market, symbol); None = no live source, the stored history is used as it is
PRICES = {
    "GC": ("commodities", "XAU/USD"), "SI": ("commodities", "XAG/USD"),
    "PL": ("commodities", "XPT/USD"), "PA": ("commodities", "XPD/USD"),
    "HG": ("commodities", "XCU/USD"), "CL": ("commodities", "WTICO/USD"),
    "NG": ("commodities", "NATGAS/USD"),
    "6E": ("forex", "EUR_USD"), "6B": ("forex", "GBP_USD"), "6J": ("forex", "USD_JPY"),
    "6S": ("forex", "USD_CHF"), "6A": ("forex", "AUD_USD"), "6C": ("forex", "USD_CAD"),
    "6N": ("forex", "NZD_USD"), "SEK": ("forex", "USD_SEK"),        # SEK: only to rebuild the dollar index from its legs
    "ES": ("indices", "SPX"), "NQ": ("indices", "NDX"), "YM": ("indices", "DJI"),
    "ZC": ("commodities", "CORN/USD"), "ZW": ("commodities", "WHEAT/USD"), "ZS": ("commodities", "SOYBN/USD"),
    "SB": ("commodities", "SUGAR/USD"), "KC": ("commodities", "COFFEE/USD"), "LE": ("futures", "LIVECATTLE"),
    "DAX": ("indices", "BDE40P"), "ESTX": ("indices", "BEZ50P"),     # quant strategies only (no CFTC COT)
    "DX": None,                                                      # rebuilt from its legs in core.load_px
}
# CFTC legacy futures-only contract codes (matched to data/cftc/*_legacy.json on 2026-08-11)
CFTC_CODES = {"6A": "232741", "6B": "096742", "6C": "090741", "6E": "099741", "6J": "097741", "6N": "112741",
              "6S": "092741", "CL": "067651", "DX": "098662", "ES": "13874A", "GC": "088691", "HG": "085692",
              "KC": "083731", "LE": "057642", "NG": "023651", "NQ": "209742", "PA": "075651", "PL": "076651",
              "SB": "080732", "SI": "084691", "YM": "124603", "ZC": "002602", "ZS": "005602", "ZW": "001602"}
CFTC_FIELDS = ["comm_positions_long_all", "comm_positions_short_all", "noncomm_positions_long_all",
               "noncomm_positions_short_all", "nonrept_positions_long_all", "nonrept_positions_short_all", "open_interest_all"]


def _curl(url, timeout=300):
    r = subprocess.run(["curl", "-s", "-m", str(timeout), "-H", f"X-API-Key: {KEY}", "-w", "\n%{http_code}", url],
                       capture_output=True, text=True).stdout
    body, _, code = r.rpartition("\n")
    return int(code or 0), body


def call(path, params, tries=10):
    """one /v3 call; a file comes back as text (a prepared job is waited for); 429 and 5xx are retried"""
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    for i in range(tries):
        code, body = _curl(url)
        if code == 200:
            time.sleep(1.1)                                 # 60 calls a minute on the free plan
            return body
        if code == 202:
            return _job(json.loads(body))
        if code == 429 or code >= 500 or code == 0:
            try:
                wait = float(json.loads(body).get("retry_after") or 0)
            except Exception:
                wait = 0
            time.sleep(max(wait, 3 * (i + 1)))
            continue
        raise RuntimeError(f"{path} {params.get('symbol', params.get('dataset', ''))}: {code} {body[:200]}")
    raise RuntimeError(f"{path} {params}: gave up after {tries} tries")


def _job(job, timeout=900):
    t0 = time.time()
    while job.get("status") not in ("ready", "failed", "expired"):
        if time.time() - t0 > timeout:
            raise RuntimeError(f"job {job.get('job_id')} not ready")
        time.sleep(3)
        code, body = _curl(f"{BASE}/jobs/{job['job_id']}")
        if code == 200:
            job = json.loads(body)
    if job["status"] != "ready":
        raise RuntimeError(f"job {job.get('job_id')} {job['status']}: {job.get('error')}")
    for i in range(10):
        code, body = _curl(f"{BASE}/jobs/{job['job_id']}/file")
        if code == 200:
            time.sleep(1.1)
            return body
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"job {job['job_id']}: file not served")


def rows_csv(text):
    return list(csv.DictReader(io.StringIO(text)))


def candles(market, symbol, start):
    """daily bars from `start`: {trading day: (open, high, low, close)}, the day = session start + 6 hours"""
    txt = call("export", {"market": market, "symbol": symbol, "timeframe": "1d", "from": start, "to": END, "format": "csv"})
    out = {}
    for r in rows_csv(txt):
        t = dt.datetime.fromisoformat(r["time"][:19]) + dt.timedelta(hours=6)
        out[t.date().isoformat()] = tuple(float(r[c]) for c in ("open", "high", "low", "close"))
    return out


def refresh_prices():
    import pandas as pd
    for name, src in PRICES.items():
        arch = pd.read_csv(os.path.join(HIST, f"{name}.csv.gz"))
        arch["day"] = arch.ts.str[:10]
        last = arch.day.max()
        new = {}
        if src:
            try:
                start = (dt.date.fromisoformat(last) - dt.timedelta(days=21)).isoformat()
                new = candles(*src, start)
            except Exception as e:
                print(f"{name:4s} {src[1]:11s} FAILED {e} (stored history only)")
        ratio = 1.0
        ov = [(arch.set_index("day").close[d], new[d][3]) for d in new if d in set(arch.day)]
        if len(ov) >= 3:
            q = sorted(a / b for a, b in ov)
            ratio = q[len(q) // 2]
            # same instrument on the same level (single days differ a little: the new bars close at 22:00 UTC, the old
            # at midnight), or a rescaled instrument that tracks the stored one closely; anything else is not spliced
            if not (0.9 < ratio < 1.1 or q[-1] / q[0] < 1.03):
                print(f"{name:4s} new series does not track the stored one (ratio {q[0]:.3f}..{q[-1]:.3f}), new rows ignored")
                new, ratio = {}, 1.0
        add = [(d, *[v * ratio for v in new[d]]) for d in sorted(new) if d > last]
        with open(os.path.join(OUT, name + ".csv"), "w") as f:
            f.write("ts,open,high,low,close\n")
            for r in arch.itertuples():
                f.write(f"{r.ts},{r.open},{r.high},{r.low},{r.close}\n")
            for d, o, h, l, c in add:
                f.write(f"{d} 00:00:00.000000,{o},{h},{l},{c}\n")
        print(f"{name:4s} {(src or ('', 'stored'))[1]:11s} history to {last}, +{len(add)} days to "
              f"{add[-1][0] if add else last}" + (f", spliced x{ratio:.4f} over {len(ov)} days" if len(ov) >= 3 else ""), flush=True)


def _num(v):
    if v in ("", "\\N", None):
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except ValueError:
        return v


def pull_cot():
    rows = rows_csv(call("reference/export", {"dataset": "cot", "from": "2015-01-01", "to": END, "format": "csv"}))
    rows = [{k: (v if k in ("symbol", "date", "name", "sector", "created_at", "lse_symbol", "candle_name", "release_date")
                 else _num(v)) for k, v in r.items()} for r in rows]
    print(f"COT (LSE): {len(rows)} rows, {min(r['date'] for r in rows)} -> {max(r['date'] for r in rows)}")
    return rows


def cftc_update():
    """append the CFTC's newest weekly reports to data/cftc/<market>_legacy.json"""
    for k, code in CFTC_CODES.items():
        path = os.path.join(CFTC_DIR, f"{k}_legacy.json")
        old = json.load(open(path))
        last = max(r["report_date_as_yyyy_mm_dd"] for r in old)[:10]
        q = urllib.parse.urlencode({"$where": f"cftc_contract_market_code='{code}' AND report_date_as_yyyy_mm_dd>'{last}T00:00:00.000'",
                                    "$select": "report_date_as_yyyy_mm_dd," + ",".join(CFTC_FIELDS), "$order": "report_date_as_yyyy_mm_dd",
                                    "$limit": "1000"})
        new = json.loads(subprocess.run(["curl", "-s", "-m", "120", f"https://publicreporting.cftc.gov/resource/6dca-aqww.json?{q}"],
                                        capture_output=True, text=True).stdout or "[]")
        keys = list(old[0].keys())
        add = [{c: r.get(c) for c in keys} for r in new]
        if add:
            json.dump(old + add, open(path, "w"))
        print(f"CFTC {k:3s} {code}: +{len(add)} reports, last {add[-1]['report_date_as_yyyy_mm_dd'][:10] if add else last}")


def pull_macro(months=4):
    """economic calendar: the last `months` months re-pulled and merged into data/macro/calendar_lse.csv.gz (history
    since 2015 is in the repo); US 2-year yield (sovereign yields, 2010 onwards) -> data/macro/us2y_lse.csv"""
    import pandas as pd
    path = os.path.join(MACRO, "calendar_lse.csv.gz")
    old = pd.read_csv(path, low_memory=False) if os.path.exists(path) else pd.DataFrame()
    first = (dt.date.today().replace(day=1) - dt.timedelta(days=31 * (months - 1))).replace(day=1)
    new = pd.DataFrame(rows_csv(call("reference/export", {"dataset": "economic_calendar", "from": first.isoformat(),
                                                          "to": END, "format": "csv"})))
    keep = ["id", "date", "time", "region_code", "event", "period_hint", "actual", "previous", "consensus", "forecast"]
    new = new[keep].replace({"\\N": None})
    new["id"] = new["id"].astype(int)
    cal = pd.concat([old[~old["id"].isin(new["id"])], new], ignore_index=True).sort_values(["date", "time"])
    cal.to_csv(path, index=False, compression="gzip")
    print(f"calendar: {len(new)} rows re-pulled since {first}, {len(cal)} in total, last {cal['date'].max()}")
    y = pd.DataFrame(rows_csv(call("reference/export", {"dataset": "sovereign_yields", "symbol": "USGB2Y",
                                                        "from": "2010-01-01", "to": END, "format": "csv"})))
    fields = sorted(y["field"].unique()) if len(y) else []
    f = next((x for x in ("mid_yield", "yield_to_maturity", "bid_yield") if x in fields), None)
    if f is None:
        raise RuntimeError(f"no yield field in {fields}")
    y = y[y["field"] == f][["date", "value"]].replace({"\\N": None}).dropna()
    y["value"] = y["value"].astype(float)
    y.drop_duplicates("date", keep="last").sort_values("date").to_csv(os.path.join(MACRO, "us2y_lse.csv"), index=False)
    print(f"US 2-year ({f} of {fields}): {len(y)} days, last {y['date'].max() if len(y) else '-'}")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    try:
        pull_macro()
    except Exception as e:                       # the board still builds without fresh macro data
        print("macro pull FAILED", e)
    if "--no-cot" not in sys.argv:
        c = pull_cot()
        json.dump(c, open(os.path.join(OUT, "cot.json"), "w"))
        cftc_update()
    refresh_prices()
