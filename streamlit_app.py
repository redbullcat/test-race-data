"""
streamlit_app.py — On The Apex race data analyser.

Directory structure: data/{SERIES}/{year}/{event}/{session_type}/{file}.csv
Session types: race, practice, qualifying, test
"""

import os
import streamlit as st

from config import DATA_DIR, TEAM_COLORS, SERIES_DISPLAY, CLASS_PRIORITY
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

def is_test_event(slug: str) -> bool:
    return any(kw in slug.lower() for kw in TEST_KEYWORDS)

def event_has_race(sessions: dict) -> bool:
    return "race" in sessions

def format_event(slug: str) -> str:
    return slug.replace("-", " ").title()

def default_class(series: str, classes: list[str]) -> str:
    """
    Return the top/leading class for a series based on what's actually
    present in the data. Checks CLASS_PRIORITY keywords in order;
    first keyword that is a substring of any class name wins.
    Falls back to the first class alphabetically.
    """
    priority = CLASS_PRIORITY.get(series, [])
    classes_lower = {c.lower(): c for c in classes}
    for kw in priority:
        for c_lower, c_orig in classes_lower.items():
            if kw in c_lower:
                return c_orig
    return sorted(classes)[0] if classes else ""

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("On The Apex")

    # ── Series ──────────────────────────────────────────────────────────────
    folder_to_display = SERIES_DISPLAY
    display_to_folder = {v: k for k, v in folder_to_display.items()}
    available_series  = sorted(race_files.keys())
    series_options    = [folder_to_display.get(s, s) for s in available_series]

    # Default to WEC
    wec_display = folder_to_display.get("WEC", "FIA WEC")
    default_series_idx = series_options.index(wec_display) if wec_display in series_options else 0

    selected_series_display = st.selectbox(
        "Series", series_options, index=default_series_idx
    )
    selected_series = display_to_folder.get(selected_series_display, selected_series_display)

    # ── Year ────────────────────────────────────────────────────────────────
    years = sorted(race_files.get(selected_series, {}).keys(), reverse=True)
    if not years:
        st.error(f"No data for {selected_series_display}.")
        st.stop()
    selected_year = st.selectbox("Year", years)  # most recent year first = index 0

    # ── All events for this year ─────────────────────────────────────────────
    all_events = race_files.get(selected_series, {}).get(selected_year, {})
    if not all_events:
        st.error(f"No events for {selected_series_display} {selected_year}.")
        st.stop()

    # Split into race weekends vs test events
    race_weekend_events = {
        slug: sessions for slug, sessions in all_events.items()
        if event_has_race(sessions) or (
            not is_test_event(slug) and
            any(s in sessions for s in ("practice", "qualifying"))
        )
    }
    test_events = {
        slug: sessions for slug, sessions in all_events.items()
        if slug not in race_weekend_events
    }

    # ── Event (race weekends only — shown here, before section selector) ────
    race_event_slugs = sorted(race_weekend_events.keys())
    # Default to last event (most recent = last alphabetically/chronologically)
    default_event_idx = len(race_event_slugs) - 1 if race_event_slugs else 0
    selected_event = st.selectbox(
        "Event",
        race_event_slugs,
        index=default_event_idx,
        format_func=format_event,
    ) if race_event_slugs else None

    # ── Section selector ────────────────────────────────────────────────────
    st.divider()
    sections = ["🏁 Race Weekend", "🔧 Tests", "📅 Season"]
    section  = st.radio("Section", sections, label_visibility="collapsed")

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

    available_test_sessions = {
        k: v for k, v in test_sessions.items()
        if k in ("test", "practice")
    }
    if not available_test_sessions:
        st.info("No session data found for this test event.")
        st.stop()

    session_type  = "test" if "test" in available_test_sessions else "practice"
    session_dir   = os.path.join(DATA_DIR, selected_series, selected_year, selected_test, session_type)
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
if not race_weekend_events or selected_event is None:
    st.info(f"No race weekend events found for {selected_series_display} {selected_year}.")
    st.stop()

event_sessions = race_weekend_events[selected_event]
event_display  = format_event(selected_event)

st.title(f"🏁 {selected_year} {selected_series_display} — {event_display}")

# ---------------------------------------------------------------------------
# Race Weekend tabs — Practice / Qualifying / Race
# ---------------------------------------------------------------------------
has_practice   = "practice"   in event_sessions
has_qualifying = "qualifying" in event_sessions
has_race       = "race"       in event_sessions

def tab_label(label: str, available: bool) -> str:
    return label if available else f"{label} (no data)"

tab_labels = [
    tab_label("Practice",   has_practice),
    tab_label("Qualifying", has_qualifying),
    tab_label("Race",       has_race),
]

practice_tab, qualifying_tab, race_tab = st.tabs(tab_labels)

# ---------------------------------------------------------------------------
# Practice tab
# ---------------------------------------------------------------------------
with practice_tab:
    if not has_practice:
        st.info("No practice data available for this event.")
    else:
        session_dir   = os.path.join(DATA_DIR, selected_series, selected_year, selected_event, "practice")
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
        session_dir   = os.path.join(DATA_DIR, selected_series, selected_year, selected_event, "qualifying")
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
        session_dir   = os.path.join(DATA_DIR, selected_series, selected_year, selected_event, "race")
        session_files = event_sessions["race"]
        file_path     = os.path.join(session_dir, session_files[0])

        df             = load_race(file_path, selected_year, selected_series)
        race_start_date = parse_race_start_date(session_files[0])

        if race_start_date is None:
            st.warning(
                "Race start date not in filename — gap evolution unavailable. "
                "Run `add_dates_to_race_files.py` to fix."
            )

        # ── Class filter — defaults to top class for this series ────────────
        classes = sorted(df["CLASS"].dropna().unique())
        if len(classes) > 1:
            top_class = default_class(selected_series, list(classes))
            class_options   = ["All classes"] + classes
            default_class_idx = class_options.index(top_class) if top_class in class_options else 0
            selected_class_filter = st.selectbox(
                "Class",
                class_options,
                index=default_class_idx,
                key="race_class_filter",
            )
            df_filtered = (
                df[df["CLASS"] == selected_class_filter].copy()
                if selected_class_filter != "All classes"
                else df
            )
        else:
            df_filtered           = df
            selected_class_filter = classes[0] if classes else "All"

        # ── Race sub-tabs ───────────────────────────────────────────────────
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
