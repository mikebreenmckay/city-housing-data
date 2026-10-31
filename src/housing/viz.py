"""Interactive Plotly charts shared by the dashboard (and usable from notebooks).

Colors come from a fixed categorical palette with separate light and dark steps.
Series take slots in a fixed order, and a metro keeps its color across charts.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from housing.metrics import COST_BURDEN_LINE

PALETTE = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
}
MUTED = {"light": "#b8b7b1", "dark": "#5c5b56"}
MAX_SERIES = len(PALETTE["light"])

# measure -> (label, plotly tick format, hover format)
MEASURES = {
    "payment_to_income": ("Mortgage payment / income", ".0%", ".1%"),
    "price_to_income": ("Home price / income", ".1f", ".2f"),
    "rent_to_income": ("Rent / income", ".0%", ".1%"),
    "home_value": ("Typical home value", "$,.0f", "$,.0f"),
    "rent": ("Typical monthly rent", "$,.0f", "$,.0f"),
    "median_income": ("Median household income", "$,.0f", "$,.0f"),
}
SHARE_MEASURES = {"payment_to_income", "rent_to_income"}


def _layout(fig: go.Figure, title: str, height: int = 450, **kwargs) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left"), height=height,
        margin=dict(l=10, r=10, t=50, b=10), hoverlabel=dict(namelength=-1),
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, title=None), **kwargs,
    )
    return fig


def color_map(metros: list[str], mode: str = "light") -> dict[str, str]:
    """Assign palette slots to metros in the order given (at most MAX_SERIES)."""
    return dict(zip(metros, PALETTE[mode]))


def ranking_bar(latest: pd.DataFrame, measure: str, focus: str, mode: str = "light") -> go.Figure:
    """Horizontal bars ranking metros on one measure, the focus metro highlighted."""
    label, tick, hover = MEASURES[measure]
    d = latest.sort_values(measure)
    colors = [PALETTE[mode][1] if m == focus else PALETTE[mode][0] for m in d["metro"]]
    fig = go.Figure(go.Bar(
        x=d[measure], y=d["metro"], orientation="h", marker=dict(color=colors, cornerradius=4),
        customdata=np.stack([d["median_income"], d["home_value"]], axis=1),
        hovertemplate=f"<b>%{{y}}</b><br>{label}: %{{x:{hover}}}<br>"
                      "Median income: %{customdata[0]:$,.0f}<br>Home value: %{customdata[1]:$,.0f}<extra></extra>",
    ))
    if measure in SHARE_MEASURES:
        fig.add_vline(x=COST_BURDEN_LINE, line_dash="dash", line_width=1,
                      annotation_text="30% cost-burden line", annotation_position="top")
    fig.update_xaxes(tickformat=tick, title=label)
    fig.update_yaxes(title=None)
    return _layout(fig, f"{label}, ranked", height=max(350, 22 * len(d) + 120), bargap=0.25)


def income_vs_costs(annual_metro: pd.DataFrame, mode: str = "light") -> go.Figure:
    """One metro's income, home value, rent and mortgage payment indexed to its first year,
    with the income estimate's 90% margin of error shaded."""
    d = annual_metro.sort_values("year")
    first = d["year"].iloc[0]
    base = d["median_income"].iloc[0]
    pal = PALETTE[mode]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(d["year"]) + list(d["year"][::-1]),
        y=list((d["median_income"] + d["median_income_moe"]) / base * 100)
          + list(((d["median_income"] - d["median_income_moe"]) / base * 100)[::-1]),
        fill="toself", fillcolor=pal[0], opacity=0.15, line=dict(width=0),
        hoverinfo="skip", name="Income margin of error (90%)",
    ))
    series = [("median_income", "Median household income"), ("home_value", "Home value"),
              ("rent", "Rent"), ("monthly_payment", "Mortgage payment")]
    for (col, name), color in zip(series, pal):
        fig.add_trace(go.Scatter(
            x=d["year"], y=d[f"{col}_index"], name=name, mode="lines+markers",
            line=dict(color=color, width=2), marker=dict(size=8),
            customdata=d[col], hovertemplate=f"{name}: %{{y:.0f}} (%{{customdata:$,.0f}})<extra></extra>",
        ))
    fig.add_hline(y=100, line_width=1, line_color=MUTED[mode])
    fig.update_xaxes(dtick=1, title=None)
    fig.update_yaxes(title=f"Index ({first} = 100)")
    return _layout(fig, f"Income vs housing costs ({first} = 100)", height=500, hovermode="x unified")


def growth_gap(annual: pd.DataFrame, focus: str, mode: str = "light") -> go.Figure:
    """Home value growth minus income growth since the first year, for each metro."""
    first, last = annual["year"].min(), annual["year"].max()
    d = annual[annual["year"] == last].assign(
        gap=lambda x: x["home_value_index"] - x["median_income_index"]).sort_values("gap")
    colors = [PALETTE[mode][1] if m == focus else PALETTE[mode][0] for m in d["metro"]]
    fig = go.Figure(go.Bar(
        x=d["gap"], y=d["metro"], orientation="h", marker=dict(color=colors, cornerradius=4),
        customdata=np.stack([d["home_value_index"] - 100, d["median_income_index"] - 100], axis=1),
        hovertemplate="<b>%{y}</b><br>Home values %{customdata[0]:+.0f}%<br>Income %{customdata[1]:+.0f}%"
                      "<br>Gap: %{x:+.0f} pts<extra></extra>",
    ))
    fig.add_vline(x=0, line_width=1, line_color=MUTED[mode])
    fig.update_xaxes(title=f"Home value growth − income growth, {first}–{last} (pts)")
    fig.update_yaxes(title=None)
    return _layout(fig, "Did home prices outrun incomes?",
                   height=max(350, 22 * len(d) + 120), bargap=0.25)


def trend_lines(monthly: pd.DataFrame, metros: list[str], value: str, indexed: bool,
                colors: dict[str, str]) -> go.Figure:
    """Monthly home value or rent for several metros, optionally indexed to the first month shown."""
    label, tick, hover = MEASURES[value]
    fig = go.Figure()
    for metro in metros:
        s = monthly[monthly["metro"] == metro].dropna(subset=[value]).sort_values("date")
        y = s[value] / s[value].iloc[0] * 100 if indexed else s[value]
        fmt = ".1f" if indexed else hover
        fig.add_trace(go.Scatter(
            x=s["date"], y=y, name=metro, mode="lines", line=dict(color=colors[metro], width=2),
            hovertemplate=f"{metro}: %{{y:{fmt}}}<extra></extra>",
        ))
    if indexed:
        start = monthly["date"].min()
        fig.update_yaxes(title=f"Index ({start:%b %Y} = 100)")
    else:
        fig.update_yaxes(title=label, tickformat=tick)
    fig.update_xaxes(title=None)
    return _layout(fig, label + (" (indexed)" if indexed else ""), hovermode="x unified")


def scatter(df: pd.DataFrame, x: str, y: str, focus: str, highlight: list[str], title: str,
            x_title: str, y_title: str, x_fmt: str, y_fmt: str, mode: str = "light",
            fit: bool = False, diagonal: bool = False) -> go.Figure:
    """Metros as points: highlighted metros in blue, the focus in orange, the rest muted."""
    pal = PALETTE[mode]
    fig = go.Figure()
    layers = [
        ("Other metros", ~df["metro"].isin(highlight + [focus]), MUTED[mode], 9),
        ("Comparison metros", df["metro"].isin(highlight) & (df["metro"] != focus), pal[0], 10),
        (focus, df["metro"] == focus, pal[1], 14),
    ]
    for name, mask, color, size in layers:
        g = df[mask]
        fig.add_trace(go.Scatter(
            x=g[x], y=g[y], mode="markers", name=name, text=g["metro"],
            marker=dict(color=color, size=size, line=dict(width=1.5, color="rgba(255,255,255,0.8)")),
            hovertemplate=f"<b>%{{text}}</b><br>{x_title}: %{{x:{x_fmt}}}<br>{y_title}: %{{y:{y_fmt}}}<extra></extra>",
        ))
    if fit:
        slope, intercept = np.polyfit(df[x], df[y], 1)
        xs = np.linspace(df[x].min(), df[x].max(), 20)
        fig.add_trace(go.Scatter(x=xs, y=slope * xs + intercept, mode="lines", name="Best fit",
                                 line=dict(color=MUTED[mode], dash="dash", width=1.5), hoverinfo="skip"))
    if diagonal:
        lo = min(df[x].min(), df[y].min())
        hi = max(df[x].max(), df[y].max())
        fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", name="Equal growth",
                                 line=dict(color=MUTED[mode], dash="dot", width=1.5), hoverinfo="skip"))
    fig.update_xaxes(title=x_title, tickformat=x_fmt.replace(".1", ".0"))
    fig.update_yaxes(title=y_title, tickformat=y_fmt.replace(".1", ".0"))
    return _layout(fig, title, height=500)
