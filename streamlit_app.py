"""
streamlit_app.py — On The Apex race data analyser.

Directory structure: data/{SERIES}/{year}/{event}/{session_type}/{file}.csv

Session types: race, practice, qualifying, test
  - race/       → race analysis CSVs
  - practice/   → practice session CSVs (race weekend)
  - qualifying/ → qualifying CSVs
  - test/       → standalone test/prologue/Roar sessions

Events with a race/ folder are race weekends.
Events with only a test/ folder are test events (Prologue, Roar, etc.)
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
# Helpers
# ---------------------------------------------------------------------------

TEST_KEYWORDS = ("test", "prologue", "roar", "rookie", "official")

def is_test_event(event_slug: str) -> bool:
    return any(kw in event_slug.lower() for kw in TEST_KEYWORDS)

def event_has_race(event_sessions: dict) -> bool:
    return "race" in event_sessions

def format_event(slug: str) -> str:
    return slug.replace("-", " ").title()

# ---------------------------------------------------------------------------
# Sidebar — Series / Year / Event
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("On The Apex")
    st.caption("Motorsport race data analysis")

    # Series
    folder_to_display = SERIES_DISPLAY
    display_to_folder = {v: k for k, v in folder_to_display.items()}
    available_series = sorted(race_files.keys())
    series_options = [folder_to_display.get(s, s) for s in available_series]
    selected_series_display = st.selectbox("Series", series_options)
    selected_series = display_to_folder.get(selected_series_display, selected_series_display)

    # Year
    years = sorted(race_files.get(selected_series, {}).keys(), reverse=True)
    if not years:
        st.error(f"No data for {selected_series_display}.")
        st.stop()
    selected_year = st.selectbox("Year", years)

    # All events for this year
    all_events = race_files.get(selected_series, {}).get(selected_year, {})
    if not all_events:
        st.error(f"No events for {selected_series_display} {selected_year}.")
        st.stop()

    # Split into race weekends and test events
    race_weekend_events = {
        slug: sessions for slug, sessions in all_events.items()
        if event_has_race(sessions) or (
            not is_test_event(slug) and any(
                s in sessions for s in ("practice", "qualifying")
            )
        )
    }
    test_events = {
        slug: sessions for slug, sessions in all_events.items()
        if slug not in race_weekend_events
    }

    # Section selector
    st.divider()
    sections = ["🏁 Race Weekend", "🔧 Tests", "📅 Season", "⬇ Data"]

    # Pre-select based on available data
    section = st.radio("Section", sections, label_visibility="collapsed")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

if section == "⬇ Data":
    st.title("⬇ Download Al-Kamel CSVs")
    from pages.downloader import show_downloader
    show_downloader()
    st.stop()

# ---------------------------------------------------------------------------
# Season section
# ---------------------------------------------------------------------------
if section == "📅 Season":
    st.title(f"📅 {selected_year} {selected_series_display} — Season")
    season_tab, track_tab = st.tabs(["Season comparison", "Track analysis"])
    with season_tab:
        from pages.season_comparison import show_season_comparison
        show_season_comparison(None, TEAM_COLORS, selected_year, selected_series)
    with track_tab:
        from pages.track import show_track
        show_track(None, TEAM_COLORS)
    st.stop()

# ---------------------------------------------------------------------------
# Tests section
# ---------------------------------------------------------------------------
if section == "🔧 Tests":
    if not test_events:
        st.info(f"No test events found for {selected_series_display} {selected_year}.")
        st.stop()

    with st.sidebar:
        selected_test = st.selectbox(
            "Test event",
            sorted(test_events.keys()),
            format_func=format_event,
        )

    test_sessions = test_events[selected_test]
    st.title(f"🔧 {selected_year} {selected_series_display} — {format_event(selected_test)}")

    # Test events typically have test/ or practice/ sessions
    available_test_sessions = {
        k: v for k, v in test_sessions.items()
        if k in ("test", "practice")
    }
    if not available_test_sessions:
        st.info("No session data found for this test event.")
        st.stop()

    # Use whichever session type is available (prefer test over practice)
    session_type = "test" if "test" in available_test_sessions else "practice"
    session_dir = os.path.join(DATA_DIR, selected_series, selected_year, selected_test, session_type)
    session_files = available_test_sessions[session_type]

    from practice_analysis import show_practice_analysis
    show_practice_analysis(
        session_dir=session_dir,
        session_files=session_files,
        team_colors=TEAM_COLORS,
        key_prefix="test",
    )
    st.stop()

# ---------------------------------------------------------------------------
# Race Weekend section
# ---------------------------------------------------------------------------
if not race_weekend_events:
    st.info(f"No race weekend events found for {selected_series_display} {selected_year}.")
    st.stop()

with st.sidebar:
    selected_event = st.selectbox(
        "Event",
        sorted(race_weekend_events.keys()),
        format_func=format_event,
    )

event_sessions = race_weekend_events[selected_event]
event_display = format_event(selected_event)

st.title(f"🏁 {selected_year} {selected_series_display} — {event_display}")

# ---------------------------------------------------------------------------
# Race Weekend tabs — Practice / Qualifying / Race
# Greyed out (disabled) if session data not available
# ---------------------------------------------------------------------------

has_practice   = "practice"   in event_sessions
has_qualifying = "qualifying" in event_sessions
has_race       = "race"       in event_sessions

# Build tab labels with indicator if no data
def tab_label(label: str, available: bool) -> str:
    return label if available else f"{label} (no data)"

tab_labels = [
    tab_label("Practice", has_practice),
    tab_label("Qualifying", has_qualifying),
    tab_label("Race", has_race),
]

practice_tab, qualifying_tab, race_tab = st.tabs(tab_labels)

# ---------------------------------------------------------------------------
# Practice tab
# ---------------------------------------------------------------------------
with practice_tab:
    if not has_practice:
        st.info("No practice data available for this event.")
    else:
        session_dir = os.path.join(DATA_DIR, selected_series, selected_year, selected_event, "practice")
        session_files = event_sessions["practice"]
        from pages.practice import show_practice
        show_practice(session_dir=session_dir, session_files=session_files, team_colors=TEAM_COLORS)

# ---------------------------------------------------------------------------
# Qualifying tab
# ---------------------------------------------------------------------------
with qualifying_tab:
    if not has_qualifying:
        st.info("No qualifying data available for this event.")
    else:
        session_dir = os.path.join(DATA_DIR, selected_series, selected_year, selected_event, "qualifying")
        session_files = event_sessions["qualifying"]
        from pages.qualifying import show_qualifying
        show_qualifying(session_dir=session_dir, session_files=session_files, team_colors=TEAM_COLORS)

# ---------------------------------------------------------------------------
# Race tab
# ---------------------------------------------------------------------------
with race_tab:
    if not has_race:
        st.info("No race data available for this event.")
    else:
        session_dir = os.path.join(DATA_DIR, selected_series, selected_year, selected_event, "race")
        session_files = event_sessions["race"]
        file_path = os.path.join(session_dir, session_files[0])

        df = load_race(file_path, selected_year, selected_series)
        race_start_date = parse_race_start_date(session_files[0])

        if race_start_date is None:
            st.warning(
                "Race start date not found in filename — gap evolution will be unavailable. "
                "Run `add_dates_to_race_files.py` to add dates."
            )

        # Class filter — persistent across all race sub-tabs
        classes = sorted(df["CLASS"].dropna().unique())
        if len(classes) > 1:
            selected_class_filter = st.selectbox(
                "Class", ["All classes"] + classes, key="race_class_filter"
            )
            if selected_class_filter != "All classes":
                df_filtered = df[df["CLASS"] == selected_class_filter].copy()
            else:
                df_filtered = df
        else:
            df_filtered = df
            selected_class_filter = classes[0] if classes else "All"

        results_tab, pace_tab, battle_tab, pits_tab, team_tab = st.tabs([
            "Results", "Pace", "Battle", "Pit stops", "Team by team"
        ])

        with results_tab:
            from race_stats import show_race_stats
            from results_table import show_results_table
            from lap_position_chart import show_lap_position_chart
            if race_start_date:
                show_race_stats(df_filtered, race_start_date)
            show_results_table(df_filtered, TEAM_COLORS)
            show_lap_position_chart(df_filtered, TEAM_COLORS)

        with pace_tab:
            from pace_chart import show_pace_chart
            from driver_pace_chart import show_driver_pace_chart
            from driver_pace_comparison_chart import show_driver_pace_comparison
            from stint_pace_chart import show_stint_pace_chart
            show_pace_chart(df_filtered, TEAM_COLORS)
            show_driver_pace_chart(df_filtered, TEAM_COLORS)
            show_driver_pace_comparison(df_filtered, TEAM_COLORS)
            show_stint_pace_chart(df_filtered, TEAM_COLORS)

        with battle_tab:
            from gap_evolution_chart import get_filtered_race_data, show_gap_evolution_chart, show_cumulative_time_chart
            if race_start_date is None:
                st.info("Gap evolution requires a race start date in the filename.")
            else:
                filtered_df, selected_class, selected_cars, lap_range = get_filtered_race_data(
                    df_filtered, race_start_date
                )
                if filtered_df is not None:
                    show_gap_evolution_chart(filtered_df, TEAM_COLORS, selected_class, selected_cars)
                    show_cumulative_time_chart(filtered_df, TEAM_COLORS, selected_class, selected_cars)

        with pits_tab:
            from race_tyre_analysis import show_tyre_analysis
            show_tyre_analysis()

        with team_tab:
            from pages.team_by_team import show_team_by_team
            show_team_by_team(df_filtered, TEAM_COLORS)
