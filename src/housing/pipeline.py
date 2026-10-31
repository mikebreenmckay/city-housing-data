"""Build the processed datasets in data/processed/.

metro_monthly.csv   one row per metro and month: home value, rent, mortgage rate
metro_annual.csv    one row per metro and year with Census income, population,
                    affordability and growth indexes
metro_latest.csv    the latest month of prices and rates against the latest Census income

Metros covered: the TOP_N largest, a FOCUS metro, and the PEERS metros closest
to the focus metro in population. The `group` column says which ("focus",
"peer" or "top"); a metro in more than one set takes the first of those.
"""

import numpy as np
import pandas as pd

from housing import metrics, metros, sources
from housing.paths import PROCESSED

TOP_N = 50
FOCUS = "Durham, NC"
PEERS = 10
FILES = {"monthly": "metro_monthly.csv", "annual": "metro_annual.csv", "latest": "metro_latest.csv"}


def _select_metros(candidates: pd.DataFrame, top_n: int, focus: str, n_peers: int) -> pd.DataFrame:
    """Pick the top_n largest metros plus focus and its n_peers nearest in population."""
    if focus not in set(candidates["metro"]):
        raise ValueError(f"Focus metro {focus!r} not found; use Zillow's name, e.g. 'Durham, NC'")
    focus_pop = candidates.loc[candidates["metro"] == focus, "population"].iloc[0]
    others = candidates[candidates["metro"] != focus]
    # Nearest on a log scale, so 10% bigger and 10% smaller count the same.
    distance = (np.log(others["population"]) - np.log(focus_pop)).abs()
    peers = others.loc[distance.nsmallest(n_peers).index, "RegionID"]
    top = candidates.nsmallest(top_n, "SizeRank")["RegionID"]

    out = candidates.copy()
    out["group"] = np.select(
        [out["metro"] == focus, out["RegionID"].isin(peers), out["RegionID"].isin(top)],
        ["focus", "peer", "top"], default="",
    )
    return out[out["group"] != ""]


def build(top_n: int = TOP_N, focus: str = FOCUS, n_peers: int = PEERS,
          refresh: bool = False) -> dict[str, pd.DataFrame]:
    home_values = sources.zillow_home_values(refresh)
    rents = sources.zillow_rents(refresh)
    rates = sources.mortgage_rates(refresh)
    census = sources.acs_median_income(refresh).merge(
        sources.acs_population(refresh).drop(columns="population_moe"), on=["cbsa", "year"], how="left")
    latest_income_year = int(census["year"].max())

    zillow_metros = home_values[["RegionID", "SizeRank", "RegionName", "StateName"]].drop_duplicates()
    # Match against each year's own metro list: the 2023 redelineation renumbered
    # some CBSAs (Cleveland 17460 -> 17410), so codes aren't stable across years.
    xwalk = pd.concat(
        [metros.crosswalk(zillow_metros, sources.acs_metro_names(y, refresh), strict=False).assign(year=y)
         for y in sorted(census["year"].unique())],
        ignore_index=True,
    )
    census = census.merge(xwalk[["cbsa", "year", "RegionID"]], on=["cbsa", "year"]).drop(columns="cbsa")
    current = xwalk[xwalk["year"] == latest_income_year].drop(columns="year")

    candidates = (
        zillow_metros.rename(columns={"RegionName": "metro", "StateName": "state"})
        .merge(current, on="RegionID")
        .merge(census.loc[census["year"] == latest_income_year, ["RegionID", "population"]], on="RegionID")
    )
    selected = _select_metros(candidates, top_n, focus, n_peers).drop(columns="population")

    # Monthly panel: Zillow dates are month ends; average the weekly rates within each month.
    monthly_rates = rates.set_index("date")["rate_30yr"].resample("ME").mean().reset_index()
    monthly = (
        selected.merge(home_values[["RegionID", "date", "home_value"]], on="RegionID")
        .merge(rents[["RegionID", "date", "rent"]], on=["RegionID", "date"], how="left")
        .merge(monthly_rates, on="date", how="left")
    )
    monthly["year"] = monthly["date"].dt.year

    # Annual: average each year's months, then join that year's Census income and population.
    id_cols = ["RegionID", "SizeRank", "metro", "state", "group", "cbsa", "cbsa_name", "year"]
    annual = monthly.groupby(id_cols, as_index=False)[["home_value", "rent", "rate_30yr"]].mean()
    annual = metrics.add_affordability(annual.merge(census, on=["RegionID", "year"]))
    annual = metrics.add_growth_indexes(annual)

    # Latest: newest month of prices and rates, newest year of income.
    last = monthly[monthly["date"] == monthly["date"].max()]
    latest = last.merge(census[census["year"] == latest_income_year].drop(columns="year"), on="RegionID")
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
