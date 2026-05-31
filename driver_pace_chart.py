"""driver_pace_chart.py — Average race pace by driver bar chart."""

import plotly.express as px
import streamlit as st

from utils import filter_top_percent, build_color_map, apply_dark_layout


def show_driver_pace_chart(df, team_colors):
    st.subheader("Average Race Pace by Driver")

    classes = sorted(df["CLASS"].dropna().unique())
    selected_classes = st.multiselect(
        "Select class(es) for driver pace:", classes, default=classes, key="dpace_class"
    )
    df = df[df["CLASS"].isin(selected_classes)]

    available_cars = sort_cars(df["NUMBER"].unique())
    selected_cars = st.multiselect(
        "Select car(s) for driver pace:", available_cars, default=available_cars, key="dpace_cars"
    )

    top_percent = st.slider(
        "Top lap % (per driver):", 0, 100, 100, step=5, key="dpace_top_pct"
    )
    if top_percent == 0:
        st.warning("0% selected — no data to display.")
        return

    df = df[df["NUMBER"].isin(selected_cars)].dropna(subset=["LAP_TIME_SECONDS"])
    if df.empty:
        st.warning("No data for selected filters.")
        return

    # filter per (car, driver)
    from utils import filter_top_percent as _ftp
    df = _ftp(df, top_percent, group_col="DRIVER_NAME")

    avg_df = (
        df.groupby(["DRIVER_NAME", "TEAM", "NUMBER", "CLASS"], as_index=False)["LAP_TIME_SECONDS"]
        .mean()
        .sort_values("LAP_TIME_SECONDS")
    )
    avg_df["Label"] = (
        avg_df["DRIVER_NAME"] + " — " + avg_df["TEAM"] + " (#" + avg_df["NUMBER"].astype(str) + ")"
    )
    color_map = build_color_map(avg_df, team_colors)

    fig = px.bar(
        avg_df,
        y="Label",
        x="LAP_TIME_SECONDS",
        color="TEAM",
        orientation="h",
        color_discrete_map=color_map,
        title="Average Race Pace by Driver",
        labels={"LAP_TIME_SECONDS": "Average Lap Time (s)", "Label": ""},
    )
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=avg_df["Label"])
    x_pad = 0.5
    fig.update_xaxes(range=[avg_df["LAP_TIME_SECONDS"].min() - x_pad,
                             avg_df["LAP_TIME_SECONDS"].max() + x_pad])
    apply_dark_layout(fig, title_font=dict(size=22))
    st.plotly_chart(fig, width='stretch')
