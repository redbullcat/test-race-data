"""_pages/practice.py — Practice session analysis: sidebar file picker + 6-tab layout."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from data_loader import load_practice_sessions
from practice_analysis import session_durations_by_name, longest_stints
from utils import seconds_to_laptime

from practice_fastest_laps_table import show_practice_fastest_laps
from practice_pace_chart import show_practice_pace_chart
from practice_long_runs import show_practice_long_runs
from practice_fastest_runs import show_practice_fastest_runs
from practice_team_run_analysis import show_practice_team_run_analysis
from practice_average_long_run_pace import show_practice_average_long_run_pace
from practice_team_avg_pace import show_practice_team_avg_pace
from race_pace_distribution import show_race_pace_distribution
from sector_analysis import show_sector_analysis
from manufacturer_battle import show_manufacturer_battle
from top_speed_chart import show_top_speed_chart


# ---------------------------------------------------------------------------
# Sidebar session file selector (returns selected filenames)
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
    # Stat cards
    n_sessions = df["PRACTICE_SESSION"].nunique() if "PRACTICE_SESSION" in df.columns else 1
    n_laps = len(df)
    n_cars = df[["NUMBER", "TEAM"]].drop_duplicates().shape[0]
    n_drivers = df["DRIVER_NAME"].nunique() if "DRIVER_NAME" in df.columns else 0

    top_speed_val, top_speed_car = "—", "—"
    if "TOP_SPEED" in df.columns:
        spd = pd.to_numeric(df["TOP_SPEED"], errors="coerce")
        if spd.notna().any():
            top_speed_val = f"{spd.max():.1f} km/h"
            top_speed_car = f"#{df.loc[spd.idxmax(), 'NUMBER']}"

    fl_time, fl_car, fl_driver = "—", "—", "—"
    if "LAP_TIME_SECONDS" in df.columns:
        valid = df.dropna(subset=["LAP_TIME_SECONDS"])
        if not valid.empty:
            row = valid.loc[valid["LAP_TIME_SECONDS"].idxmin()]
            fl_time = seconds_to_laptime(row["LAP_TIME_SECONDS"])
            fl_car = str(int(row["NUMBER"])) if pd.notna(row["NUMBER"]) else "—"
            fl_driver = str(row.get("DRIVER_NAME", "—"))

    st.markdown("""
        <style>
        [data-testid="stMetricLabel"] p,
        [data-testid="stMetricDelta"] > div { white-space: normal !important; }
        </style>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4, c5, c6 = st.columns([0.9, 0.9, 0.9, 0.9, 1.5, 1.8])
    c1.metric("Sessions", n_sessions)
    c2.metric("Total Laps", n_laps)
    c3.metric("Cars", n_cars)
    c4.metric("Drivers", n_drivers)
    c5.metric("Top Speed", top_speed_val, top_speed_car)
    c6.metric("Fastest Lap", fl_time, f"#{fl_car} · {fl_driver}")

    st.divider()
    st.markdown("#### Fastest Lap by Class")
    show_practice_fastest_laps(df)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def show_practice(session_dir: str, session_files: list[str], team_colors: dict) -> None:
    if not session_files:
        st.info("No practice session files found.")
        return

    key_prefix = "prac"
    selected_files = _sidebar_file_selector(session_dir, session_files, key_prefix)

    if not selected_files:
        st.warning("No sessions selected.")
        return

    df = load_practice_sessions(session_dir, tuple(selected_files))
    if df.empty:
        st.error("Failed to load session data.")
        return

    required = {"LAP_TIME", "NUMBER", "TEAM", "CLASS", "DRIVER_NAME"}
    missing = required - set(df.columns)
    if missing:
        st.error("Missing required columns: " + ", ".join(sorted(missing)))
        return

    longest_stints_df = longest_stints(df)

    tab_overview, tab_laptimes, tab_longruns, tab_team, tab_sectors, tab_mfr = st.tabs([
        "Overview", "Lap Times", "Long Runs", "Team", "Sectors", "Manufacturers",
    ])

    with tab_overview:
        _show_overview(df, team_colors, key_prefix)

    with tab_laptimes:
        show_practice_pace_chart(df, team_colors, key_prefix=key_prefix)
        st.divider()
        show_race_pace_distribution(df, team_colors, key_prefix=f"{key_prefix}_pd",
                                    session_label="Session")

    with tab_longruns:
        show_practice_long_runs(longest_stints_df, team_colors, key_prefix=key_prefix)
        st.divider()
        show_practice_fastest_runs(df, team_colors, key_prefix=key_prefix)
        st.divider()
        show_practice_average_long_run_pace(df, team_colors, key_prefix=key_prefix)

    with tab_team:
        st.session_state["session_durations"] = session_durations_by_name(
            tuple({f: os.path.join(session_dir, f) for f in selected_files}.items())
        )
        show_practice_team_run_analysis(df, team_colors, key_prefix=key_prefix)
        st.divider()
        show_practice_team_avg_pace(df, team_colors, key_prefix=key_prefix)

    with tab_sectors:
        show_sector_analysis(df, team_colors, key_prefix=f"{key_prefix}_sec")

    with tab_mfr:
        show_manufacturer_battle(df, team_colors, key_prefix=f"{key_prefix}_mfr")
        st.divider()
        show_top_speed_chart(df, team_colors, key_prefix=f"{key_prefix}_ts",
                             session_label="Session")
