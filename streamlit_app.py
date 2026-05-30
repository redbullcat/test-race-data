"""
streamlit_app.py — On The Apex race data analyser.

Entry point. Handles sidebar navigation and passes context to page modules.
Chart logic lives in pages/; shared utilities in utils.py and data_loader.py.
"""

import streamlit as st

from config import DATA_DIR, TEAM_COLORS, SERIES_DISPLAY
from data_loader import load_file_index, load_race, parse_race_start_date

st.set_page_config(
    page_title="On The Apex",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# File index (cached — only rebuilt when the data directory changes)
# ---------------------------------------------------------------------------
race_files = load_file_index(DATA_DIR)

import os
st.write("Working directory:", os.getcwd())
st.write("DATA_DIR:", DATA_DIR)
st.write("DATA_DIR exists:", os.path.exists(DATA_DIR))
if os.path.exists(DATA_DIR):
    st.write("Contents:", os.listdir(DATA_DIR))
st.write("race_files:", race_files)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("On The Apex")

    # Series selector — show display names, map back to folder names
    folder_to_display = SERIES_DISPLAY
    display_to_folder = {v: k for k, v in folder_to_display.items()}
    all_display_names = list(folder_to_display.values())

    selected_series_display = st.selectbox("Series", all_display_names)
    selected_series = display_to_folder.get(selected_series_display, selected_series_display)

    selected_year = st.selectbox("Year", sorted(race_files.keys(), reverse=True))

    available_series = race_files.get(selected_year, {})
    if selected_series not in available_series:
        st.error(f"No {selected_series_display} data available for {selected_year}.")
        st.stop()

    events = available_series[selected_series]
    event_keys = sorted(events.keys())

    def _event_label(key):
        event = events[key]
        if event["race_file"] is None and event["sessions"]:
            return f"{key.replace('_', ' ').title()} (Practice)"
        return key.replace("_", " ").title()

    selected_event_idx = st.selectbox(
        "Event",
        range(len(event_keys)),
        format_func=lambda i: _event_label(event_keys[i]),
    )
    selected_event_key = event_keys[selected_event_idx]
    selected_event = events[selected_event_key]

    page = st.selectbox(
        "Page",
        [
            "Overview",
            "Team by team",
            "Team season comparison",
            "Track analysis",
            "Practice / Test analysis",
        ],
    )

# ---------------------------------------------------------------------------
# Load race data (skipped for practice-only page)
# ---------------------------------------------------------------------------
df = None
df_pre = None
race_start_date = None

if page != "Practice / Test analysis":
    if selected_event["race_file"] is None:
        st.error(f"No main race CSV found for {selected_event_key}.")
        st.stop()

    file_path = f"{DATA_DIR}/{selected_year}/{selected_series}/{selected_event['race_file']}"
    df = load_race(file_path, selected_year, selected_series)
    race_start_date = parse_race_start_date(selected_event["race_file"])

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title(f"🏁 {selected_year} {selected_series_display} — {selected_event_key.replace('_', ' ').title()}")

# ---------------------------------------------------------------------------
# Route to pages
# ---------------------------------------------------------------------------
if page == "Overview":
    from pages.overview import show_overview
    show_overview(df, race_start_date, TEAM_COLORS)

elif page == "Team by team":
    from pages.team_by_team import show_team_by_team
    show_team_by_team(df, TEAM_COLORS)

elif page == "Team season comparison":
    from pages.season_comparison import show_season_comparison
    show_season_comparison(df, TEAM_COLORS, selected_year, selected_series)

elif page == "Track analysis":
    from pages.track import show_track
    show_track(df, TEAM_COLORS)

elif page == "Practice / Test analysis":
    from pages.practice import show_practice
    show_practice(DATA_DIR, selected_year, selected_series, selected_event_key, TEAM_COLORS)

# ---------------------------------------------------------------------------
# Debug expander (only when race data loaded)
# ---------------------------------------------------------------------------
if df is not None:
    with st.expander("Debug: Car IDs", expanded=False):
        debug_df = (
            df[["CAR_ID", "NUMBER", "TEAM", "CLASS"]]
            .drop_duplicates()
            .sort_values(["CLASS", "TEAM", "NUMBER"])
            .reset_index(drop=True)
        )
        st.dataframe(debug_df, use_container_width=True, hide_index=True)
