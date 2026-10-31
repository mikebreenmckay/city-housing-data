"""City housing affordability dashboard.

    streamlit run app/dashboard.py

Reads data/processed/ (rebuild it with scripts/build_data.py).
"""

import numpy as np
import pandas as pd
import streamlit as st

from housing import load_processed, viz
from housing.pipeline import FOCUS

st.set_page_config(page_title="City Housing Affordability", page_icon="🏠", layout="wide")


@st.cache_data
def load() -> dict[str, pd.DataFrame]:
    return load_processed()


def nearest_in_population(latest: pd.DataFrame, focus: str, n: int) -> list[str]:
    """The n metros closest to focus in population (log scale), within this dataset."""
    pop = latest.set_index("metro")["population"]
    distance = (np.log(pop.drop(focus)) - np.log(pop[focus])).abs()
    return distance.nsmallest(n).index.tolist()


data = load()
monthly, annual, latest = data["monthly"], data["annual"], data["latest"]
first_year, last_year = int(annual["year"].min()), int(annual["year"].max())
as_of = latest["date"].max()
mode = "dark" if st.context.theme.type == "dark" else "light"
metros = sorted(latest["metro"])

st.title("City Housing Affordability")
st.caption(
    f"Zillow prices and rents through {as_of:%B %Y} · Census ACS median household income {first_year}–{last_year} · "
    "Freddie Mac 30-year mortgage rates. Mortgage payment assumes 20% down and excludes taxes and insurance."
)

# --- Controls, one row above everything they affect ---
c1, c2, c3 = st.columns([2, 2, 2])
focus = c1.selectbox("Focus metro", metros, index=metros.index(FOCUS) if FOCUS in metros else 0)
compare_to = c2.radio("Compare with", ["10 closest in population", "50 largest metros", "All metros"], horizontal=True)
measure = c3.selectbox("Affordability measure", ["payment_to_income", "price_to_income", "rent_to_income"],
                       format_func=lambda m: viz.MEASURES[m][0])

if compare_to == "10 closest in population":
    cohort = [focus] + nearest_in_population(latest, focus, 10)
elif compare_to == "50 largest metros":
    cohort = sorted(set(latest.loc[latest["group"] == "top", "metro"]) | {focus})
else:
    cohort = metros
peers = [m for m in cohort if m != focus]

# --- Headline numbers for the focus metro ---
f_now = latest[latest["metro"] == focus].iloc[0]
f_annual = annual[annual["metro"] == focus].sort_values("year")
f_first = f_annual.iloc[0]
cohort_median = latest.loc[latest["metro"].isin(peers), measure].median()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Mortgage payment / income", f"{f_now['payment_to_income']:.0%}",
          f"{(f_now['payment_to_income'] - f_first['payment_to_income']) * 100:+.0f} pts since {first_year}",
          delta_color="inverse", border=True)
k2.metric("Home price / income", f"{f_now['price_to_income']:.1f}×",
          f"{f_now['price_to_income'] - f_first['price_to_income']:+.1f} since {first_year}",
          delta_color="inverse", border=True)
k3.metric("Rent / income", f"{f_now['rent_to_income']:.0%}",
          f"{(f_now['rent_to_income'] - f_first['rent_to_income']) * 100:+.0f} pts since {first_year}",
          delta_color="inverse", border=True)
k4.metric(f"Median household income ({last_year})", f"${f_now['median_income']:,.0f}",
          f"{f_now['median_income'] / f_first['median_income'] - 1:+.0%} since {first_year}", border=True,
          help=f"ACS 1-year estimate, 90% margin of error ±${f_now['median_income_moe']:,.0f}")

fmt = "{:.0%}" if measure in viz.SHARE_MEASURES else "{:.1f}"
rank = int((latest.loc[latest["metro"].isin(cohort), measure] > f_now[measure]).sum()) + 1
st.markdown(
    f"**{focus}** ranks **{rank} of {len(cohort)}** least affordable on {viz.MEASURES[measure][0].lower()} "
    f"({fmt.format(f_now[measure])} vs a comparison median of {fmt.format(cohort_median)})."
)

tab_rank, tab_income, tab_trends, tab_rel, tab_data = st.tabs(
    ["Ranking", "Income vs costs", "Price & rent trends", "Relationships", "Data"])

with tab_rank:
    st.plotly_chart(viz.ranking_bar(latest[latest["metro"].isin(cohort)], measure, focus, mode),
                    width="stretch")

with tab_income:
    left, right = st.columns(2)
    left.plotly_chart(viz.income_vs_costs(f_annual, mode), width="stretch")
    left.caption("Shaded band: the income estimate's 90% margin of error. A move inside the band may be survey noise.")
    right.caption("Right of zero: home values grew faster than incomes since the first year.")
    right.plotly_chart(viz.growth_gap(annual[annual["metro"].isin(cohort)], focus, mode), width="stretch")
    table = f_annual.set_index("year")[["median_income", "median_income_moe", "home_value", "rent",
                                       "rate_30yr", "monthly_payment", "payment_to_income"]]
    st.dataframe(table, column_config={
        "median_income": st.column_config.NumberColumn("Median income", format="$%,.0f"),
        "median_income_moe": st.column_config.NumberColumn("Income ± (90%)", format="$%,.0f"),
        "home_value": st.column_config.NumberColumn("Home value", format="$%,.0f"),
        "rent": st.column_config.NumberColumn("Monthly rent", format="$%,.0f"),
        "rate_30yr": st.column_config.NumberColumn("30-yr rate", format="%.2f%%"),
        "monthly_payment": st.column_config.NumberColumn("Mortgage payment", format="$%,.0f"),
        "payment_to_income": st.column_config.NumberColumn("Payment / income", format="percent", step=0.001),
    })

with tab_trends:
    t1, t2, t3, t4 = st.columns([3, 1, 1, 1])
    default = [focus] + nearest_in_population(latest, focus, 3)
    chosen = t1.multiselect(f"Metros (up to {viz.MAX_SERIES})", metros, default=default, max_selections=viz.MAX_SERIES)
    value = t2.radio("Show", ["home_value", "rent"], format_func=lambda v: viz.MEASURES[v][0])
    indexed = t3.toggle("Indexed", value=True, help="Start of the period = 100")
    start = t4.selectbox("From", [2000, 2010, 2015, 2019, 2020, 2021], index=4)
    if chosen:
        m = monthly[monthly["date"].dt.year >= start]
        st.plotly_chart(viz.trend_lines(m, chosen, value, indexed, viz.color_map(chosen, mode)),
                        width="stretch")
        if value == "rent" and start < 2015:
            st.caption("Zillow's rent index starts in 2015.")

with tab_rel:
    w = annual[annual["year"] == last_year].assign(
        income_growth=lambda d: d["median_income_index"] / 100 - 1,
        value_growth=lambda d: d["home_value_index"] / 100 - 1,
    )
    r_level = np.corrcoef(w["median_income"], w["home_value"])[0, 1]
    r_growth = np.corrcoef(w["income_growth"], w["value_growth"])[0, 1]
    left, right = st.columns(2)
    left.plotly_chart(viz.scatter(
        w, "median_income", "home_value", focus, peers,
        f"Higher-income metros have pricier homes (r = {r_level:.2f})",
        f"Median household income ({last_year})", f"Typical home value ({last_year})", "$,.0f", "$,.0f",
        mode, fit=True), width="stretch")
    left.caption("Above the fit line: homes are expensive for the local income level.")
    right.plotly_chart(viz.scatter(
        w, "income_growth", "value_growth", focus, peers,
        f"Income growth vs home value growth, {first_year}–{last_year} (r = {r_growth:.2f})",
        "Income growth", "Home value growth", ".1%", ".1%", mode, diagonal=True), width="stretch")
    right.caption("Above the diagonal: home values grew faster than incomes.")

with tab_data:
    cols = ["metro", "group", "population", "median_income", "home_value", "rent", "rate_30yr",
            "price_to_income", "rent_to_income", "payment_to_income"]
    shown = latest.loc[latest["metro"].isin(cohort), cols].sort_values(measure, ascending=False)
    st.dataframe(shown, hide_index=True, column_config={
        "population": st.column_config.NumberColumn("Population", format="localized"),
        "median_income": st.column_config.NumberColumn("Median income", format="$%,.0f"),
        "home_value": st.column_config.NumberColumn("Home value", format="$%,.0f"),
        "rent": st.column_config.NumberColumn("Monthly rent", format="$%,.0f"),
        "rate_30yr": st.column_config.NumberColumn("30-yr rate", format="%.2f%%"),
        "price_to_income": st.column_config.NumberColumn("Price / income", format="%.1f"),
        "rent_to_income": st.column_config.NumberColumn("Rent / income", format="percent", step=0.001),
        "payment_to_income": st.column_config.NumberColumn("Payment / income", format="percent", step=0.001),
    })
    st.download_button("Download annual data (CSV)", annual[annual["metro"].isin(cohort)].to_csv(index=False),
                       file_name="metro_annual.csv", mime="text/csv")
