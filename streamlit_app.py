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
from race_stats import show_race_stats   # ← NEW IMPORT

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

selected_series = st.sidebar.selectbox("Series", ["IMSA", "FIA WEC"])

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

events_for_series = race_files[selected_year][selected_series]

def event_display_name(event_key, event_data):
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

# --- Load data ---
if page in ["Overview", "Team by team", "Team season comparison", "Track analysis"]:
    if selected_event["race_file"] is None:
        st.error(f"No main race CSV found for {selected_event_key}.")
        st.stop()

    file_path = os.path.join(DATA_DIR, selected_year, selected_series, selected_event["race_file"])
    df = pd.read_csv(file_path, delimiter=";")
    df.columns = df.columns.str.strip()

    if "\ufeffNUMBER" in df.columns:
        df.rename(columns={"\ufeffNUMBER": "NUMBER"}, inplace=True)

    # Add YEAR and SERIES columns for CAR_ID construction
    df["YEAR"] = selected_year
    df["SERIES"] = selected_series

    # Ensure TEAM and NUMBER are strings with no leading zero stripping
    df["NUMBER"] = df["NUMBER"].astype(str).str.strip()
    df["TEAM"] = df["TEAM"].astype(str).str.strip()

    # Create unique CAR_ID by combining YEAR_SERIES_TEAM_NUMBER
    df["CAR_ID"] = (
        df["YEAR"].astype(str) + "_" +
        df["SERIES"].astype(str) + "_" +
        df["TEAM"] + "_" +
        df["NUMBER"]
    )

# --- Page Header ---
st.header(f"{selected_year} {selected_series} – {selected_event_key.capitalize()} Analysis")

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
    'TF Sport': '#eaaa1d', 
    'Cadillac Wayne Taylor Racing': '#0E3463', 
    'JDC-Miller MotorSports': '#F8D94A', 
    'Acura Meyer Shank Racing w/Curb Agajanian': '#E6662C', 
    'Cadillac Whelen': '#D53C35' }

# --- Pages ---
if page == "Overview":
    show_race_stats(df)          # ← NEW STATS SECTION
    show_pace_chart(df, team_colors)
    show_driver_pace_chart(df, team_colors)
    show_lap_position_chart(df, team_colors)
    show_driver_pace_comparison(df, team_colors)
    show_results_table(df, team_colors)
    show_gap_evolution_chart(df, team_colors)
    show_stint_pace_chart(df, team_colors)

elif page == "Team by team":
    race_classes = sorted(df["CLASS"].dropna().unique())
    if race_classes:
        tabs = st.tabs(race_classes)
        for tab, race_class in zip(tabs, race_classes):
            with tab:
                class_df = df[df["CLASS"] == race_class]
                if not class_df.empty:
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

# --- Debug: Car ID table ---
with st.expander("Debug: Car IDs"):
    debug_df = (
        df[["CAR_ID", "NUMBER", "TEAM", "CLASS"]]
        .drop_duplicates()
        .sort_values(["CLASS", "TEAM", "NUMBER"])
        .reset_index(drop=True)
    )

    st.dataframe(
        debug_df,
        use_container_width=True,
        hide_index=True
    )
