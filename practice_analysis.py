import os
import re
import pandas as pd
import streamlit as st
from datetime import timedelta

from practice_fastest_laps_table import show_practice_fastest_laps
from practice_pace_chart import show_practice_pace_chart
from practice_long_runs import show_practice_long_runs
from practice_fastest_runs import show_practice_fastest_runs
from practice_team_run_analysis import show_practice_team_run_analysis

PRACTICE_PATTERN = re.compile(r"_practice(\d+)\.csv$", re.IGNORECASE)
SESSION_PATTERN = re.compile(r"_session(\d+)\.csv$", re.IGNORECASE)


def parse_hour_to_seconds(x):
    """Parse HOUR (hh:mm:ss.000) to seconds since midnight."""
    try:
        h, m, s = str(x).split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return None


def parse_elapsed_to_seconds(x):
    """Parse ELAPSED (mm:ss.000 or h:mm:ss.000) to seconds."""
    try:
        parts = str(x).split(":")
        if len(parts) == 2:
            mins, secs = parts
            return int(mins) * 60 + float(secs)
        elif len(parts) == 3:
            hrs, mins, secs = parts
            return int(hrs) * 3600 + int(mins) * 60 + float(secs)
    except Exception:
        return None


def show_practice_analysis(
    data_dir: str,
    year: str,
    series: str,
    race: str,
    team_colors: dict
):
    """
    Practice / Test session analysis page.
    """

    st.subheader("Practice / Test Session Analysis")

    base_path = os.path.join(data_dir, year, series)

    if not os.path.isdir(base_path):
        st.error("Data directory not found.")
        return

    # --- Discover practice and session files ---
    practice_files = {}
    session_files = {}

    race_lower = race.lower()

    for filename in os.listdir(base_path):
        filename_lower = filename.lower()

        if not filename_lower.startswith(race_lower):
            continue

        match_practice = PRACTICE_PATTERN.search(filename_lower)
        if match_practice:
            session_number = int(match_practice.group(1))
            practice_files[session_number] = os.path.join(base_path, filename)
            continue

        match_session = SESSION_PATTERN.search(filename_lower)
        if match_session:
            session_number = int(match_session.group(1))
            session_files[session_number] = os.path.join(base_path, filename)
            continue

    # Use practice files if found, else session files
    if practice_files:
        available_sessions = sorted(practice_files.keys())
        files_to_load = practice_files
    elif session_files:
        available_sessions = sorted(session_files.keys())
        files_to_load = session_files
    else:
        st.warning("No practice/test session files found for this event.")
        return

    # --- Preload session durations ---
    session_durations = {}

    for session in available_sessions:
        try:
            df_tmp = pd.read_csv(files_to_load[session], delimiter=";")
        except Exception:
            continue

        df_tmp.columns = df_tmp.columns.str.strip()

        if "HOUR" not in df_tmp.columns or "ELAPSED" not in df_tmp.columns:
            continue

        df_tmp["HOUR_SECONDS"] = df_tmp["HOUR"].apply(parse_hour_to_seconds)
        df_tmp["ELAPSED_SECONDS"] = df_tmp["ELAPSED"].apply(parse_elapsed_to_seconds)

        df_tmp = df_tmp.dropna(subset=["HOUR_SECONDS", "ELAPSED_SECONDS"])

        if df_tmp.empty:
            continue

        # Session start = first car to cross the line
        start_hour = df_tmp["HOUR_SECONDS"].min()
        end_hour = df_tmp["HOUR_SECONDS"].max()
        duration_hour_sec = end_hour - start_hour

        # Cross-check with ELAPSED
        duration_elapsed_sec = df_tmp["ELAPSED_SECONDS"].max()

        # Prefer ELAPSED if within 2 minutes, else fall back to HOUR
        if abs(duration_hour_sec - duration_elapsed_sec) <= 120:
            session_minutes = duration_elapsed_sec / 60
        else:
            session_minutes = duration_hour_sec / 60

        session_durations[session] = round(session_minutes, 1)

    # --- Session selection UI ---
    st.markdown("### Session Selection")

    all_sessions_selected = st.checkbox("All sessions", value=True)

    selected_sessions = []

    for session in available_sessions:
        duration_str = ""
        if session in session_durations:
            duration_str = f" ({session_durations[session]} minutes)"

        checked = st.checkbox(
            f"Session {session}{duration_str}",
            value=all_sessions_selected,
            disabled=all_sessions_selected
        )
        if checked:
            selected_sessions.append(session)

    if not selected_sessions:
        st.warning("No sessions selected.")
        return

    # --- Load selected sessions ---
    session_dfs = []

    for session in selected_sessions:
        try:
            df_session = pd.read_csv(files_to_load[session], delimiter=";")
        except Exception as e:
            st.error(f"Failed to load Session {session}: {e}")
            return

        df_session.columns = df_session.columns.str.strip()
        df_session["PRACTICE_SESSION"] = f"Session {session}"

        session_dfs.append(df_session)

    df = pd.concat(session_dfs, ignore_index=True)
    df.columns = df.columns.str.strip()

    # --- Validation ---
    required_columns = {
        "LAP_TIME",
        "NUMBER",
        "TEAM",
        "CLASS",
        "DRIVER_NAME"
    }

    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        st.error(
            "Missing required columns for practice analysis: "
            + ", ".join(sorted(missing_columns))
        )
        return

    # --- Keep LAP_TIME as string and strip whitespace ---
    df["LAP_TIME"] = df["LAP_TIME"].astype(str).str.strip()

    # --- High-level metrics ---
    st.markdown("### Session Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Sessions", len(selected_sessions))

    with col2:
        st.metric("Total laps", len(df))

    with col3:
        st.metric("Cars", df["NUMBER"].nunique())

    with col4:
        st.metric("Drivers", df["DRIVER_NAME"].nunique())

    st.markdown("---")

    show_practice_fastest_laps(df)
    show_practice_pace_chart(df, team_colors)
    show_practice_long_runs(df, team_colors)
    show_practice_fastest_runs(df, team_colors)
    show_practice_team_run_analysis(df, team_colors)
