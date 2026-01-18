import os
import re
import pandas as pd
import streamlit as st

from pace_chart import show_pace_chart
from lap_position_chart import show_lap_position_chart
from driver_pace_chart import show_driver_pace_chart
from driver_pace_comparison_chart import show_driver_pace_comparison
from team_driver_pace_comparison import show_team_driver_pace_comparison
from results_table import show_results_table
from gap_evolution_chart import show_gap_evolution_chart
from stint_pace_chart import show_stint_pace_chart
from team_season_comparison import show_team_season_comparison
from track_analysis import show_track_analysis
from practice_analysis import show_practice_analysis

DATA_DIR = "data"

# Helper regexes
RACE_CSV_RE = re.compile(r"^(.+)\.csv$", re.IGNORECASE)
SESSION_CSV_RE = re.compile(r"^(.+?)_(practice|session)(\d+)\.csv$", re.IGNORECASE)

def get_event_names(series_path):
    """Return a dict mapping event base names to their race CSV (if any) and session CSVs."""
    events = {}
    for f in os.listdir(series_path):
        if not f.lower().endswith(".csv"):
            continue
        f_lower = f.lower()
        race_match = RACE_CSV_RE.match(f)
        session_match = SESSION_CSV_RE.match(f)
        if session_match:
            base_name = session_match.group(1).lower()
            event = events.setdefault(base_name, {"race_file": None, "sessions": []})
            event["sessions"].append(f)
        elif race_match:
            base_name = race_match.group(1).lower()
            event = events.setdefault(base_name, {"race_file": None, "sessions": []})
            event["race_file"] = f
    return events

# --- Load available race data ---
race_files = {}

for year in sorted(os.listdir(DATA_DIR)):
    year_path = os.path.join(DATA_DIR, year)
    if not os.path.isdir(year_path):
        continue

    series_dict = {}

    for series in sorted(os.listdir(year_path)):
        series_path = os.path.join(year_path, series)
        if not os.path.isdir(series_path):
            continue

        events = get_event_names(series_path)
        if events:
            series_dict[series] = events

    if series_dict:
        race_files[year] = series_dict

# --- Sidebar Selectors ---

st.sidebar.header("Configuration")

selected_series = st.sidebar.selectbox(
    "Series",
    ["IMSA", "FIA WEC"]
)

page = st.sidebar.selectbox(
    "Page",
    ["Overview", "Team by team", "Team season comparison", "Track analysis", "Practice / Test analysis"]
)

selected_year = st.sidebar.selectbox(
    "Year",
    sorted(race_files.keys(), reverse=True)
)

available_series_for_year = race_files[selected_year].keys()

if selected_series not in available_series_for_year:
    st.error(f"No {selected_series} data available for {selected_year}.")
    st.stop()

# Build the list of available races/events (race CSV or grouped sessions)
events_for_series = race_files[selected_year][selected_series]

def event_display_name(event_key, event_data):
    # Show event name with marker if grouped sessions only (no race CSV)
    if event_data["race_file"] is None and event_data["sessions"]:
        return f"{event_key.capitalize()} (Test Sessions)"
    else:
        return event_key.capitalize()

event_keys = sorted(events_for_series.keys())

display_names = [event_display_name(k, events_for_series[k]) for k in event_keys]

selected_event_idx = st.sidebar.selectbox(
    "Race",
    range(len(event_keys)),
    format_func=lambda i: display_names[i]
)

selected_event_key = event_keys[selected_event_idx]
selected_event = events_for_series[selected_event_key]

# --- Load data for the selected event ---

if page == "Overview" or page == "Team by team" or page == "Team season comparison" or page == "Track analysis":
    # For these pages, only allow loading a single CSV (race CSV)
    if selected_event["race_file"] is None:
        st.error(f"No main race CSV found for {selected_event_key}. Please select a proper race event.")
        st.stop()

    file_path = os.path.join(
        DATA_DIR,
        selected_year,
        selected_series,
        selected_event["race_file"]
    )

    if not os.path.isfile(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    df = pd.read_csv(file_path, delimiter=";")
    df.columns = df.columns.str.strip()
    if "\ufeffNUMBER" in df.columns:
        df.rename(columns={"\ufeffNUMBER": "NUMBER"}, inplace=True)

    # Aston Martin 007 / 009 fix (safe for IMSA/WEC)
    if {"TEAM", "NUMBER"}.issubset(df.columns):
        df["NUMBER"] = df.apply(
            lambda row: (
                "007"
                if row["TEAM"] == "Aston Martin Thor Team"
                and str(row["NUMBER"]).strip() == "7"
                else "009"
                if row["TEAM"] == "Aston Martin Thor Team"
                and str(row["NUMBER"]).strip() == "9"
                else str(row["NUMBER"]).lstrip("0")
            ),
            axis=1
        )

    df["NUMBER"] = df["NUMBER"].astype(str)

    # The rest of your sidebar filters and page logic come here...

elif page == "Practice / Test analysis":
    # For practice analysis page, load all session CSVs if grouped sessions,
    # else load race CSV as single session
    session_dfs = []
    if selected_event["sessions"]:
        # Load all sessions CSVs for this grouped event
        for session_file in sorted(selected_event["sessions"]):
            session_path = os.path.join(DATA_DIR, selected_year, selected_series, session_file)
            if not os.path.isfile(session_path):
                st.error(f"Session file not found: {session_path}")
                st.stop()
            try:
                df_session = pd.read_csv(session_path, delimiter=";")
                df_session.columns = df_session.columns.str.strip()
                # Add session label, e.g. "Practice 1" or "Session 1"
                match = SESSION_CSV_RE.match(session_file)
                session_type = match.group(2).capitalize()
                session_num = match.group(3)
                df_session["PRACTICE_SESSION"] = f"{session_type} {session_num}"
                session_dfs.append(df_session)
            except Exception as e:
                st.error(f"Failed to load session file {session_file}: {e}")
                st.stop()

        if not session_dfs:
            st.error("No session data files found for this event.")
            st.stop()

        df = pd.concat(session_dfs, ignore_index=True)
    else:
        # No sessions, just a race CSV
        if selected_event["race_file"] is None:
            st.error(f"No data files found for {selected_event_key}")
            st.stop()

        race_file_path = os.path.join(DATA_DIR, selected_year, selected_series, selected_event["race_file"])
        if not os.path.isfile(race_file_path):
            st.error(f"File not found: {race_file_path}")
            st.stop()

        df = pd.read_csv(race_file_path, delimiter=";")
        df.columns = df.columns.str.strip()
        if "\ufeffNUMBER" in df.columns:
            df.rename(columns={"\ufeffNUMBER": "NUMBER"}, inplace=True)
        df["PRACTICE_SESSION"] = "Race"

    # Aston Martin 007 / 009 fix (safe for IMSA/WEC)
    if {"TEAM", "NUMBER"}.issubset(df.columns):
        df["NUMBER"] = df.apply(
            lambda row: (
                "007"
                if row["TEAM"] == "Aston Martin Thor Team"
                and str(row["NUMBER"]).strip() == "7"
                else "009"
                if row["TEAM"] == "Aston Martin Thor Team"
                and str(row["NUMBER"]).strip() == "9"
                else str(row["NUMBER"]).lstrip("0")
            ),
            axis=1
        )

    df["NUMBER"] = df["NUMBER"].astype(str)

# --- Sidebar Filters ---

apply_global_filters = st.sidebar.checkbox(
    "Apply global filters",
    value=False
)

if "CLASS" in df.columns:
    available_classes = df["CLASS"].dropna().unique().tolist()
else:
    available_classes = []

selected_classes = st.sidebar.multiselect(
    "Select Classes",
    available_classes,
    default=available_classes,
    disabled=not apply_global_filters
)

available_cars = df["NUMBER"].unique().tolist()

selected_cars = st.sidebar.multiselect(
    "Select Cars",
    available_cars,
    default=available_cars,
    disabled=not apply_global_filters
)

top_percent = st.sidebar.slider(
    "Select Top Lap Percentage",
    0,
    100,
    100,
    step=20,
    help="Use 0% to hide all data.",
    disabled=not apply_global_filters
)

if top_percent == 0:
    st.warning("You selected 0%. You won't see any data.")

# --- Team color mapping ---

team_colors = {
    'Cadillac Hertz Team JOTA': '#d4af37',
    'Peugeot TotalEnergies': '#BBD64D',
    'Ferrari AF Corse': '#d62728',
    'Toyota Gazoo Racing': '#000000',
    'BMW M Team WRT': '#2426a8',
    'Porsche Penske Motorsport': '#ffffff',
    'Alpine Endurance Team': '#2673e2',
    'Aston Martin Thor Team': '#01655c',
    'AF Corse': '#FCE903',
    'Proton Competition': '#fcfcff',
    'WRT': '#2426a8',
    'United Autosports': '#FF8000',
    'Akkodis ASP': '#ff443b',
    'Iron Dames': '#e5017d',
    'Manthey': '#0192cf',
    'Heart of Racing': '#242c3f',
    'Racing Spirit of Leman': '#428ca8',
    'Iron Lynx': '#fefe00',
    'TF Sport': '#eaaa1d'
}

# --- Page Header ---
st.header(f"{selected_year} {selected_series} – {selected_event_key.capitalize()} Analysis")

# --- Show charts ---

if page == "Overview":
    show_pace_chart(df, team_colors)
    show_driver_pace_chart(df, team_colors)
    show_lap_position_chart(df, team_colors)
    show_driver_pace_comparison(df, team_colors)
    show_results_table(df, team_colors)
    show_gap_evolution_chart(df, team_colors)
    show_stint_pace_chart(df, team_colors)

elif page == "Team by team":
    race_classes = sorted(df["CLASS"].dropna().unique())

    if not race_classes:
        st.warning("No class data available in this race.")
    else:
        tabs = st.tabs(race_classes)

        for tab, race_class in zip(tabs, race_classes):
            with tab:
                st.subheader(f"{race_class}")

                class_df = df[df["CLASS"] == race_class]

                if class_df.empty:
                    st.info("No data available for this class in this race.")
                else:
                    show_team_driver_pace_comparison(class_df, team_colors)

elif page == "Team season comparison":
    show_team_season_comparison(df, team_colors)

elif page == "Track analysis":
    show_track_analysis(df, team_colors)

elif page == "Practice / Test analysis":
    show_practice_analysis(
        data_dir=DATA_DIR,
        year=selected_year,
        series=selected_series,
        race=selected_event_key,
        team_colors=team_colors
    )
