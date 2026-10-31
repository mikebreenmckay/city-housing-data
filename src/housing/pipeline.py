"""Build the processed datasets in data/processed/.

metro_monthly.csv   one row per metro and month: home value, rent, mortgage rate
metro_annual.csv    one row per metro and year with Census income and affordability
metro_latest.csv    the latest month of prices and rates against the latest Census income
"""

import pandas as pd

from housing import metrics, metros, sources
from housing.paths import PROCESSED

TOP_N = 50
FILES = {"monthly": "metro_monthly.csv", "annual": "metro_annual.csv", "latest": "metro_latest.csv"}


def _top_metros(home_values: pd.DataFrame, n: int) -> pd.DataFrame:
    ranks = home_values[["RegionID", "SizeRank", "RegionName", "StateName"]].drop_duplicates()
    return ranks.sort_values("SizeRank").head(n).rename(columns={"RegionName": "metro", "StateName": "state"})


def build(top_n: int = TOP_N, refresh: bool = False) -> dict[str, pd.DataFrame]:
    home_values = sources.zillow_home_values(refresh)
    rents = sources.zillow_rents(refresh)
    rates = sources.mortgage_rates(refresh)
    income = sources.acs_median_income(refresh)
    latest_income_year = int(income["year"].max())

    top = _top_metros(home_values, top_n)
    # Match against each year's own metro list: the 2023 redelineation renumbered
    # some CBSAs (Cleveland 17460 -> 17410), so codes aren't stable across years.
    zillow_names = top.rename(columns={"metro": "RegionName"})
    xwalk = pd.concat(
        [metros.crosswalk(zillow_names, sources.acs_metro_names(y, refresh)).assign(year=y)
         for y in sorted(income["year"].unique())],
        ignore_index=True,
    )
    income = income.merge(xwalk[["cbsa", "year", "RegionID"]], on=["cbsa", "year"]).drop(columns="cbsa")
    current = xwalk[xwalk["year"] == latest_income_year].drop(columns="year")
    top = top.merge(current, on="RegionID")

    # Monthly panel: Zillow dates are month ends; average the weekly rates within each month.
    monthly_rates = rates.set_index("date")["rate_30yr"].resample("ME").mean().reset_index()
    monthly = (
        top.merge(home_values[["RegionID", "date", "home_value"]], on="RegionID")
        .merge(rents[["RegionID", "date", "rent"]], on=["RegionID", "date"], how="left")
        .merge(monthly_rates, on="date", how="left")
    )
    monthly["year"] = monthly["date"].dt.year

    # Annual: average each year's months, then join that year's Census income.
    id_cols = ["RegionID", "SizeRank", "metro", "state", "cbsa", "cbsa_name", "year"]
    annual = monthly.groupby(id_cols, as_index=False)[["home_value", "rent", "rate_30yr"]].mean()
    annual = metrics.add_affordability(annual.merge(income, on=["RegionID", "year"]))

    # Latest: newest month of prices and rates, newest year of income.
    last = monthly[monthly["date"] == monthly["date"].max()]
    latest = last.merge(income[income["year"] == latest_income_year].drop(columns="year"), on="RegionID")
    latest = metrics.add_affordability(latest).assign(income_year=latest_income_year)

    tables = {
        "monthly": monthly.drop(columns="year"),
        "annual": annual,
        "latest": latest.drop(columns="year").sort_values("payment_to_income", ascending=False),
    }
    PROCESSED.mkdir(parents=True, exist_ok=True)
    for key, df in tables.items():
        df.to_csv(PROCESSED / FILES[key], index=False)
    return tables


def load_processed() -> dict[str, pd.DataFrame]:
    """Read the processed CSVs (run build() or scripts/build_data.py first)."""
    tables = {}
    for key, name in FILES.items():
        dates = ["date"] if key != "annual" else None
        tables[key] = pd.read_csv(PROCESSED / name, dtype={"cbsa": str}, parse_dates=dates)
    return tables
