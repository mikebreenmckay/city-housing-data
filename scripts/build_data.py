"""Download the raw sources and rebuild data/processed/.

    python scripts/build_data.py            # use cached downloads where present
    python scripts/build_data.py --refresh  # re-download everything
"""

import argparse

from housing import build
from housing.pipeline import TOP_N


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="re-download raw files")
    parser.add_argument("--top", type=int, default=TOP_N, help=f"number of largest metros (default {TOP_N})")
    args = parser.parse_args()

    tables = build(top_n=args.top, refresh=args.refresh)
    for name, df in tables.items():
        print(f"{name:8s} {len(df):>7,} rows")
    latest = tables["latest"]
    print(f"\nLatest month: {latest['date'].max():%Y-%m}, income year: {latest['income_year'].iloc[0]}")
    cols = ["metro", "home_value", "median_income", "price_to_income", "payment_to_income"]
    print("\nLeast affordable (mortgage payment share of income):")
    print(latest[cols].head(10).to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    main()
