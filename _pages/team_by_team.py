"""pages/team_by_team.py — Per-class, per-team driver pace breakdown."""

import streamlit as st
from team_driver_pace_comparison import show_team_driver_pace_comparison


def show_team_by_team(df, team_colors):
    if df is None:
        st.error("No race data loaded.")
        return

    classes = sorted(df["CLASS"].dropna().unique())
    tabs = st.tabs(classes)

    for tab, cls in zip(tabs, classes):
        with tab:
            class_df = df[df["CLASS"] == cls]
            if not class_df.empty:
                show_team_driver_pace_comparison(class_df, team_colors)
