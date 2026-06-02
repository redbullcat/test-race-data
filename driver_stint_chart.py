"""
driver_stint_chart.py — Head-to-head driver comparison within a team.

Splits race pace and consistency by driver stints, using DRIVER_NAME
and CROSSING_FINISH_LINE_IN_PIT to identify each driver's contributions.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import apply_dark_layout, sort_cars, seconds_to_laptime, chart_export_buttons


@st.cache_data(show_spinner=False)
def _build_driver_stints(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign each lap to a driver stint, grouping consecutive laps by the same
    driver within a car. Returns DataFrame with per-stint stats.
    """
    df = df.dropna(subset=["LAP_NUMBER", "DRIVER_NAME"]).copy()
    df["LAP_NUMBER"] = df["LAP_NUMBER"].astype(int)

    rows = []
    for (number, team, cls), car_df in df.groupby(["NUMBER", "TEAM", "CLASS"]):
        car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)

        # Identify driver change points
        car_df["DRIVER_CHANGE"] = car_df["DRIVER_NAME"] != car_df["DRIVER_NAME"].shift()
        car_df["DRIVER_STINT"] = car_df["DRIVER_CHANGE"].cumsum()

        for stint_id, stint_df in car_df.groupby("DRIVER_STINT"):
            driver = stint_df["DRIVER_NAME"].iloc[0]
            times = stint_df["LAP_TIME_SECONDS"].dropna()
            if times.empty:
                continue
            median_t = times.median()
            clean = times[times <= median_t * 1.05]
            rows.append({
                "NUMBER": number,
                "TEAM": team,
                "CLASS": cls,
                "Driver": driver,
                "Driver Stint": int(stint_id),
                "Start Lap": int(stint_df["LAP_NUMBER"].min()),
                "End Lap": int(stint_df["LAP_NUMBER"].max()),
                "Laps": len(times),
                "Avg Pace (s)": round(clean.mean(), 3) if not clean.empty else None,
                "Std Dev (s)": round(clean.std(), 3) if len(clean) > 1 else None,
                "Best Lap (s)": round(times.min(), 3),
            })

    return pd.DataFrame(rows)


def show_driver_stint_chart(df: pd.DataFrame, team_colors: dict) -> None:
    st.subheader("Driver Comparison Within Teams")
    st.caption("Compares each driver's average clean pace and consistency across their stints.")

    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Class:", classes, key="drv_class")

    class_df = df[df["CLASS"] == selected_class].copy()
    stint_df = _build_driver_stints(class_df)

    if stint_df.empty:
        st.info("No driver stint data available.")
        return

    stint_df = stint_df[stint_df["CLASS"] == selected_class]

    cars = sort_cars(stint_df["NUMBER"].unique())
    selected_car = st.selectbox(
        "Select car:",
        cars,
        format_func=lambda n: f"#{n} — {stint_df[stint_df['NUMBER']==n]['TEAM'].iloc[0]}",
        key="drv_car",
    )

    car_stints = stint_df[stint_df["NUMBER"] == selected_car].copy()
    drivers = car_stints["Driver"].unique()

    # Summary: one row per driver (aggregated across their stints)
    driver_summary = (
        car_stints.groupby("Driver")
        .agg(
            Total_Laps=("Laps", "sum"),
            Avg_Pace=("Avg Pace (s)", "mean"),
            Std_Dev=("Std Dev (s)", "mean"),
            Best_Lap=("Best Lap (s)", "min"),
        )
        .reset_index()
        .sort_values("Avg_Pace")
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Average Pace by Driver**")
        fig = go.Figure()
        colors = ["#4C9BE8", "#E87C4C", "#4CE87C", "#E84C9B", "#9BE84C"]
        for i, (_, row) in enumerate(driver_summary.iterrows()):
            color = colors[i % len(colors)]
            fig.add_trace(go.Bar(
                y=[row["Driver"].split()[-1]],  # surname only for brevity
                x=[row["Avg_Pace"]],
                orientation="h",
                marker_color=color,
                name=row["Driver"],
                customdata=[[row["Driver"], row["Total_Laps"], seconds_to_laptime(row["Best_Lap"])]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Avg pace: %{x:.3f}s<br>"
                    "Laps: %{customdata[1]}<br>"
                    "Best lap: %{customdata[2]}"
                    "<extra></extra>"
                ),
            ))
        pad = 0.3
        if not driver_summary.empty:
            fig.update_xaxes(range=[
                driver_summary["Avg_Pace"].min() - pad,
                driver_summary["Avg_Pace"].max() + pad,
            ])
        apply_dark_layout(fig, showlegend=False)
        st.plotly_chart(fig, width="stretch")
        chart_export_buttons(fig=fig, filename="driver_stint_chart", height=500)

    with col2:
        st.markdown("**Consistency (Std Dev) by Driver**")
        fig2 = go.Figure()
        ds_sorted = driver_summary.sort_values("Std_Dev")
        for i, (_, row) in enumerate(ds_sorted.iterrows()):
            color = colors[i % len(colors)]
            fig2.add_trace(go.Bar(
                y=[row["Driver"].split()[-1]],
                x=[row["Std_Dev"]],
                orientation="h",
                marker_color=color,
                name=row["Driver"],
                hovertemplate=f"<b>{row['Driver']}</b><br>Std dev: %{{x:.3f}}s<extra></extra>",
            ))
        apply_dark_layout(fig2, showlegend=False)
        st.plotly_chart(fig2, width="stretch")
        chart_export_buttons(fig=fig2, filename="driver_stint_consistency", height=500)

    # Stint-by-stint pace trace
    st.markdown("**Pace Trace by Stint**")
    fig3 = go.Figure()
    colors_map = {d: colors[i % len(colors)] for i, d in enumerate(drivers)}

    for _, stint_row in car_stints.sort_values("Start Lap").iterrows():
        driver = stint_row["Driver"]
        driver_laps = class_df[
            (class_df["NUMBER"] == selected_car) &
            (class_df["LAP_NUMBER"] >= stint_row["Start Lap"]) &
            (class_df["LAP_NUMBER"] <= stint_row["End Lap"]) &
            (class_df["DRIVER_NAME"] == driver)
        ].sort_values("LAP_NUMBER")

        clean_median = driver_laps["LAP_TIME_SECONDS"].median()
        clean_laps = driver_laps[driver_laps["LAP_TIME_SECONDS"] <= clean_median * 1.10]

        if clean_laps.empty:
            continue

        fig3.add_trace(go.Scatter(
            x=clean_laps["LAP_NUMBER"],
            y=clean_laps["LAP_TIME_SECONDS"],
            mode="markers+lines",
            name=driver,
            line=dict(color=colors_map.get(driver, "#888888")),
            marker=dict(size=4),
            legendgroup=driver,
            showlegend=bool(stint_row["Driver Stint"] == car_stints[car_stints["Driver"] == driver]["Driver Stint"].min()),
        ))

    fig3.update_layout(
        xaxis_title="Lap Number",
        yaxis_title="Lap Time (s)",
    )
    apply_dark_layout(fig3)
    st.plotly_chart(fig3, width="stretch")
    chart_export_buttons(fig=fig3, filename="driver_lap_trace", height=500)
