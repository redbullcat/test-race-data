"""pace_chart.py — Average race pace bar chart."""

import plotly.express as px
import streamlit as st

from utils import filter_top_percent, build_color_map, apply_dark_layout, sort_cars


def show_pace_chart(df, team_colors):
    st.subheader("Average Race Pace by Car")

    classes = sorted(df["CLASS"].dropna().unique())
    selected_classes = st.multiselect(
        "Select class(es):", classes, default=classes, key="pace_class"
    )

    df = df[df["CLASS"].isin(selected_classes)]

    available_cars = sort_cars(df["NUMBER"].unique())
    selected_cars = st.multiselect(
        "Select car(s):", available_cars, default=available_cars, key="pace_cars"
    )

    valid_laps = df["LAP_NUMBER"].dropna()
    if valid_laps.empty:
        st.warning("No lap number data available for this session.")
        return
    min_lap = int(valid_laps.min())
    max_lap = int(valid_laps.max())
    lap_range = st.slider(
        "Lap range:", min_lap, max_lap, (min_lap, max_lap), key="pace_laps"
    )

    top_percent = st.slider(
        "Top lap %:", 0, 100, 100, step=20, key="pace_top_pct",
        help="0% hides all data."
    )
    if top_percent == 0:
        st.warning("0% selected — no data to display.")
        return

    df = df[
        df["CLASS"].isin(selected_classes)
        & df["NUMBER"].isin(selected_cars)
        & df["LAP_NUMBER"].between(lap_range[0], lap_range[1])
    ].dropna(subset=["LAP_TIME_SECONDS"])

    if df.empty:
        st.warning("No data for selected filters.")
        return

    df = filter_top_percent(df, top_percent)

    avg_df = (
        df.groupby(["NUMBER", "TEAM", "CLASS"], as_index=False)["LAP_TIME_SECONDS"]
        .mean()
        .sort_values("LAP_TIME_SECONDS")
    )
    avg_df["Label"] = avg_df["NUMBER"] + " — " + avg_df["TEAM"]
    color_map = build_color_map(avg_df, team_colors)

    fig = px.bar(
        avg_df,
        y="Label",
        x="LAP_TIME_SECONDS",
        color="TEAM",
        orientation="h",
        color_discrete_map=color_map,
        title="Average Race Pace by Car",
        labels={"LAP_TIME_SECONDS": "Average Lap Time (s)", "Label": ""},
    )
    fig.update_yaxes(
        type="category",
        categoryorder="array",
        categoryarray=avg_df["Label"],
    )
    x_pad = 0.5
    fig.update_xaxes(range=[avg_df["LAP_TIME_SECONDS"].min() - x_pad,
                             avg_df["LAP_TIME_SECONDS"].max() + x_pad])
    apply_dark_layout(fig, title_font=dict(size=22))
    st.plotly_chart(fig, width='stretch')
