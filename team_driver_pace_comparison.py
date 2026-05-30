"""team_driver_pace_comparison.py — Per-team driver pace comparison."""

import plotly.express as px
import streamlit as st

from utils import get_team_color, filter_top_percent, apply_dark_layout


def show_team_driver_pace_comparison(df, team_colors):
    st.subheader("Team-by-Team Driver Pace Comparison")

    df = df.dropna(subset=["LAP_TIME_SECONDS"])
    if df.empty:
        st.warning("No valid lap time data.")
        return

    classes = sorted(df["CLASS"].dropna().unique())
    tabs = st.tabs(classes)

    for cls, tab in zip(classes, tabs):
        with tab:
            class_df = df[df["CLASS"] == cls]
            teams = sorted(class_df["TEAM"].dropna().unique())

            for team in teams:
                team_df = class_df[class_df["TEAM"] == team]
                driver_avgs = (
                    team_df.groupby("DRIVER_NAME")["LAP_TIME_SECONDS"]
                    .mean()
                    .reset_index()
                    .sort_values("LAP_TIME_SECONDS")
                )
                if driver_avgs.empty:
                    continue

                color = get_team_color(team, team_colors)
                fig = px.bar(
                    driver_avgs,
                    x="DRIVER_NAME",
                    y="LAP_TIME_SECONDS",
                    title=f"{team} — Driver Comparison",
                    labels={"LAP_TIME_SECONDS": "Avg Lap Time (s)", "DRIVER_NAME": "Driver"},
                    color_discrete_sequence=[color],
                    text=driver_avgs["LAP_TIME_SECONDS"].round(3).astype(str),
                )
                y_pad = 0.3
                fig.update_layout(
                    yaxis=dict(range=[
                        driver_avgs["LAP_TIME_SECONDS"].min() - y_pad,
                        driver_avgs["LAP_TIME_SECONDS"].max() + y_pad,
                    ]),
                    title_font=dict(size=20),
                )
                apply_dark_layout(fig)
                st.plotly_chart(fig, use_container_width=True)
                st.divider()
