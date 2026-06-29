"""_pages/qualifying.py — Qualifying session analysis: sidebar file picker + 5-tab layout."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from data_loader import load_practice_sessions
from practice_analysis import session_durations_by_name
from utils import seconds_to_laptime

from practice_fastest_laps_table import show_practice_fastest_laps
from practice_pace_chart import show_practice_pace_chart
from race_pace_distribution import show_race_pace_distribution
from sector_analysis import show_sector_analysis
from manufacturer_battle import show_manufacturer_battle
from top_speed_chart import show_top_speed_chart
from qualifying_story_chart import show_qualifying_story


# ---------------------------------------------------------------------------
# Sidebar session file selector
# ---------------------------------------------------------------------------

def _sidebar_file_selector(session_dir: str, session_files: list[str], key_prefix: str) -> list[str]:
    files_map = {f: os.path.join(session_dir, f) for f in session_files}
    durations = session_durations_by_name(tuple(files_map.items()))

    with st.sidebar:
        st.divider()
        st.markdown("**Session files**")
        all_selected = st.checkbox("All sessions", value=True, key=f"{key_prefix}_all")
        selected: list[str] = []
        for filename in session_files:
            dur_str = f" ({durations[filename]:.0f} min)" if filename in durations else ""
            label = os.path.splitext(filename)[0].replace("_", " ").title() + dur_str
            checked = st.checkbox(
                label,
                value=all_selected,
                disabled=all_selected,
                key=f"{key_prefix}_file_{filename}",
            )
            if all_selected or checked:
                selected.append(filename)
    return selected


# ---------------------------------------------------------------------------
# Overview tab
# ---------------------------------------------------------------------------

def _show_overview(df: pd.DataFrame, team_colors: dict, key_prefix: str) -> None:
    n_laps = len(df)
    n_cars = df[["NUMBER", "TEAM"]].drop_duplicates().shape[0]

    # Pole: car with the fastest single lap across the session
    pole_car, pole_team, pole_time = "—", "—", "—"
    if "LAP_TIME_SECONDS" in df.columns:
        valid = df.dropna(subset=["LAP_TIME_SECONDS"])
        if not valid.empty:
            row = valid.loc[valid["LAP_TIME_SECONDS"].idxmin()]
            pole_car = str(int(row["NUMBER"])) if pd.notna(row["NUMBER"]) else "—"
            pole_team = str(row.get("TEAM", "—"))
            pole_time = seconds_to_laptime(row["LAP_TIME_SECONDS"])

    top_speed_val, top_speed_car = "—", "—"
    if "TOP_SPEED" in df.columns:
        spd = pd.to_numeric(df["TOP_SPEED"], errors="coerce")
        if spd.notna().any():
            top_speed_val = f"{spd.max():.1f} km/h"
            top_speed_car = f"#{df.loc[spd.idxmax(), 'NUMBER']}"

    fl_driver = "—"
    if "DRIVER_NAME" in df.columns and "LAP_TIME_SECONDS" in df.columns:
        valid = df.dropna(subset=["LAP_TIME_SECONDS"])
        if not valid.empty:
            fl_driver = str(valid.loc[valid["LAP_TIME_SECONDS"].idxmin()].get("DRIVER_NAME", "—"))

    st.markdown("""
        <style>
        [data-testid="stMetricLabel"] p,
        [data-testid="stMetricDelta"] > div { white-space: normal !important; }
        </style>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns([1.8, 0.9, 0.9, 1.5, 1.8])
    c1.metric("Pole Position", f"#{pole_car}", pole_team)
    c2.metric("Total Laps", n_laps)
    c3.metric("Cars", n_cars)
    c4.metric("Top Speed", top_speed_val, top_speed_car)
    c5.metric("Pole Time", pole_time, f"#{pole_car} · {fl_driver}")

    st.divider()
    st.markdown("#### Qualifying Results by Class")
    show_practice_fastest_laps(df)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def show_qualifying(session_dir: str, session_files: list[str], team_colors: dict) -> None:
    if not session_files:
        st.info("No qualifying session files found.")
        return

    key_prefix = "qual"
    selected_files = _sidebar_file_selector(session_dir, session_files, key_prefix)

    if not selected_files:
        st.warning("No sessions selected.")
        return

    df = load_practice_sessions(session_dir, tuple(selected_files))
    if df.empty:
        st.error("Failed to load qualifying data.")
        return

    tab_overview, tab_laptimes, tab_story, tab_sectors, tab_mfr = st.tabs([
        "Overview", "Lap Times", "Story", "Sectors", "Manufacturers",
    ])

    with tab_overview:
        _show_overview(df, team_colors, key_prefix)

    with tab_laptimes:
        show_practice_pace_chart(df, team_colors, key_prefix=key_prefix)
        st.divider()
        show_race_pace_distribution(df, team_colors, key_prefix=f"{key_prefix}_pd",
                                    session_label="Qualifying")

    with tab_story:
        show_qualifying_story(
            df=df,
            team_colors=team_colors,
            session_files=selected_files,
            key_prefix=f"{key_prefix}_story",
        )

    with tab_sectors:
        show_sector_analysis(df, team_colors, key_prefix=f"{key_prefix}_sec")

    with tab_mfr:
        show_manufacturer_battle(df, team_colors, key_prefix=f"{key_prefix}_mfr")
        st.divider()
        show_top_speed_chart(df, team_colors, key_prefix=f"{key_prefix}_ts",
                             session_label="Qualifying")
