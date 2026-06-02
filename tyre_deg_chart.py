"""
tyre_deg_chart.py — Tyre degradation rate analysis.

Fits a linear regression to each car's lap times within each stint to
compute a degradation rate (seconds per lap lost). Ranks teams by deg rate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import apply_dark_layout, build_color_map, sort_cars, chart_export_buttons


def _identify_stints(car_df: pd.DataFrame) -> pd.Series:
    """
    Assign a stint number to each lap based on pit stop crossings.
    A new stint starts after any lap where CROSSING_FINISH_LINE_IN_PIT == 'B'.
    """
    car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)
    stint = 1
    stints = []
    for _, row in car_df.iterrows():
        stints.append(stint)
        if str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B":
            stint += 1
    return pd.Series(stints, index=car_df.index)


@st.cache_data(show_spinner=False)
def _compute_deg_rates(df: pd.DataFrame, min_stint_laps: int = 5) -> pd.DataFrame:
    """
    For each car/stint with at least min_stint_laps laps, fit a linear
    regression of LAP_TIME_SECONDS vs lap-in-stint and extract the slope
    (= degradation rate in s/lap).

    Returns a DataFrame with columns:
        NUMBER, TEAM, CLASS, stint, laps, deg_rate, r2, median_pace
    """
    if "CROSSING_FINISH_LINE_IN_PIT" not in df.columns:
        return pd.DataFrame()

    df = df.dropna(subset=["LAP_TIME_SECONDS", "LAP_NUMBER"]).copy()
    # Remove clear outliers (SC laps, pit laps) — keep laps within 110% of car's median
    median_times = df.groupby("NUMBER")["LAP_TIME_SECONDS"].transform("median")
    df = df[df["LAP_TIME_SECONDS"] <= median_times * 1.10]

    rows = []
    for (number, team, cls), car_df in df.groupby(["NUMBER", "TEAM", "CLASS"]):
        car_df = car_df.sort_values("LAP_NUMBER").copy()
        car_df["STINT"] = _identify_stints(car_df)

        for stint_num, stint_df in car_df.groupby("STINT"):
            stint_df = stint_df.reset_index(drop=True)
            if len(stint_df) < min_stint_laps:
                continue

            x = np.arange(len(stint_df), dtype=float)
            y = stint_df["LAP_TIME_SECONDS"].values

            # Linear regression
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]  # s/lap — positive = degrading

            # R² to filter out noise
            y_pred = np.polyval(coeffs, x)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            rows.append({
                "NUMBER": number,
                "TEAM": team,
                "CLASS": cls,
                "Stint": stint_num,
                "Laps": len(stint_df),
                "Deg Rate (s/lap)": round(slope, 4),
                "R²": round(r2, 3),
                "Median Pace (s)": round(y.mean(), 3),
            })

    return pd.DataFrame(rows)


def show_tyre_deg_chart(df: pd.DataFrame, team_colors: dict) -> None:
    st.subheader("Tyre Degradation")
    st.caption("Linear degradation rate (s/lap) fitted to each stint. Positive = getting slower.")

    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Class:", classes, key="deg_class")

    min_laps = st.slider(
        "Minimum stint length (laps):", 3, 15, 5, key="deg_min_laps",
        help="Shorter stints are excluded — too few points for reliable regression."
    )

    class_df = df[df["CLASS"] == selected_class].copy()
    deg_df = _compute_deg_rates(class_df, min_stint_laps=min_laps)

    if deg_df.empty:
        st.info("Not enough stint data to compute degradation rates. "
                "This requires pit crossing data in the CSV.")
        return

    # Aggregate per car: weighted average deg rate by stint length
    car_agg = (
        deg_df.groupby(["NUMBER", "TEAM"])
        .apply(lambda g: pd.Series({
            "Avg Deg Rate (s/lap)": np.average(g["Deg Rate (s/lap)"], weights=g["Laps"]),
            "Stints": len(g),
            "Total Laps": g["Laps"].sum(),
            "Median Pace (s)": g["Median Pace (s)"].mean(),
        }))
        .reset_index()
        .sort_values("Avg Deg Rate (s/lap)")
    )
    car_agg["Label"] = car_agg["NUMBER"] + " — " + car_agg["TEAM"]
    car_agg["Avg Deg Rate (s/lap)"] = car_agg["Avg Deg Rate (s/lap)"].round(4)

    color_map = build_color_map(car_agg, team_colors)

    fig = go.Figure()
    for _, row in car_agg.iterrows():
        color = color_map.get(row["TEAM"], "#888888")
        fig.add_trace(go.Bar(
            y=[row["Label"]],
            x=[row["Avg Deg Rate (s/lap)"]],
            orientation="h",
            name=row["TEAM"],
            marker_color=color,
            customdata=[[row["Stints"], row["Total Laps"], row["Median Pace (s)"]]],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Deg rate: %{x:.4f} s/lap<br>"
                "Stints: %{customdata[0]}<br>"
                "Total laps: %{customdata[1]}<br>"
                "Avg pace: %{customdata[2]:.3f}s"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        title="Tyre Degradation Rate by Car",
        xaxis_title="Degradation Rate (s/lap) — lower is better",
        yaxis_title="",
        showlegend=False,
        yaxis=dict(categoryorder="array", categoryarray=car_agg["Label"].tolist()),
    )
    apply_dark_layout(fig, title_font=dict(size=22))
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(fig=fig, filename="tyre_deg_chart", height=500)

    # Stint detail table
    with st.expander("Stint detail", expanded=False):
        display = deg_df[["NUMBER", "TEAM", "Stint", "Laps", "Deg Rate (s/lap)", "R²", "Median Pace (s)"]].copy()
        display = display[display["NUMBER"].isin(car_agg["NUMBER"])]
        display = display.sort_values(["NUMBER", "Stint"])
        st.dataframe(display, hide_index=True, width="stretch")
        chart_export_buttons(df=display, filename="tyre_deg_stint_detail")
