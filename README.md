# City Housing Data

How affordable is housing in the 50 largest US metro areas, and how has that changed?
This project joins Zillow home values and rents with Census household income and
Freddie Mac mortgage rates to measure what a typical home costs a typical household.

![Mortgage payment as a share of median household income, 50 largest metros](images/payment_to_income.png)

## Findings so far (September 2026 prices, 2025 income)

- In **18 of 50 metros** the mortgage on a typical home (20% down, 30-year fixed) takes more
  than 30% of median household income, before taxes and insurance.
- Los Angeles (60%), San Jose (58%), San Diego (53%) and San Francisco (52%) are the least
  affordable; Pittsburgh (18%), Oklahoma City and St. Louis are the most.
- From 2021 to 2025 the median metro's payment-to-income rose about **9 percentage points**,
  driven mostly by mortgage rates roughly doubling.
- Owning a typical home costs more each month than renting one in **39 of 50 metros**.

See [notebooks/01_affordability.ipynb](notebooks/01_affordability.ipynb) for the charts and full table.

## Data sources

All are public downloads with no API key required.

| Source | What | Frequency |
|---|---|---|
| [Zillow Home Value Index](https://www.zillow.com/research/data/) | Typical home value (mid-tier, smoothed, seasonally adjusted) | Monthly, 2000– |
| [Zillow Observed Rent Index](https://www.zillow.com/research/data/) | Typical market rent | Monthly, 2015– |
| [Census ACS 1-year](https://www.census.gov/programs-surveys/acs/data/summary-file.html), table B19013 | Median household income by metro | Annual, 2021– |
| [Freddie Mac PMMS](https://www.freddiemac.com/pmms) | Average 30-year fixed mortgage rate | Weekly |

## Measures

| Measure | Definition |
|---|---|
| `price_to_income` | Home value ÷ median household income |
| `rent_to_income` | 12 × monthly rent ÷ median household income |
| `payment_to_income` | Monthly principal + interest (20% down, 30-year fixed) ÷ monthly median income |

Zillow labels metros by first city ("Dallas, TX"); they're matched to Census CBSA codes by
first city and state in each year's own metro list, since the 2023 redelineation renumbered some
metros (e.g. Cleveland 17460 → 17410).

## Project layout

```
src/housing/        reusable package (sources, metro matching, metrics, pipeline)
scripts/            build_data.py: download sources and rebuild data/processed/
data/processed/     tidy CSVs: metro_monthly, metro_annual, metro_latest (committed)
data/raw/           cached downloads (git-ignored)
notebooks/          analysis notebooks
```

The `housing` package returns plain DataFrames, so a dashboard (e.g. Streamlit) can sit on
top of `housing.load_processed()` without changing the pipeline.

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python scripts/build_data.py   # add --refresh to re-download, --top N for more metros
jupyter notebook notebooks/
```

## Ideas for next steps

- Backfill income before 2021 (Census API, needs a free key) for a pre-pandemic baseline
- Add property tax and insurance to the monthly cost
- Interactive dashboard: pick metros, compare trends, map affordability
- Supply side: Census building permits vs population growth
