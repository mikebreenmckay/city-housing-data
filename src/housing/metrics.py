"""Affordability measures.

price_to_income    typical home value / median household income
rent_to_income     a year of typical rent / median household income
payment_to_income  monthly principal + interest on a 30-year fixed loan with
                   DOWN_PAYMENT down, as a share of monthly median income.
                   Excludes taxes, insurance and HOA, so real costs run higher.

A common rule of thumb treats 30% of income as the line for being cost-burdened.

Growth indexes (*_index) set each metro's first year to 100, so income and
housing costs can be compared on one scale: if home_value_index outruns
median_income_index, homes are getting less affordable there.
"""

import pandas as pd

DOWN_PAYMENT = 0.20
LOAN_YEARS = 30
COST_BURDEN_LINE = 0.30


def monthly_payment(principal: pd.Series, annual_rate_pct: pd.Series, years: int = LOAN_YEARS) -> pd.Series:
    r = annual_rate_pct / 100 / 12
    n = years * 12
    return principal * r / (1 - (1 + r) ** -n)


def add_affordability(df: pd.DataFrame) -> pd.DataFrame:
    """Add affordability columns to a frame with home_value, rent, median_income and rate_30yr."""
    out = df.copy()
    monthly_income = out["median_income"] / 12
    payment = monthly_payment(out["home_value"] * (1 - DOWN_PAYMENT), out["rate_30yr"])
    out["monthly_payment"] = payment
    out["price_to_income"] = out["home_value"] / out["median_income"]
    out["rent_to_income"] = out["rent"] * 12 / out["median_income"]
    out["payment_to_income"] = payment / monthly_income
    return out


GROWTH_COLUMNS = ["median_income", "home_value", "rent", "monthly_payment"]


def add_growth_indexes(annual: pd.DataFrame, columns: list[str] = GROWTH_COLUMNS) -> pd.DataFrame:
    """Add <column>_index: each metro's value relative to its first year, which is 100."""
    out = annual.sort_values(["RegionID", "year"]).copy()
    for col in columns:
        out[f"{col}_index"] = out[col] / out.groupby("RegionID")[col].transform("first") * 100
    return out
