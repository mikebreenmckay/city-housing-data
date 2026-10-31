"""Download and parse the raw data sources.

Every source is a public file that needs no API key. Downloads are cached in
data/raw/; pass refresh=True to fetch them again.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import requests

from housing.paths import RAW

ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
ZORI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zori/"
    "Metro_zori_uc_sfrcondomfr_sm_month.csv"
)
PMMS_URL = "https://www.freddiemac.com/pmms/docs/PMMS_history.csv"
ACS_BASE = "https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF"
# The table-based ACS summary files start with the 2021 release.
ACS_FIRST_YEAR = 2021


def download(url: str, name: str, refresh: bool = False) -> Path | None:
    """Fetch url into data/raw/name. Returns None if the file doesn't exist upstream."""
    path = RAW / name
    if path.exists() and not refresh:
        return path
    RAW.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=120)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def _zillow_long(path: Path, value_name: str) -> pd.DataFrame:
    wide = pd.read_csv(path)
    wide = wide[wide["RegionType"] == "msa"]
    ids = ["RegionID", "SizeRank", "RegionName", "StateName"]
    long = wide.melt(id_vars=ids, value_vars=wide.columns[5:], var_name="date", value_name=value_name)
    long["date"] = pd.to_datetime(long["date"])
    return long.dropna(subset=[value_name])


def zillow_home_values(refresh: bool = False) -> pd.DataFrame:
    """Zillow Home Value Index (typical home value, mid-tier, smoothed, seasonally adjusted)."""
    return _zillow_long(download(ZHVI_URL, "zhvi_metro.csv", refresh), "home_value")


def zillow_rents(refresh: bool = False) -> pd.DataFrame:
    """Zillow Observed Rent Index (typical market rent, all home types, smoothed)."""
    return _zillow_long(download(ZORI_URL, "zori_metro.csv", refresh), "rent")


def mortgage_rates(refresh: bool = False) -> pd.DataFrame:
    """Freddie Mac weekly average 30-year fixed mortgage rate, in percent."""
    df = pd.read_csv(download(PMMS_URL, "pmms.csv", refresh), usecols=["date", "pmms30"])
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y")
    return df.rename(columns={"pmms30": "rate_30yr"}).dropna()


def acs_metro_names(year: int, refresh: bool = False) -> pd.DataFrame:
    """CBSA code and official name for every metropolitan statistical area in an ACS release."""
    url = f"{ACS_BASE.format(year=year)}/documentation/Geos{year}1YR.txt"
    path = download(url, f"acs_geos_{year}.txt", refresh)
    geos = pd.read_csv(path, sep="|", dtype=str, usecols=["SUMLEVEL", "CBSA", "NAME"])
    geos = geos[(geos["SUMLEVEL"] == "310") & geos["NAME"].str.endswith("Metro Area")]
    return geos[["CBSA", "NAME"]].rename(columns={"CBSA": "cbsa", "NAME": "cbsa_name"})


def acs_median_income(refresh: bool = False) -> pd.DataFrame:
    """ACS 1-year median household income (table B19013) for each metro and year."""
    frames = []
    for year in range(ACS_FIRST_YEAR, date.today().year + 1):
        url = f"{ACS_BASE.format(year=year)}/data/1YRData/acsdt1y{year}-b19013.dat"
        path = download(url, f"acs_b19013_{year}.dat", refresh)
        if path is None:
            continue
        df = pd.read_csv(path, sep="|", dtype={"GEO_ID": str})
        df = df[df["GEO_ID"].str.startswith("310")]
        frames.append(pd.DataFrame({
            "cbsa": df["GEO_ID"].str[-5:],
            "year": year,
            "median_income": pd.to_numeric(df["B19013_E001"], errors="coerce"),
        }))
    return pd.concat(frames, ignore_index=True).dropna()
