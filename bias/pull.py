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
    "SB": ("SUGAR/USD", "commodity"),          # only needed to rebuild DXY from its legs
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


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
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
