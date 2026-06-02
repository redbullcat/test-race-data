"""gap_evolution_chart.py — Gap evolution and cumulative time charts."""

from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from utils import parse_hour_with_rollover, build_color_map, apply_dark_layout, sort_cars, chart_export_buttons


def get_filtered_race_data(df, race_start_date):
    """Shared UI filtering for gap/cumulative charts. Returns filtered df and selections."""
    required = {"CLASS", "NUMBER", "LAP_TIME", "LAP_NUMBER", "TEAM", "ELAPSED", "HOUR"}
    missing = required - set(df.columns)
    if missing:
        st.warning(f"Required columns missing: {missing}")
        return None, None, None, None

    df = df.copy()
    df["HOUR_DT"] = parse_hour_with_rollover(df, race_start_date)
    df["LAP_NUMBER"] = df["LAP_NUMBER"].dropna()

    selected_class = st.selectbox("Select class:", sorted(df["CLASS"].dropna().unique()), key="gap_class")
    class_df = df[df["CLASS"] == selected_class].copy()

    car_numbers = sort_cars(class_df["NUMBER"].dropna().unique())
    default_cars = car_numbers[:3] if len(car_numbers) >= 3 else car_numbers
    selected_cars = st.multiselect(
        "Select cars to compare:", car_numbers, default=default_cars, key="gap_cars"
    )
    if not selected_cars:
        st.info("Select at least one car.")
        return None, None, None, None

    selected_df = class_df[class_df["NUMBER"].isin(selected_cars)].copy()
    selected_df["LAP_NUMBER"] = selected_df["LAP_NUMBER"].astype(int)
    selected_df = selected_df.dropna(subset=["HOUR_DT", "LAP_NUMBER"])

    min_lap, max_lap = int(selected_df["LAP_NUMBER"].min()), int(selected_df["LAP_NUMBER"].max())
    lap_range = st.slider(
        "Lap range:", min_lap, max_lap, (min_lap, max_lap), key="gap_laps"
    )

    filtered_df = selected_df[
        selected_df["LAP_NUMBER"].between(lap_range[0], lap_range[1])
    ]
    if filtered_df.empty:
        st.info("No data for selected filters.")
        return None, None, None, None

    return filtered_df, selected_class, selected_cars, lap_range


def show_gap_evolution_chart(filtered_df, team_colors, selected_class, selected_cars):
    st.subheader("Gap Evolution")

    df = filtered_df.copy()
    race_start_dt = datetime.combine(df["HOUR_DT"].min().date(), datetime.min.time())
    df["CUM_TIME_SEC"] = (df["HOUR_DT"] - race_start_dt).dt.total_seconds()

    fastest_car = df.groupby("NUMBER")["CUM_TIME_SEC"].max().idxmin()
    ref = df[df["NUMBER"] == fastest_car][["LAP_NUMBER", "CUM_TIME_SEC"]].rename(
        columns={"CUM_TIME_SEC": "REF_TIME"}
    )
    merged = df.merge(ref, on="LAP_NUMBER", how="left")
    merged["GAP"] = merged["CUM_TIME_SEC"] - merged["REF_TIME"]

    fig = go.Figure()
    color_map = build_color_map(df, team_colors)

    for car in selected_cars:
        car_data = merged[merged["NUMBER"] == car]
        if car_data.empty:
            continue
        team = car_data["TEAM"].iloc[0]
        fig.add_trace(go.Scatter(
            x=car_data["LAP_NUMBER"],
            y=car_data["GAP"],
            mode="lines+markers",
            name=f"{car} – {team}",
            line=dict(width=2, color=color_map.get(team, "#AAAAAA")),
            marker=dict(size=4),
        ))

    fig.update_layout(
        title=f"Gap Evolution – {selected_class}",
        xaxis_title="Lap Number",
        yaxis_title="Gap to Leader (s)",
    )
    apply_dark_layout(fig)
    st.plotly_chart(fig, width='stretch')
    chart_export_buttons(fig=fig, filename="gap_evolution_chart", height=500)


def show_cumulative_time_chart(filtered_df, team_colors, selected_class, selected_cars):
    st.subheader("Cumulative Time")

    df = filtered_df.copy()
    race_start_dt = datetime.combine(df["HOUR_DT"].min().date(), datetime.min.time())
    df["CUM_TIME_SEC"] = (df["HOUR_DT"] - race_start_dt).dt.total_seconds()

    fig = go.Figure()
    color_map = build_color_map(df, team_colors)

    for car in selected_cars:
        car_data = df[df["NUMBER"] == car]
        if car_data.empty:
            continue
        team = car_data["TEAM"].iloc[0]
        fig.add_trace(go.Scatter(
            x=car_data["LAP_NUMBER"],
            y=car_data["CUM_TIME_SEC"],
            mode="lines+markers",
            name=f"{car} – {team}",
            line=dict(width=2, color=color_map.get(team, "#AAAAAA")),
            marker=dict(size=4),
        ))

    fig.update_layout(
        title=f"Cumulative Time – {selected_class}",
        xaxis_title="Lap Number",
        yaxis_title="Cumulative Time (s)",
    )
    apply_dark_layout(fig)
    st.plotly_chart(fig, width='stretch')
    chart_export_buttons(fig=fig, filename="gap_evolution_button", height=500)
