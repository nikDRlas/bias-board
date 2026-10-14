# Bias Board

Weekly directional bias for 18 futures markets (metals, energy, currencies and US stock indices), from two engines:

- **COT positioning**: retail (non-reportables) faded and commercials followed at extremes of five nested lookbacks
  (6 months to 5 years, lit at the 80th/20th percentile), with the track record of past cases.
- **Seasonality**: Seasonax-style windows counted in trading days (`bias/seasonal.py`): win ratio over the
  15 prior years, at least 12 of 15, 5–63 trading days long, entry within −2 to +8 weeks; trend-removed count shown too.
- **Calendar events** for the stock indices (`bias/events.py`): turn of the month, first trading day, Halloween,
  FOMC window. Fixed in advance with a known cause; shown as information. FOMC dates in `data/fomc_dates.csv`.

**The verdict is the COT read.** Seasonality is shown as context only, because the walk-forward test in
`research/conflict_test.py` (results in `data/research/conflict.json`) found that the board's seasonal windows won
50% out of sample (2019–2026, 1,161 trades), the same whether COT agreed or not, while the COT read won about 54% over
8 weeks and kept that when the calendar pointed the other way. Rerun the test with `python research/conflict_test.py`.

The site has two pages: `index.html`, the interactive board, and `outlook.html`, the full written outlook.

## How it updates

`.github/workflows/weekly.yml` runs every Saturday at 07:00 UTC, after the Friday CFTC release:

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
