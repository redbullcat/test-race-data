import os
import re
import pandas as pd
import streamlit as st
import plotly.express as px

from practice_fastest_laps_table import show_practice_fastest_laps
from practice_pace_chart import show_practice_pace_chart
from practice_long_runs import show_practice_long_runs
from practice_fastest_runs import show_practice_fastest_runs
from practice_team_run_analysis import show_practice_team_run_analysis

PRACTICE_PATTERN = re.compile(r"_practice(\d+)\.csv$", re.IGNORECASE)
SESSION_PATTERN = re.compile(r"_session(\d+)\.csv$", re.IGNORECASE)


def parse_hour_to_seconds(x):
    try:
        h, m, s = str(x).split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return None


def parse_elapsed_to_seconds(x):
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


def get_longest_stints(df, selected_classes, selected_cars, top_percent):
    # Filter classes and cars
    filtered_df = df[df["CLASS"].isin(selected_classes) & df["NUMBER"].isin(selected_cars)].copy()

    # Convert LAP_TIME to seconds
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except Exception:
            return None

    filtered_df["LAP_TIME_SECONDS"] = filtered_df["LAP_TIME"].apply(lap_to_seconds)
    filtered_df = filtered_df.dropna(subset=["LAP_TIME_SECONDS"])

    # Filter top X% fastest laps per car
    def filter_top_percent_laps(df_inner, percent):
        filtered_dfs = []
        for car_number, group in df_inner.groupby("NUMBER"):
            group_sorted = group.sort_values("LAP_TIME_SECONDS")
            n_laps = len(group_sorted)
            n_keep = max(1, int(n_laps * percent / 100))
            filtered_dfs.append(group_sorted.head(n_keep))
        return pd.concat(filtered_dfs)

    filtered_df = filter_top_percent_laps(filtered_df, top_percent)

    longest_runs = []

    for car_number, group in filtered_df.groupby("NUMBER"):
        if "LAP_NUMBER" in group.columns:
            group = group.sort_values(["PRACTICE_SESSION", "LAP_NUMBER"]).reset_index(drop=True)
        else:
            group = group.sort_values("PRACTICE_SESSION").reset_index(drop=True)

        max_stint = []
        max_stint_session = None
        current_stint = []
        current_stint_session = None
        skip_next = False

        for _, row in group.iterrows():
            if skip_next:
                skip_next = False
                continue

            if str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B":
                if current_stint and len(current_stint) > len(max_stint):
                    max_stint = current_stint
                    max_stint_session = current_stint_session
                current_stint = []
                current_stint_session = None
                skip_next = True
                continue

            if not current_stint:
                current_stint_session = row["PRACTICE_SESSION"]

            current_stint.append(row)

        if current_stint and len(current_stint) > len(max_stint):
            max_stint = current_stint
            max_stint_session = current_stint_session

        if not max_stint:
            continue

        stint_df = pd.DataFrame(max_stint)

        longest_runs.append({
            "Car": car_number,
            "Team": stint_df.iloc[0]["TEAM"] if "TEAM" in stint_df.columns else "",
            "Class": stint_df.iloc[0]["CLASS"] if "CLASS" in stint_df.columns else "",
            "Lap_Times": stint_df["LAP_TIME_SECONDS"].tolist(),
            "Lap_Numbers": stint_df["LAP_NUMBER"].tolist() if "LAP_NUMBER" in stint_df.columns else list(range(1, len(stint_df) + 1)),
            "Stint_Length": len(stint_df),
            "Session": max_stint_session
        })

    return pd.DataFrame(longest_runs)


def show_longest_stint_pace(long_runs_df, team_colors):
    if long_runs_df.empty:
        st.warning("No valid longest stint data to show.")
        return

    # Prepare data for plotting: each lap per car
    plot_data = []

    for _, row in long_runs_df.iterrows():
        for lap_idx, lap_time in enumerate(row["Lap_Times"], start=1):
            plot_data.append({
                "Car": row["Car"],
                "Team": row["Team"],
                "Lap": lap_idx,
                "Lap Time (s)": lap_time,
            })

    plot_df = pd.DataFrame(plot_data)

    # Color mapping helper
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"

    plot_df["Color"] = plot_df["Team"].apply(get_team_color)

    fig = px.line(
        plot_df,
        x="Lap",
        y="Lap Time (s)",
        color="Car",
        color_discrete_map={car: clr for car, clr in zip(plot_df["Car"], plot_df["Color"])},
        markers=True,
        title="Longest Stint Pace by Lap per Car",
        labels={"Lap": "Lap Number in Stint", "Lap Time (s)": "Lap Time (seconds)"}
    )

    fig.update_yaxes(autorange="reversed", title="Lap Time (seconds) (Faster at bottom)")
    fig.update_xaxes(dtick=1)
    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white"),
        legend_title_text="Car Number"
    )

    st.plotly_chart(fig, use_container_width=True)


def show_practice_analysis(
    data_dir: str,
    year: str,
    series: str,
    race: str,
    team_colors: dict
):
    st.subheader("Practice / Test Session Analysis")

    base_path = os.path.join(data_dir, year, series)

    if not os.path.isdir(base_path):
        st.error("Data directory not found.")
        return

    # Discover practice and session files
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

    # Preload session durations
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

    # Session selection UI
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

    # Load selected sessions
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

    # Filters for class and car for longest stint charts
    classes = sorted(df["CLASS"].dropna().unique().tolist())
    selected_classes = st.multiselect(
        "Select Class(es) for Longest Stint Charts:",
        options=classes,
        default=classes,
        key="longest_stint_class_filter"
    )

    available_cars = sorted(df[df["CLASS"].isin(selected_classes)]["NUMBER"].unique().tolist())
    selected_cars = st.multiselect(
        "Select Car(s) for Longest Stint Charts:",
        options=available_cars,
        default=available_cars,
        key="longest_stint_car_filter"
    )

    top_percent = st.slider(
        "Select Top Lap Percentage for Longest Stint Charts:",
        0,
        100,
        100,
        step=20,
        key="longest_stint_top_lap_filter",
        help="Use 0% to hide all data."
    )

    if top_percent == 0:
        st.warning("You selected 0%. You won't see any data for the longest stint charts.")
        return

    # Get preprocessed longest stint data
    longest_stints_df = get_longest_stints(df, selected_classes, selected_cars, top_percent)

    # --- Session Overview ---
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

    with st.expander("Long Runs - Average Pace by Car", expanded=True):
        show_practice_long_runs(df, team_colors)

    with st.expander("Longest Stint Pace by Lap per Car", expanded=True):
        show_longest_stint_pace(longest_stints_df, team_colors)

    with st.expander("Fastest Runs", expanded=True):
        show_practice_fastest_runs(df, team_colors)

    with st.expander("Team Run Analysis", expanded=True):
        show_practice_team_run_analysis(df, team_colors)
