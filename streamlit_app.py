"""
streamlit_app.py — On The Apex race data analyser.

Directory structure: data/{SERIES}/{year}/{race}/{session_type}/{file}.csv
"""

import os
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
# File index
# ---------------------------------------------------------------------------
race_files = load_file_index(DATA_DIR)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("On The Apex")

    page = st.selectbox(
        "Page",
        [
            "Overview",
            "Team by team",
            "Team season comparison",
            "Track analysis",
            "Practice / Test analysis",
            "Qualifying analysis",
            "⬇ Download CSVs",
        ],
    )

    if page == "⬇ Download CSVs":
        pass  # no data selectors needed
    else:
        # Series
        folder_to_display = SERIES_DISPLAY
        display_to_folder = {v: k for k, v in folder_to_display.items()}

        available_series_folders = sorted(race_files.keys())
        # Show display names where we have one, else the folder name itself
        series_options = [
            folder_to_display.get(s, s) for s in available_series_folders
        ]
        selected_series_display = st.selectbox("Series", series_options)
        selected_series = display_to_folder.get(
            selected_series_display, selected_series_display
        )

        # Year
        years_for_series = sorted(
            race_files.get(selected_series, {}).keys(), reverse=True
        )
        if not years_for_series:
            st.error(f"No data found for {selected_series_display}.")
            st.stop()
        selected_year = st.selectbox("Year", years_for_series)

        # Race
        races_for_year = sorted(
            race_files.get(selected_series, {}).get(selected_year, {}).keys()
        )
        if not races_for_year:
            st.error(f"No races found for {selected_series_display} {selected_year}.")
            st.stop()
        selected_race = st.selectbox(
            "Race",
            races_for_year,
            format_func=lambda r: r.replace("-", " ").title(),
        )

        # Session type (what's available for this race)
        sessions_available = race_files[selected_series][selected_year][selected_race]
        session_type_options = list(sessions_available.keys())

        # Default to race if available, otherwise first available
        default_idx = (
            session_type_options.index("race")
            if "race" in session_type_options
            else 0
        )
        selected_session_type = st.selectbox(
            "Session type",
            session_type_options,
            index=default_idx,
            format_func=str.title,
        )

# ---------------------------------------------------------------------------
# Download page — render immediately, no race data needed
# ---------------------------------------------------------------------------
if page == "⬇ Download CSVs":
    st.title("⬇ Download Al-Kamel CSVs")
    from pages.downloader import show_downloader
    show_downloader()
    st.stop()

# ---------------------------------------------------------------------------
# Load data for the selected session
# ---------------------------------------------------------------------------
session_dir = os.path.join(
    DATA_DIR, selected_series, selected_year, selected_race, selected_session_type
)
session_files = sessions_available[selected_session_type]

df = None
race_start_date = None

if selected_session_type == "race":
    if not session_files:
        st.error("No race CSV found in this folder.")
        st.stop()
    file_path = os.path.join(session_dir, session_files[0])
    df = load_race(file_path, selected_year, selected_series)
    race_start_date = parse_race_start_date(session_files[0])

elif selected_session_type in ("practice", "qualifying"):
    # Loaded on-demand by the practice/qualifying page
    pass

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
race_display = selected_race.replace("-", " ").title()
st.title(
    f"🏁 {selected_year} {selected_series_display} — "
    f"{race_display} / {selected_session_type.title()}"
)

# ---------------------------------------------------------------------------
# Route to pages
# ---------------------------------------------------------------------------
if page == "Overview":
    if selected_session_type != "race":
        st.info("Overview is available for race sessions. Please select 'race' as the session type.")
    else:
        from pages.overview import show_overview
        show_overview(df, race_start_date, TEAM_COLORS)

elif page == "Team by team":
    if selected_session_type != "race":
        st.info("Team by team is available for race sessions.")
    else:
        from pages.team_by_team import show_team_by_team
        show_team_by_team(df, TEAM_COLORS)

elif page == "Team season comparison":
    from pages.season_comparison import show_season_comparison
    show_season_comparison(df, TEAM_COLORS, selected_year, selected_series)

elif page == "Track analysis":
    from pages.track import show_track
    show_track(df, TEAM_COLORS)

elif page == "Practice / Test analysis":
    if selected_session_type != "practice":
        st.info("Switch session type to 'practice' to use this page.")
    else:
        from pages.practice import show_practice
        show_practice(
            session_dir=session_dir,
            session_files=session_files,
            team_colors=TEAM_COLORS,
        )

elif page == "Qualifying analysis":
    if selected_session_type != "qualifying":
        st.info("Switch session type to 'qualifying' to use this page.")
    else:
        from pages.qualifying import show_qualifying
        show_qualifying(
            session_dir=session_dir,
            session_files=session_files,
            team_colors=TEAM_COLORS,
        )

# ---------------------------------------------------------------------------
# Debug expander
# ---------------------------------------------------------------------------
if df is not None:
    with st.expander("Debug: Car IDs", expanded=False):
        debug_df = (
            df[["CAR_ID", "NUMBER", "TEAM", "CLASS"]]
            .drop_duplicates()
            .sort_values(["CLASS", "TEAM", "NUMBER"])
            .reset_index(drop=True)
        )
        st.dataframe(debug_df, width='stretch', hide_index=True)
