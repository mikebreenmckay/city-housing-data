"""Download the raw sources and rebuild data/processed/.

    python scripts/build_data.py            # use cached downloads where present
    python scripts/build_data.py --refresh  # re-download everything
    python scripts/build_data.py --focus "Boise City, ID" --peers 15
"""

import argparse

from housing import build
from housing.pipeline import FOCUS, PEERS, TOP_N


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="re-download raw files")
    parser.add_argument("--top", type=int, default=TOP_N, help=f"number of largest metros (default {TOP_N})")
    parser.add_argument("--focus", default=FOCUS, help=f"metro to compare against its peers (default {FOCUS!r})")
    parser.add_argument("--peers", type=int, default=PEERS, help=f"metros nearest the focus in population (default {PEERS})")
    args = parser.parse_args()

    tables = build(top_n=args.top, focus=args.focus, n_peers=args.peers, refresh=args.refresh)
    for name, df in tables.items():
        print(f"{name:8s} {len(df):>7,} rows")
    latest = tables["latest"]
    print(f"\nLatest month: {latest['date'].max():%Y-%m}, income year: {latest['income_year'].iloc[0]}")
    cols = ["metro", "population", "home_value", "median_income", "price_to_income", "payment_to_income"]
    print(f"\n{args.focus} and its peers (mortgage payment share of income):")
    peers = latest[latest["group"].isin(["focus", "peer"])]
    print(peers[cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    main()
