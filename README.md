# Bias Board

Weekly directional bias for 24 futures markets (metals, energy, currencies, US stock indices, grains, softs and cattle), plus a separate Quant strategies view, from two engines:

- **COT positioning**: retail (non-reportables) faded and commercials followed at extremes of five nested lookbacks
  (6 months to 5 years, lit at the 80th/20th percentile), with the track record of past cases.
- **Seasonality**: Seasonax-style windows counted in trading days (`bias/seasonal.py`): win ratio over the
  15 prior years, at least 12 of 15, 5–30 trading days long, entry within −2 to +8 weeks; trend-removed count shown too.
- **Quant strategies** (`bias/events.py`, own view in the app): fixed calendar rules with a known cause, validated on the
  20 years after publication: turn of the month, first trading day, Halloween and FOMC window on the S&P, Nasdaq and Dow,
  and the corn pre-harvest short. FOMC dates in `data/fomc_dates.csv`.
- Coffee and live cattle use TradingView back-adjusted futures history (`data/history/`, to May 2026) continued with
  LSE daily prices; their win ratios are exact, % averages approximate.

**The verdict** (`bias/verdict.py`, tested walk-forward 2019–26 in `research/verdict_test.py`, results in
`data/research/verdict.json`): the COT read carries a bias on its own (held at least 8 weeks outside currencies);
a seasonal window counts next to COT at any size, and alone only on agricultural markets with a usual move of at
least 3 normal daily moves. Gates: slow COT signals skipped, a COT minimum record outside currencies, Bernd's evidence
gate on currencies, US indices long-only, and "move done" (the US macro score is shown as context only since
October 2026: as a gate it cancelled the better verdicts, `research/macro_strength_test.py`). Rerun with
`SKIP_SLOW=1 python research/verdict_test.py`. Sugar and coffee prices continue on Yahoo Finance front-month futures
(made continuous across rolls) since LSE stopped them in October 2026.

The site has two pages: `index.html`, the interactive board, and `outlook.html`, the full written outlook.

## How it updates

`.github/workflows/weekly.yml` runs Mon–Fri after the US close and every Saturday at 07:00 UTC, after the Friday CFTC release (the Saturday run also records the live verdicts):

1. `bias/pull.py` pulls COT and daily spot prices from the London Strategic Edge API.
2. `bias/build.py` builds the outlook (`site/outlook.html`).
3. `bias/app.py` builds the board (`site/index.html`).
4. The `site/` folder is deployed to GitHub Pages.

It can also be started by hand from the Actions tab, optionally with a past report date to rebuild that week.

## Setup

1. Repository secret `LSE_KEY` = your London Strategic Edge API key (Settings → Secrets and variables → Actions).
2. Settings → Pages → Source: **GitHub Actions**.

## Running locally

```bash
pip install -r requirements.txt
echo "<your key>" > .lse_key
python bias/pull.py && python bias/build.py && python bias/app.py
open site/index.html
```

`OUTLOOK_DATE=2026-10-11 python bias/build.py` rebuilds the board as of a past date (COT and prices are cut at that date).

## Data notes

- `data/cftc/` holds CFTC legacy COT history. It back-fills the years before 2015 and is used throughout for WTI and
  natural gas, because the LSE series for those two is a different contract before 2026.
- Yen, franc and Canadian dollar spot are inverted to futures direction; the dollar index is rebuilt from its six legs.

Educational content, not financial advice.
