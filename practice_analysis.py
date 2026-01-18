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


def get_longest_stints(df):
    """
    Calculate the longest no-pit stint per car across all sessions,
    excluding out-laps and in-laps defined by laps crossing finish line in pits ('B').

    Returns a DataFrame with columns:
    - Car
    - Team
    - Manufacturer
    - Class
    - Drivers (string)
    - Lap_Numbers (list)
    - Lap_Times (list of seconds)
    - Stint_Length
    - Average_Lap_Time_Seconds
    - Average_20_Percent_Pace
    - Session
    """
    # Ensure LAP_TIME_SECONDS exists
    if "LAP_TIME_SECONDS" not in df.columns:
        def lap_to_seconds(x):
            try:
                mins, secs = x.split(":")
                return int(mins) * 60 + float(secs)
            except Exception:
                return None
        df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)

    df = df.dropna(subset=["LAP_TIME_SECONDS"])

    longest_runs = []

    for car_number, car_group in df.groupby("NUMBER"):
        max_stint = []
        max_stint_session = None
        max_stint_len = 0

        # Group by session within car
        for session_name, session_group in car_group.groupby("PRACTICE_SESSION"):
            # Sort by LAP_NUMBER for proper sequence
            if "LAP_NUMBER" in session_group.columns:
                session_group = session_group.sort_values("LAP_NUMBER").reset_index(drop=True)
            else:
                session_group = session_group.reset_index(drop=True)

            current_stint = []
            current_stint_session = None
            skip_next = False  # to skip lap after 'B' lap (in-lap)

            for idx, row in session_group.iterrows():
                if skip_next:
                    # Skip the in-lap right after a 'B' lap
                    skip_next = False
                    continue

                crossing_pit = str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B"

                if crossing_pit:
                    # End current stint at previous lap (exclude this pit lap and previous lap)
                    if current_stint:
                        # Remove last lap from current_stint (the out-lap before pit)
                        if len(current_stint) > 0:
                            current_stint = current_stint[:-1]

                        if len(current_stint) > max_stint_len:
                            max_stint = current_stint
                            max_stint_session = session_name
                            max_stint_len = len(current_stint)

                    current_stint = []
                    current_stint_session = None
                    skip_next = True  # skip next lap (in-lap)
                    continue

                # Add laps to current stint only if not out-lap or in-lap
                if not current_stint:
                    current_stint_session = session_name

                current_stint.append(row)

            # Final check after loop for this session
            if current_stint and len(current_stint) > max_stint_len:
                max_stint = current_stint
                max_stint_session = session_name
                max_stint_len = len(current_stint)

        if not max_stint:
            continue

        stint_df = pd.DataFrame(max_stint)

        # Prepare data for output
        lap_times = stint_df["LAP_TIME_SECONDS"].tolist()
        lap_numbers = stint_df["LAP_NUMBER"].tolist() if "LAP_NUMBER" in stint_df.columns else list(range(1, len(lap_times) + 1))
        avg_lap_time = sum(lap_times) / len(lap_times) if lap_times else None

        # Calculate average 20% pace (fastest 20% laps average)
        lap_times_sorted = sorted(lap_times)
        top_20_count = max(1, int(len(lap_times_sorted) * 0.2))
        avg_20_pace = sum(lap_times_sorted[:top_20_count]) / top_20_count if lap_times_sorted else None

        team = stint_df.iloc[0]["TEAM"] if "TEAM" in stint_df.columns else ""
        manufacturer = stint_df.iloc[0]["MANUFACTURER"] if "MANUFACTURER" in stint_df.columns else ""
        race_class = stint_df.iloc[0]["CLASS"] if "CLASS" in stint_df.columns else ""

        drivers = stint_df["DRIVER_NAME"].dropna().unique()
        drivers_str = " / ".join(drivers)

        longest_runs.append({
            "Car": car_number,
            "Team": team,
            "Manufacturer": manufacturer,
            "Class": race_class,
            "Drivers": drivers_str,
            "Lap_Numbers": lap_numbers,
            "Lap_Times": lap_times,
            "Average_Lap_Time_Seconds": avg_lap_time,
            "Average_20_Percent_Pace": avg_20_pace,
            "Stint_Length": len(lap_times),
            "Session": max_stint_session
        })

    return pd.DataFrame(longest_runs)


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

        start_hour = df_tmp["HOUR_SECONDS"].min()
        end_hour = df_tmp["HOUR_SECONDS"].max()
        duration_hour_sec = end_hour - start_hour
        duration_elapsed_sec = df_tmp["ELAPSED_SECONDS"].max()

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
        df_session = pd.read_csv(files_to_load[session], delimiter=";")
        df_session.columns = df_session.columns.str.strip()
        df_session["PRACTICE_SESSION"] = f"Session {session}"
        session_dfs.append(df_session)

    df = pd.concat(session_dfs, ignore_index=True)
    df.columns = df.columns.str.strip()

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

    df["LAP_TIME"] = df["LAP_TIME"].astype(str).str.strip()

    # --- Session Overview (always visible) ---
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

    # --- Collapsible chart sections ---
    with st.expander("Fastest Laps", expanded=True):
        show_practice_fastest_laps(df)

    with st.expander("Pace Chart", expanded=True):
        show_practice_pace_chart(df, team_colors)

    # --- Calculate longest stints once ---
    longest_stints_df = get_longest_stints(df)

    with st.expander("Long Runs", expanded=True):
        show_practice_long_runs(longest_stints_df, team_colors)

    with st.expander("Fastest Runs", expanded=True):
        show_practice_fastest_runs(df, team_colors)

    with st.expander("Team Run Analysis", expanded=True):
        show_practice_team_run_analysis(df, team_colors)
