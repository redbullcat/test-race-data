"""race_pace_distribution.py — Race pace box plot and individual lap strip chart.

Replicates the formula1dashboard.com Race Pace + Lap Times views using Plotly.
Works for practice, qualifying, and race sessions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (
    apply_dark_layout, build_color_map, sort_cars,
    filter_top_percent, seconds_to_laptime, chart_export_buttons,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nice_tick_step(span: float) -> float:
    if span <= 5:   return 1.0
    if span <= 15:  return 2.0
    if span <= 30:  return 5.0
    if span <= 90:  return 10.0
    return 20.0


def _lap_time_yaxis(series: pd.Series) -> dict:
    """Build yaxis dict with lap-time-formatted tick labels."""
    y_min, y_max = series.min(), series.max()
    step = _nice_tick_step(y_max - y_min)
    tick_vals = list(np.arange(np.floor(y_min / step) * step, y_max + step, step))
    return dict(
        tickvals=tick_vals,
        ticktext=[seconds_to_laptime(v) for v in tick_vals],
        range=[y_min - step * 0.6, y_max + step * 0.6],
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def show_race_pace_distribution(
    df: pd.DataFrame,
    team_colors: dict,
    key_prefix: str = "rpd",
    session_label: str = "Race",
) -> None:
    """
    Render a pace distribution box plot and an individual lap strip chart.

    Parameters
    ----------
    df          : DataFrame with at minimum NUMBER, TEAM, LAP_TIME_SECONDS, LAP_NUMBER.
    team_colors : {team_name: hex_color} dict.
    key_prefix  : Unique prefix for Streamlit widget keys.
    session_label : Display label used in chart titles (e.g. "Race", "Practice").
    """
    st.subheader(f"{session_label} Pace Distribution")

    if "LAP_TIME_SECONDS" not in df.columns:
        st.info("Lap time data not available.")
        return

    # ── Shared filters ────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([3, 2, 2])

    all_cars = sort_cars(df["NUMBER"].dropna().unique())
    with col1:
        selected_cars = st.multiselect(
            "Cars", all_cars, default=all_cars, key=f"{key_prefix}_rpd_cars"
        )

    valid_laps = df["LAP_NUMBER"].dropna()
    if valid_laps.empty:
        st.warning("No lap number data.")
        return
    min_lap, max_lap = int(valid_laps.min()), int(valid_laps.max())

    with col2:
        lap_range = st.slider(
            "Lap range", min_lap, max_lap, (min_lap, max_lap),
            key=f"{key_prefix}_rpd_laps",
        )

    with col3:
        top_pct = st.slider(
            "Top lap %", 20, 100, 100, step=10,
            key=f"{key_prefix}_rpd_pct",
            help="Keep only the fastest N% of each car's laps — removes SC/FCY laps and traffic.",
        )

    dff = df[
        df["NUMBER"].isin(selected_cars) &
        df["LAP_NUMBER"].between(lap_range[0], lap_range[1])
    ].dropna(subset=["LAP_TIME_SECONDS"]).copy()

    if dff.empty:
        st.warning("No data for selected filters.")
        return

    if top_pct < 100:
        dff = filter_top_percent(dff, top_pct)

    # Sort cars by median pace (fastest left)
    median_order = (
        dff.groupby("NUMBER")["LAP_TIME_SECONDS"].median()
        .sort_values()
        .index.tolist()
    )

    color_map = build_color_map(dff, team_colors)
    yaxis = _lap_time_yaxis(dff["LAP_TIME_SECONDS"])

    # ── Box plot ──────────────────────────────────────────────────────────────
    st.markdown("#### Pace Distribution")
    fig_box = go.Figure()

    for number in median_order:
        car_df = dff[dff["NUMBER"] == number]
        if car_df.empty:
            continue
        team = car_df["TEAM"].iloc[0]
        color = color_map.get(team, "#888888")

        fig_box.add_trace(go.Box(
            y=car_df["LAP_TIME_SECONDS"],
            name=str(number),
            marker_color=color,
            line=dict(color=color, width=1.5),
            fillcolor=color + "55",   # 33% opacity fill
            boxpoints=False,
            whiskerwidth=0.6,
            hovertemplate=(
                f"<b>Car {number}</b> — {team}<br>"
                "Median: %{median:.3f}s<br>"
                "Q1–Q3: %{q1:.3f} – %{q3:.3f}s<extra></extra>"
            ),
        ))

    apply_dark_layout(
        fig_box,
        title=f"{session_label} Pace — Distribution by Car",
        yaxis=yaxis,
        height=480,
        showlegend=False,
    )
    st.plotly_chart(fig_box, use_container_width=True)
    chart_export_buttons(fig=fig_box, filename=f"{key_prefix}_pace_box", height=480)

    st.divider()

    # ── Strip / dot chart ─────────────────────────────────────────────────────
    st.markdown("#### Individual Lap Times")

    driver_col_avail = "DRIVER_NAME" in dff.columns

    fig_strip = go.Figure()

    rng = np.random.default_rng(seed=42)

    for number in median_order:
        car_df = dff[dff["NUMBER"] == number].copy()
        if car_df.empty:
            continue
        team = car_df["TEAM"].iloc[0]
        color = color_map.get(team, "#888888")

        # Deterministic jitter seeded per car so reruns are stable
        car_rng = np.random.default_rng(abs(hash(str(number))) % 2**32)
        jitter = car_rng.uniform(-0.38, 0.38, size=len(car_df))

        custom = (
            car_df[["LAP_NUMBER", "DRIVER_NAME"]].fillna("").values
            if driver_col_avail
            else np.column_stack([car_df["LAP_NUMBER"].values,
                                  [""] * len(car_df)])
        )

        fig_strip.add_trace(go.Scatter(
            x=np.array([str(number)] * len(car_df), dtype=object),
            y=car_df["LAP_TIME_SECONDS"].values,
            mode="markers",
            name=str(number),
            marker=dict(color=color, size=5, opacity=0.7),
            customdata=custom,
            hovertemplate=(
                f"<b>Car {number}</b><br>"
                "Lap %{customdata[0]}: %{y:.3f}s<br>"
                "%{customdata[1]}<extra></extra>"
            ),
        ))

    apply_dark_layout(
        fig_strip,
        title=f"{session_label} Lap Times — Individual Laps",
        yaxis=yaxis,
        height=480,
        showlegend=False,
    )
    st.plotly_chart(fig_strip, use_container_width=True)
    chart_export_buttons(fig=fig_strip, filename=f"{key_prefix}_pace_strip", height=480)
