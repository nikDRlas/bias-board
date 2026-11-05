#!/usr/bin/env python3
"""Pull the CFTC's newer COT reports (futures only) for the board's markets into data/cftc_new/ (2026-11-05):
  disaggregated (dataset 72hh-3qpy, commodities): producer/merchant, swap dealers, managed money, other reportables
  TFF           (dataset gpe5-46if, currencies + indices): dealers, asset managers, leveraged funds, other reportables
Both start June 2006. Same contract codes as the legacy report (bias/pull.py CFTC_CODES). Run: LSE_KEY=x python3 research/cot_new_pull.py

TEST 2026-11-05 (research/verdict_test.py SKIP_SLOW=1 with bias/core.py COT_SRC / COT_SRC_SCOPE; data/research/cot_new.json):
  legacy (board)                        572 verdicts  +1052%  (2019-22 +510 / 2023-26 +542)  DD -150
  legacy cut to 2006-06 (fair base)     535           +797    (+376 / +421)
  commodities producer/merchant vs managed money (pm) vs legacy06 on the same history: +264 vs +534 (19-22 +112 vs +262,
      23-26 +152 vs +272) -> worse in both halves, metals & energy almost gone (+61 vs +200)
  currencies+indices dealers vs leveraged funds (pm)  +192 vs +263 (+70/+122 vs +113/+149): worse both halves
  currencies+indices dealers+asset mgrs vs lev+other (wide) +248 vs +263 (+97/+151 vs +113/+149): 19-22 worse
  currencies+indices asset managers vs lev funds (am)  63 verdicts +66: far fewer signals, worse
  disaggregated "wide" (producer+swap vs managed money+other) = the legacy groups exactly (checked on GC), so the only
  new commodity grouping is producer vs managed money. VERDICT: legacy stays; no newer grouping beats it in either half.
  Side finding: cutting the legacy history to 2006 alone costs commodities +791 -> +534 (COT record minimum and the
  calendar's COT-agree years lose their 2003-06 cases) -> those rules are sensitive to which old cases they see.
AS AN ADD-ON (verdicts the newer report gives where legacy has none on that market; drift control = same market, side
and length from every start day of the period):
  producer vs managed money (all mkts)  71 new, -32% (19-22 -39 / 23-26 +7); legacy+new +1020 vs +1052 -> no
  TFF dealers+asset mgrs vs lev+other   95 new, +90% (+33/+57); legacy+new +1142% (+543/+599) -- looked good, BUT
     indices    14 new (13 COT+calendar, 14 different dates) excess over drift +1.33%/verdict t2.1, both halves; HOLDOUT
                2012-18 (research/verdict_test.py WF_START=2012-01-07): 15 new, excess -0.10% -> no edge out of sample
     currencies 81 new, excess +0.49 (19-22 +0.0 / 23-26 +0.49, mostly 6C); holdout 34 new +0.67 t2.4 -> fails 2019-22
  TFF asset mgrs vs lev funds           40 new, +22% (+9/+13); 3 index verdicts -> too thin
  control: index calendar windows allowed alone (legacy COT) 37 new, excess -0.99 -> the TFF read is not just a calendar
  switch, but its index gain does not survive the holdout. VERDICT: no add-on either.
MORE COMMODITY GROUPINGS (COT_SRC_SCOPE=cmdty; fair base = legacy cut to 2006: 2019-26 +534% (+262/+272), holdout
2012-18 -100% (-145/+45); board legacy +791 / holdout -66):
                           replacement 2019-26     holdout 2012-18     add-on (new setups) 2019-26
  producer vs MM (pm)      +264 (+112/+152)         -127               30 new  -88 (-81/-7)
  prod+swap vs MM only     +590 (+267/+323)         -90 (-104/+14)     44 new  -10 (-47/+38)
  producer vs MM+other     +238 (+93/+145)          -255               31 new  +18 (-39/+57)
  swap dealers vs MM       +231 (+240/-10)          -87                47 new  -90 (-31/-58)
Only prod+swap vs MM (= legacy commercials, funds = managed money instead of all non-commercials) edges the fair base
(+56, 19-22 only +5; holdout -90 vs -100) - within noise, and it cannot use the pre-2006 history that is worth +257 on
the board. No add-on positive in both halves. VERDICT: nothing for commodities."""
import json, os, subprocess, sys, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bias"))
from pull import CFTC_CODES                            # noqa: E402
import core as C                                       # noqa: E402
OUT = os.path.join(HERE, "..", "data", "cftc_new")
DIS = ("72hh-3qpy", ["prod_merc_positions_long", "prod_merc_positions_short", "swap_positions_long_all", "swap__positions_short_all",
                     "m_money_positions_long_all", "m_money_positions_short_all", "other_rept_positions_long", "other_rept_positions_short",
                     "nonrept_positions_long_all", "nonrept_positions_short_all", "open_interest_all"])
TFF = ("gpe5-46if", ["dealer_positions_long_all", "dealer_positions_short_all", "asset_mgr_positions_long", "asset_mgr_positions_short",
                     "lev_money_positions_long", "lev_money_positions_short", "other_rept_positions_long", "other_rept_positions_short",
                     "nonrept_positions_long_all", "nonrept_positions_short_all", "open_interest_all"])
os.makedirs(OUT, exist_ok=True)
for k, code in CFTC_CODES.items():
    ds, fields = TFF if C.M[k][3] in ("FX", "Indices") or k == "DX" else DIS
    q = urllib.parse.urlencode({"$where": f"cftc_contract_market_code='{code}'", "$select": "report_date_as_yyyy_mm_dd," + ",".join(fields),
                                "$order": "report_date_as_yyyy_mm_dd", "$limit": "5000"})
    rows = json.loads(subprocess.run(["curl", "-s", "-m", "180", f"https://publicreporting.cftc.gov/resource/{ds}.json?{q}"],
                                     capture_output=True, text=True).stdout)
    tag = "tff" if ds == TFF[0] else "dis"
    json.dump(rows, open(os.path.join(OUT, f"{k}_{tag}.json"), "w"))
    miss = sum(any(f not in r for f in fields) for r in rows)
    print(f"{k:3s} {tag} {len(rows):4d} reports {rows[0]['report_date_as_yyyy_mm_dd'][:10]} .. {rows[-1]['report_date_as_yyyy_mm_dd'][:10]}  rows with a missing field: {miss}")
