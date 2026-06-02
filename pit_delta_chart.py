"""
pit_delta_chart.py — Pit stop delta analysis.

Computes actual time lost in each pit stop vs a theoretical no-stop baseline,
then ranks teams by average pit stop loss.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import apply_dark_layout, build_color_map, sort_cars, chart_export_buttons


@st.cache_data(show_spinner=False)
def _compute_pit_deltas(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each pit stop, compute the time lost versus the car's own median
    green-flag lap time (which serves as the theoretical pace baseline).

    A pit stop sequence:
      - in-lap:  the lap crossing the finish line in the pit (flagged 'B')
      - pit stop: time spent stationary (not directly in lap data)
      - out-lap: the lap after rejoining

    We approximate pit stop loss as:
        (in_lap_time + out_lap_time) - (2 × median_green_lap_time)

    This is the standard approximation used by F1 Strategy Group and
    endurance racing analysts when raw pit lane timing isn't available.
    """
    if "CROSSING_FINISH_LINE_IN_PIT" not in df.columns:
        return pd.DataFrame()

    df = df.dropna(subset=["LAP_TIME_SECONDS", "LAP_NUMBER"]).copy()
    df["LAP_NUMBER"] = df["LAP_NUMBER"].astype(int)

    # Compute median green-flag lap time per car (exclude outliers > 110%)
    def _green_median(car_df):
        median = car_df["LAP_TIME_SECONDS"].median()
        green = car_df[car_df["LAP_TIME_SECONDS"] <= median * 1.10]
        return green["LAP_TIME_SECONDS"].median() if not green.empty else median

    car_medians = (
        df.groupby("NUMBER")
        .apply(_green_median)
        .reset_index()
        .rename(columns={0: "GREEN_MEDIAN"})
    )

    rows = []
    for (number, team, cls), car_df in df.groupby(["NUMBER", "TEAM", "CLASS"]):
        car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)
        green_med = car_medians.loc[car_medians["NUMBER"] == number, "GREEN_MEDIAN"]
        if green_med.empty:
            continue
        green_med = green_med.iloc[0]

        pit_laps = car_df[
            car_df["CROSSING_FINISH_LINE_IN_PIT"].astype(str).str.strip().str.upper() == "B"
        ]

        for _, pit_row in pit_laps.iterrows():
            lap_n = pit_row["LAP_NUMBER"]
            # In-lap time
            in_lap_time = pit_row["LAP_TIME_SECONDS"]
            # Out-lap: next lap after the pit lap
            out_rows = car_df[car_df["LAP_NUMBER"] == lap_n + 1]
            if out_rows.empty:
                continue
            out_lap_time = out_rows.iloc[0]["LAP_TIME_SECONDS"]

            pit_loss = (in_lap_time + out_lap_time) - (2 * green_med)

            rows.append({
                "NUMBER": number,
                "TEAM": team,
                "CLASS": cls,
                "Pit Lap": int(lap_n),
                "In-Lap (s)": round(in_lap_time, 3),
                "Out-Lap (s)": round(out_lap_time, 3),
                "Baseline (s)": round(green_med, 3),
                "Pit Loss (s)": round(pit_loss, 3),
            })

    return pd.DataFrame(rows)


def show_pit_delta_chart(df: pd.DataFrame, team_colors: dict) -> None:
    st.subheader("Pit Stop Delta")
    st.caption(
        "Time lost per pit stop vs each car's own green-flag median pace. "
        "Calculated as (in-lap + out-lap) − (2 × median lap)."
    )

    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Class:", classes, key="pit_class")

    class_df = df[df["CLASS"] == selected_class].copy()
    pit_df = _compute_pit_deltas(class_df)

    if pit_df.empty:
        st.info("No pit stop data found. This requires CROSSING_FINISH_LINE_IN_PIT data in the CSV.")
        return

    # Filter to selected class
    pit_df = pit_df[pit_df["CLASS"] == selected_class]
    if pit_df.empty:
        st.info("No pit stop data for this class.")
        return

    # Aggregate per car
    car_agg = (
        pit_df.groupby(["NUMBER", "TEAM"])
        .agg(
            Stops=("Pit Lap", "count"),
            Avg_Loss=("Pit Loss (s)", "mean"),
            Min_Loss=("Pit Loss (s)", "min"),
            Max_Loss=("Pit Loss (s)", "max"),
        )
        .reset_index()
        .sort_values("Avg_Loss")
    )
    car_agg["Label"] = car_agg["NUMBER"] + " — " + car_agg["TEAM"]

    color_map = build_color_map(car_agg, team_colors)

    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure()
        for _, row in car_agg.iterrows():
            color = color_map.get(row["TEAM"], "#888888")
            fig.add_trace(go.Bar(
                y=[row["Label"]],
                x=[row["Avg_Loss"]],
                orientation="h",
                name=row["TEAM"],
                marker_color=color,
                customdata=[[row["Stops"], row["Min_Loss"], row["Max_Loss"]]],
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Avg pit loss: %{x:.2f}s<br>"
                    "Stops: %{customdata[0]}<br>"
                    "Best: %{customdata[1]:.2f}s<br>"
                    "Worst: %{customdata[2]:.2f}s"
                    "<extra></extra>"
                ),
            ))
        fig.update_layout(
            title="Avg Pit Loss by Car",
            xaxis_title="Time lost (s)",
            yaxis=dict(categoryorder="array", categoryarray=car_agg["Label"].tolist()),
            showlegend=False,
        )
        apply_dark_layout(fig, title_font=dict(size=18))
        st.plotly_chart(fig, width="stretch")
        chart_export_buttons(fig=fig, filename="pit_delta_chart", height=500)

    with col2:
        # Individual stop scatter
        pit_df["Label"] = pit_df["NUMBER"] + " — " + pit_df["TEAM"]
        fig2 = go.Figure()
        for car in sort_cars(pit_df["NUMBER"].unique()):
            car_stops = pit_df[pit_df["NUMBER"] == car]
            if car_stops.empty:
                continue
            team = car_stops["TEAM"].iloc[0]
            color = color_map.get(team, "#888888")
            label = car_stops["Label"].iloc[0]
            fig2.add_trace(go.Scatter(
                x=car_stops["Pit Lap"],
                y=car_stops["Pit Loss (s)"],
                mode="markers",
                name=label,
                marker=dict(color=color, size=10),
                customdata=car_stops[["In-Lap (s)", "Out-Lap (s)", "Baseline (s)"]].values,
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "Lap: %{x}<br>"
                    "Pit loss: %{y:.2f}s<br>"
                    "In-lap: %{customdata[0]:.3f}s<br>"
                    "Out-lap: %{customdata[1]:.3f}s<br>"
                    "Baseline: %{customdata[2]:.3f}s"
                    "<extra></extra>"
                ),
            ))
        fig2.update_layout(
            title="Individual Pit Stops",
            xaxis_title="Lap number",
            yaxis_title="Time lost (s)",
        )
        apply_dark_layout(fig2, title_font=dict(size=18))
        st.plotly_chart(fig2, width="stretch")
        chart_export_buttons(fig=fig2, filename="pit_delta_scatter", height=500)

    with st.expander("Full pit stop detail", expanded=False):
        display = pit_df[["NUMBER", "TEAM", "Pit Lap", "In-Lap (s)", "Out-Lap (s)", "Baseline (s)", "Pit Loss (s)"]]
        st.dataframe(display.sort_values(["NUMBER", "Pit Lap"]), hide_index=True, width="stretch")
        chart_export_buttons(df=display, filename="pit_stop_data")
