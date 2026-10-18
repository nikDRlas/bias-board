#!/usr/bin/env python3
"""Refresh the LSE data behind the weekly-outlook recompile (COT + daily spot).

COT   -> data/live/cot.json      (LSE /vault/ref/cot, 2015 onwards)
Daily -> data/live/<NAME>.csv    (LSE /vault/candles, timeframe=1d)
The API key comes from the LSE_KEY environment variable, or a local .lse_key file.
Uses curl (this machine's Python has no usable CA bundle for the host).
"""
import json, os, subprocess, sys, time, urllib.parse, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.environ.get("LSE_KEY") or open(os.path.join(ROOT, ".lse_key")).read().strip()
OUT = os.path.join(ROOT, "data", "live")
BASE = "https://api.londonstrategicedge.com/vault"
END = (dt.date.today() + dt.timedelta(days=1)).isoformat()

# report name -> (LSE symbol, dataset)
PRICES = {
    "GC": ("XAU/USD", "commodity"), "SI": ("XAG/USD", "commodity"),
    "PL": ("XPT/USD", "commodity"), "PA": ("XPD/USD", "commodity"),
    "HG": ("XCU/USD", "commodity"), "CL": ("WTICO/USD", "commodity"),
    "NG": ("NATGAS/USD", "commodity"), "DX": ("DXY/USD", "currency_index"),
    "6E": ("EUR/USD", "fx"), "6B": ("GBP/USD", "fx"), "6J": ("USD/JPY", "fx"),
    "6S": ("USD/CHF", "fx"), "6A": ("AUD/USD", "fx"), "6C": ("USD/CAD", "fx"),
    "6N": ("NZD/USD", "fx"),
    "SEK": ("USD/SEK", "fx"),
    "ES": ("SPX500/USD", "index"), "NQ": ("NAS100/USD", "index"), "YM": ("US30/USD", "index"),
    "ZC": ("CORN/USD", "commodity"), "ZW": ("WHEAT/USD", "commodity"), "ZS": ("SOYBN/USD", "commodity"),
    "SB": ("SUGAR/USD", "commodity"),
    "KC": ("COFFEE/USD", "commodity"), "LE": ("CATTLE/USD", "commodity"),
    "DAX": ("DE30/EUR", "index"), "ESTX": ("EU50/EUR", "index"),     # quant strategies only (no CFTC COT)          # only needed to rebuild DXY from its legs
}


def fetch(url, retries=5):
    r = ""
    for i in range(retries):
        r = subprocess.run(["curl", "-s", "-m", "90", "-H", f"x-api-key: {KEY}",
                            "-H", "User-Agent: curl/8.4.0", url],
                           capture_output=True, text=True).stdout
        try:
            d = json.loads(r)
            if isinstance(d, list):
                return d
        except Exception:
            pass
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"failed: {url.split('?')[1]} -> {r[:200]}")


def pull_candles(sym, dataset, start="1990-01-01"):
    rows = []
    while True:
        q = urllib.parse.urlencode({"symbol": sym, "dataset": dataset,
                                    "timeframe": "1d", "start": start, "end": END})
        b = fetch(f"{BASE}/candles?{q}")
        if rows:
            b = [x for x in b if x["ts"] > rows[-1]["ts"]]
        if not b:
            break
        rows.extend(b)
        if len(b) < 4000:
            break
        start = rows[-1]["ts"][:10]
        time.sleep(0.2)
    return rows


def pull_cot():
    rows = []
    for y in range(2015, dt.date.today().year + 1):
        b = fetch(f"{BASE}/ref/cot?start={y}-01-01&end={y}-12-31&limit=5000")
        print(f"  cot {y}: {len(b)} rows", flush=True)
        rows.extend(b)
        time.sleep(0.2)
    return rows


MACRO = os.path.join(ROOT, "data", "macro")


def pull_macro(months=4):
    """economic calendar: the last `months` months re-pulled and merged into data/macro/calendar_lse.csv.gz (history
    since 2015 is in the repo); US 2-year yield (sovereign series, 2010 onwards) -> data/macro/us2y_lse.csv"""
    import pandas as pd
    path = os.path.join(MACRO, "calendar_lse.csv.gz")
    old = pd.read_csv(path, low_memory=False) if os.path.exists(path) else pd.DataFrame()
    first = (dt.date.today().replace(day=1) - dt.timedelta(days=31 * (months - 1))).replace(day=1)
    rows, m = [], first
    while m <= dt.date.today():
        nxt = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        rows += fetch(f"{BASE}/ref/economic_calendar?start={m.isoformat()}&end={(nxt - dt.timedelta(days=1)).isoformat()}")
        m = nxt
    keep = ["id", "date", "time", "region_code", "event", "period_hint", "actual", "previous", "consensus", "forecast"]
    new = pd.DataFrame(rows)[keep]
    cal = pd.concat([old[~old["id"].isin(new["id"])], new], ignore_index=True).sort_values(["date", "time"])
    cal.to_csv(path, index=False, compression="gzip")
    print(f"calendar: {len(new)} rows re-pulled since {first}, {len(cal)} in total, last {cal['date'].max()}")
    y = fetch(f"{BASE}/series?dataset=sovereign_yields&symbol=USGB2Y&start=2010-01-01&end={END}")
    pd.DataFrame(y)[["date", "value"]].to_csv(os.path.join(MACRO, "us2y_lse.csv"), index=False)
    print(f"US 2-year: {len(y)} days, last {y[-1]['date'] if y else '-'}")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    try:
        pull_macro()
    except Exception as e:                       # the board still builds without fresh macro data
        print("macro pull FAILED", e)
    if "--no-cot" not in sys.argv:
        c = pull_cot()
        json.dump(c, open(os.path.join(OUT, "cot.json"), "w"))
        print("COT rows", len(c), min(x["date"] for x in c), max(x["date"] for x in c))
    for name, (sym, ds) in PRICES.items():
        try:
            r = pull_candles(sym, ds)
        except Exception as e:
            print(f"{name:3s} {sym:11s} FAILED {e}")
            continue
        with open(os.path.join(OUT, name + ".csv"), "w") as f:
            f.write("ts,open,high,low,close\n")
            for x in r:
                f.write(f"{x['ts']},{x['open']},{x['high']},{x['low']},{x['close']}\n")
        print(f"{name:3s} {sym:11s} {len(r):5d} bars {r[0]['ts'][:10]} -> {r[-1]['ts'][:10]}"
              if r else f"{name} {sym} EMPTY", flush=True)
