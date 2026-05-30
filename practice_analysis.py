"""practice_analysis.py — Practice / test session analysis page."""

import math
import os
import re

import pandas as pd
import streamlit as st

from config import DATA_DIR
from data_loader import load_practice_sessions
from utils import lap_to_seconds

from practice_fastest_laps_table import show_practice_fastest_laps
from practice_pace_chart import show_practice_pace_chart
from practice_long_runs import show_practice_long_runs
from practice_fastest_runs import show_practice_fastest_runs
from practice_team_run_analysis import show_practice_team_run_analysis
from practice_average_long_run_pace import show_practice_average_long_run_pace

_PRACTICE_RE = re.compile(r"_practice(\d+)\.csv$", re.IGNORECASE)
_SESSION_RE = re.compile(r"_session(\d+)\.csv$", re.IGNORECASE)


def _parse_elapsed_secs(val) -> float | None:
    return lap_to_seconds(val)


@st.cache_data(show_spinner=False)
def _session_durations(session_files_tuple: tuple) -> dict[int, float]:
    """Compute the duration in minutes for each session."""
    session_files = dict(session_files_tuple)
    durations = {}

    for num, path in session_files.items():
        try:
            df = pd.read_csv(path, delimiter=";")
        except Exception:
            continue
        df.columns = df.columns.str.strip()
        if "ELAPSED" not in df.columns:
            continue

        df["ELAPSED_S"] = df["ELAPSED"].apply(_parse_elapsed_secs)
        df = df.dropna(subset=["ELAPSED_S"])
        if df.empty:
            continue

        durations[num] = round(df["ELAPSED_S"].max() / 60, 1)

    return durations


@st.cache_data(show_spinner=False)
def _longest_stints(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the longest continuous no-pit stint per car across all sessions."""
    rows = []

    for (car, team), car_group in df.groupby(["NUMBER", "TEAM"]):
        best_stint = []
        best_session = None

        for session_name, session_df in car_group.groupby("PRACTICE_SESSION"):
            session_df = session_df.sort_values("LAP_NUMBER").reset_index(drop=True)
            current: list = []
            skip_next = False

            for _, row in session_df.iterrows():
                if skip_next:
                    skip_next = False
                    continue
                in_pit = str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B"
                if in_pit:
                    trimmed = current[:-1]  # remove the in-lap
                    if len(trimmed) > len(best_stint):
                        best_stint, best_session = trimmed, session_name
                    current = []
                    skip_next = True
                else:
                    current.append(row)

            if len(current) > len(best_stint):
                best_stint, best_session = current, session_name

        if not best_stint:
            continue

        stint_df = pd.DataFrame(best_stint).dropna(subset=["LAP_TIME_SECONDS"])
        if stint_df.empty:
            continue

        times = stint_df["LAP_TIME_SECONDS"].tolist()
        n20 = max(1, int(len(times) * 0.2))
        avg20 = sum(sorted(times)[:n20]) / n20

        rows.append({
            "Car": car,
            "Team": team,
            "Manufacturer": stint_df.iloc[0].get("MANUFACTURER", ""),
            "Class": stint_df.iloc[0].get("CLASS", ""),
            "Drivers": " / ".join(stint_df["DRIVER_NAME"].dropna().unique()),
            "Lap_Numbers": stint_df["LAP_NUMBER"].tolist(),
            "Lap_Times": times,
            "Average_Lap_Time_Seconds": sum(times) / len(times),
            "Average_20_Percent_Pace": avg20,
            "Stint_Length": len(times),
            "Session": best_session,
        })

    return pd.DataFrame(rows)


def show_practice_analysis(data_dir: str, year: str, series: str, race: str, team_colors: dict):
    st.subheader("Practice / Test Session Analysis")

    base_path = os.path.join(data_dir, year, series)
    if not os.path.isdir(base_path):
        st.error("Data directory not found.")
        return

    # Discover files
    practice_files: dict[int, str] = {}
    session_files: dict[int, str] = {}
    race_lower = race.lower()

    for filename in os.listdir(base_path):
        fl = filename.lower()
        if not fl.startswith(race_lower):
            continue
        m_p = _PRACTICE_RE.search(fl)
        if m_p:
            practice_files[int(m_p.group(1))] = os.path.join(base_path, filename)
            continue
        m_s = _SESSION_RE.search(fl)
        if m_s:
            session_files[int(m_s.group(1))] = os.path.join(base_path, filename)

    files_to_use = practice_files or session_files
    if not files_to_use:
        st.warning("No practice / test session files found for this event.")
        return

    available_sessions = sorted(files_to_use.keys())
    # Compute durations once (cached)
    durations = _session_durations(tuple(files_to_use.items()))

    # Session selector
    st.markdown("### Session Selection")
    all_selected = st.checkbox("All sessions", value=True, key="prac_all_sessions")

    selected_sessions: list[int] = []
    for num in available_sessions:
        dur_str = f" ({durations[num]} min)" if num in durations else ""
        checked = st.checkbox(
            f"Session {num}{dur_str}",
            value=all_selected,
            disabled=all_selected,
            key=f"prac_session_{num}",
        )
        if all_selected or checked:
            selected_sessions.append(num)

    if not selected_sessions:
        st.warning("No sessions selected.")
        return

    # Load and cache combined practice DataFrame
    df = load_practice_sessions(files_to_use, tuple(selected_sessions))

    if df.empty:
        st.error("Failed to load session data.")
        return

    required = {"LAP_TIME", "NUMBER", "TEAM", "CLASS", "DRIVER_NAME"}
    missing = required - set(df.columns)
    if missing:
        st.error("Missing required columns: " + ", ".join(sorted(missing)))
        return

    # Overview metrics
    st.markdown("### Session Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sessions", len(selected_sessions))
    c2.metric("Total laps", len(df))
    c3.metric("Cars", df[["NUMBER", "TEAM"]].drop_duplicates().shape[0])
    c4.metric("Drivers", df["DRIVER_NAME"].nunique())
    st.divider()

    longest_stints_df = _longest_stints(df)

    with st.expander("Fastest Laps", expanded=True):
        show_practice_fastest_laps(df)

    with st.expander("Pace Chart", expanded=True):
        show_practice_pace_chart(df, team_colors)

    with st.expander("Long Runs", expanded=True):
        show_practice_long_runs(longest_stints_df, team_colors)

    with st.expander("Fastest Runs", expanded=True):
        show_practice_fastest_runs(df, team_colors)

    with st.expander("Team Run Analysis", expanded=True):
        # Pass session durations via a local variable (practice_team_run_analysis reads it)
        st.session_state["session_durations"] = durations
        show_practice_team_run_analysis(df, team_colors)

    with st.expander("Average Long Run Pace", expanded=False):
        show_practice_average_long_run_pace(df, team_colors)
