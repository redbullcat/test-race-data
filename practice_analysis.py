import os
import re
import pandas as pd
import streamlit as st

from practice_fastest_laps_table import show_practice_fastest_laps

PRACTICE_PATTERN = re.compile(r"_practice(\d+)\.csv$", re.IGNORECASE)

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

    # --- Discover practice sessions ---
    practice_files = {}

    for filename in os.listdir(base_path):
        if not filename.lower().startswith(race.lower()):
            continue

        match = PRACTICE_PATTERN.search(filename)
        if match:
            session_number = int(match.group(1))
            practice_files[session_number] = os.path.join(base_path, filename)

    if not practice_files:
        st.warning("No practice/test session files found for this event.")
        return

    available_sessions = sorted(practice_files.keys())

    # --- Session selection UI ---
    st.markdown("### Session Selection")

    all_sessions_selected = st.checkbox("All sessions", value=True)

    selected_sessions = []

    for session in available_sessions:
        checked = st.checkbox(
            f"Practice {session}",
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
            df_session = pd.read_csv(practice_files[session], delimiter=";")
        except Exception as e:
            st.error(f"Failed to load Practice {session}: {e}")
            return

        df_session.columns = df_session.columns.str.strip()
        df_session["PRACTICE_SESSION"] = f"Practice {session}"

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
