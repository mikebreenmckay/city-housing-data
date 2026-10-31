"""Match Zillow metro names to Census CBSA codes.

Zillow labels a metro by its first principal city and state ("Dallas, TX"), while
the Census uses the full CBSA title ("Dallas-Fort Worth-Arlington, TX Metro Area").
Both start with the same first city and state, so that pair is the join key.
"""

import re

import pandas as pd


def _match_key(name: str) -> tuple[str, str]:
    name = re.sub(r" (Metro|Micro) Area$", "", name)
    cities, states = name.rsplit(", ", 1)
    first_city = re.split(r"[-/]", cities)[0].strip().lower()
    return first_city, states.split("-")[0]


def crosswalk(zillow_metros: pd.DataFrame, census_metros: pd.DataFrame, strict: bool = True) -> pd.DataFrame:
    """Return Zillow RegionID -> CBSA code.

    With strict=True, raises if any Zillow metro has no match; otherwise unmatched
    metros (mostly micropolitan areas, which census_metros excludes) are dropped.
    """
    z = zillow_metros[["RegionID", "RegionName"]].drop_duplicates().copy()
    c = census_metros.copy()
    z["key"] = z["RegionName"].map(_match_key)
    c["key"] = c["cbsa_name"].map(_match_key)
    merged = z.merge(c, on="key", how="left")
    missing = merged[merged["cbsa"].isna()]["RegionName"].tolist()
    if missing and strict:
        raise ValueError(f"No Census CBSA match for Zillow metros: {missing}")
    return merged.dropna(subset=["cbsa"])[["RegionID", "cbsa", "cbsa_name"]]
