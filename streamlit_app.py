"""
streamlit_app.py — On The Apex race data analyser.
"""

import os
import streamlit as st

from config import DATA_DIR, TEAM_COLORS, SERIES_DISPLAY, CLASS_PRIORITY
from data_loader import load_file_index, load_race, parse_race_start_date
from manifest import load_manifest, manifest_to_file_index, get_event_meta
from live_db import live_db_available, load_live_race, get_session_meta, get_live_stats, DEFAULT_DB

st.set_page_config(
    page_title="On The Apex",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# File index — use manifest if available (fast), else walk filesystem
# ---------------------------------------------------------------------------
_manifest = load_manifest(DATA_DIR)
if _manifest is not None:
    race_files = manifest_to_file_index(_manifest)
else:
    race_files = load_file_index(DATA_DIR)
    _manifest = {}

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
    """Return the top/leading class present in the data for this series."""
    priority = CLASS_PRIORITY.get(series, [])
    classes_lower = {c.lower(): c for c in classes}
    for kw in priority:
        for c_lower, c_orig in classes_lower.items():
            if kw in c_lower:
                return c_orig
    return sorted(classes)[0] if classes else ""

# ---------------------------------------------------------------------------
# URL query param state
# ---------------------------------------------------------------------------
params = st.query_params

def _get_param(key: str, default: str) -> str:
    val = params.get(key)
    return val if val else default

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("On The Apex")

    # ── Live mode ────────────────────────────────────────────────────────────
    _live_available = live_db_available(DEFAULT_DB)
    _live_mode = st.toggle(
        "🔴 Live mode",
        value=False,
        key="live_mode",
        help="Read from live database (run live_collector.py first)",
        disabled=not _live_available,
    )
    if not _live_available:
        st.caption("No live data — start live_collector.py")
    elif _live_mode:
        _stats = get_live_stats(DEFAULT_DB)
        _meta  = get_session_meta(DEFAULT_DB)
        st.caption(
            f"🟢 {_meta.get('session_name', 'Live session')} | "
            f"{_stats.get('n_laps', 0)} laps | "
            f"{_stats.get('elapsed_hours', 0):.1f}h elapsed"
        )

    # ── Series ──────────────────────────────────────────────────────────────
    folder_to_display = SERIES_DISPLAY
    display_to_folder = {v: k for k, v in folder_to_display.items()}
    available_series  = sorted(race_files.keys())
    series_options    = [folder_to_display.get(s, s) for s in available_series]

    wec_display = folder_to_display.get("WEC", "FIA WEC")
    param_series = _get_param("series", wec_display)
    default_series_idx = (
        series_options.index(param_series)
        if param_series in series_options
        else (series_options.index(wec_display) if wec_display in series_options else 0)
    )

    selected_series_display = st.selectbox(
        "Series", series_options, index=default_series_idx
    )
    selected_series = display_to_folder.get(selected_series_display, selected_series_display)

    # ── Year ────────────────────────────────────────────────────────────────
    years = sorted(race_files.get(selected_series, {}).keys(), reverse=True)
    if not years:
        st.error(f"No data for {selected_series_display}.")
        st.stop()

    param_year = _get_param("year", years[0])
    default_year_idx = years.index(param_year) if param_year in years else 0
    selected_year = st.selectbox("Year", years, index=default_year_idx)

    # ── All events for this year ─────────────────────────────────────────────
    all_events = race_files.get(selected_series, {}).get(selected_year, {})
    if not all_events:
        st.error(f"No events for {selected_series_display} {selected_year}.")
        st.stop()

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

    # ── Event dropdown (race weekends) ──────────────────────────────────────
    race_event_slugs = sorted(race_weekend_events.keys())

    if race_event_slugs:
        param_event = _get_param("event", race_event_slugs[-1])
        default_event_idx = (
            race_event_slugs.index(param_event)
            if param_event in race_event_slugs
            else len(race_event_slugs) - 1
        )

        def _event_label(slug: str) -> str:
            label = format_event(slug)
            meta = get_event_meta(_manifest, selected_series, selected_year, slug)
            if meta.get("laps"):
                label += f"  ({meta['laps']:,} laps)"
            return label

        selected_event = st.selectbox(
            "Event",
            race_event_slugs,
            index=default_event_idx,
            format_func=_event_label,
        )
    else:
        selected_event = None

    # ── Section selector ────────────────────────────────────────────────────
    st.divider()
    sections = ["🏁 Race Weekend", "🔧 Tests", "📅 Season"]
    section  = st.radio("Section", sections, label_visibility="collapsed")

# ---------------------------------------------------------------------------
# Update URL params
# ---------------------------------------------------------------------------
st.query_params.update({
    "series": selected_series_display,
    "year":   selected_year,
    "event":  selected_event or "",
})

# ---------------------------------------------------------------------------
# Live mode — dedicated page, bypasses event navigation entirely
# ---------------------------------------------------------------------------
if _live_mode and _live_available:
    from live_db import load_live_race, get_session_meta, get_live_stats

    _df_live = load_live_race(DEFAULT_DB)
    _live_meta  = get_session_meta(DEFAULT_DB)
    _live_stats = get_live_stats(DEFAULT_DB)

    # Manual session type selector
    _session_type = st.radio(
        "Session type",
        ["Practice / Test", "Qualifying", "Race"],
        horizontal=True,
        key="live_session_type",
    )

    st.title(f"🔴 Live — {_session_type}")
    _elapsed_h = _live_stats.get("elapsed_hours", 0)
    st.info(
        f"**{_live_stats.get('n_laps', 0)} laps recorded** | "
        f"Lap {_live_stats.get('max_lap', 0)} | "
        f"{_elapsed_h:.2f}h elapsed"
    )

    # Auto-refresh every 60 seconds using streamlit-autorefresh
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=60000, key="live_autorefresh")
    except ImportError:
        import time as _time
        if "live_last_refresh" not in st.session_state:
            st.session_state["live_last_refresh"] = _time.time()
        _seconds_since_refresh = _time.time() - st.session_state["live_last_refresh"]
        _refresh_in = max(0, 60 - int(_seconds_since_refresh))
        st.caption(f"⏱ Auto-refreshing in {_refresh_in}s — install streamlit-autorefresh for automatic updates")
        if _seconds_since_refresh > 60:
            st.session_state["live_last_refresh"] = _time.time()
            st.rerun()

    if _df_live is None or _df_live.empty:
        st.warning("No laps recorded yet — waiting for data…")
        st.stop()

    # Class filter
    _live_classes = sorted(_df_live["CLASS"].dropna().unique())
    if len(_live_classes) > 1:
        _live_class = st.selectbox("Class", _live_classes, key="live_class")
        _df_live = _df_live[_df_live["CLASS"] == _live_class].copy()
    elif _live_classes:
        _live_class = _live_classes[0]
        st.caption(f"Class: {_live_class}")

    # Show charts based on inferred session type
    if _session_type in ("Race", "Qualifying"):
        from lap_position_chart import show_lap_position_chart
        from pace_chart import show_pace_chart
        from story_chart import show_story

        live_tabs = st.tabs(["Position", "Pace", "Story"])

        with live_tabs[0]:
            show_lap_position_chart(_df_live, TEAM_COLORS)

        with live_tabs[1]:
            show_pace_chart(_df_live, TEAM_COLORS)

        with live_tabs[2]:
            show_story(_df_live, TEAM_COLORS, race_start_date=None)

    else:
        # Practice / Test — show practice charts
        from practice_average_long_run_pace import show_practice_average_long_run_pace
        from practice_team_avg_pace import show_practice_team_avg_pace

        _df_live["PRACTICE_SESSION"] = "Live Session"

        live_tabs = st.tabs(["Pace", "Team Pace"])

        with live_tabs[0]:
            show_practice_average_long_run_pace(_df_live, TEAM_COLORS, key_prefix="live")

        with live_tabs[1]:
            show_practice_team_avg_pace(_df_live, TEAM_COLORS, key_prefix="live")

    st.stop()

# ---------------------------------------------------------------------------
# Season section
# ---------------------------------------------------------------------------
if section == "📅 Season":
    st.title(f"📅 {selected_year} {selected_series_display} — Season")
    season_tab, track_tab = st.tabs(["Season comparison", "Track analysis"])
    with season_tab:
        from _pages.season_comparison import show_season_comparison
        show_season_comparison(None, TEAM_COLORS, selected_year, selected_series)
    with track_tab:
        from _pages.track import show_track
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
# Race data loading
# ---------------------------------------------------------------------------
has_practice   = "practice"   in event_sessions
has_qualifying = "qualifying" in event_sessions
has_race       = "race"       in event_sessions

_df_race         = None
_race_start_date = None
_classes         = []

if _live_mode and _live_available:
    with st.spinner("Loading live race data…"):
        _df_race = load_live_race(DEFAULT_DB)
    if _df_race is not None and not _df_race.empty:
        _classes = sorted(_df_race["CLASS"].dropna().unique())
        _meta  = get_session_meta(DEFAULT_DB)
        _stats = get_live_stats(DEFAULT_DB)
        st.info(
            f"🔴 **Live mode** — {_meta.get('session_name', 'Live session')} | "
            f"{_stats.get('n_laps', 0)} laps recorded | "
            f"Lap {_stats.get('max_lap', 0)} | "
            f"{_stats.get('elapsed_hours', 0):.2f}h elapsed"
        )
        import time as _time
        if "live_last_refresh" not in st.session_state:
            st.session_state["live_last_refresh"] = _time.time()
        if _time.time() - st.session_state["live_last_refresh"] > 60:
            st.session_state["live_last_refresh"] = _time.time()
            st.rerun()
    else:
        st.warning("Live database found but no laps yet — waiting for data…")
        _df_race = None

elif has_race:
    _race_session_dir = os.path.join(DATA_DIR, selected_series, selected_year, selected_event, "race")
    _race_files       = event_sessions["race"]
    _race_file_path   = os.path.join(_race_session_dir, _race_files[0])
    with st.spinner("Loading race data…"):
        _df_race = load_race(_race_file_path, selected_year, selected_series)
    _race_start_date = parse_race_start_date(_race_files[0])
    _classes = sorted(_df_race["CLASS"].dropna().unique())

# ---------------------------------------------------------------------------
# Shared class selector
# ---------------------------------------------------------------------------
_selected_class_filter = None
_df_filtered = _df_race

if _df_race is not None and len(_classes) > 1:
    top_class = default_class(selected_series, list(_classes))
    class_options     = ["All classes"] + list(_classes)
    default_class_idx = class_options.index(top_class) if top_class in class_options else 0
    _selected_class_filter = st.selectbox(
        "Class", class_options, index=default_class_idx, key="race_class_filter"
    )
    _df_filtered = (
        _df_race[_df_race["CLASS"] == _selected_class_filter].copy()
        if _selected_class_filter != "All classes"
        else _df_race
    )
elif _df_race is not None and len(_classes) == 1:
    _selected_class_filter = _classes[0]

# ---------------------------------------------------------------------------
# Race Weekend tabs
# ---------------------------------------------------------------------------
def tab_label(label: str, available: bool) -> str:
    return label if available else f"{label} (no data)"

tab_labels = [
    tab_label("Practice",   has_practice),
    tab_label("Qualifying", has_qualifying),
    tab_label("Race",       has_race),
]

practice_tab, qualifying_tab, race_tab = st.tabs(tab_labels)

# ── Practice ────────────────────────────────────────────────────────────────
with practice_tab:
    if not has_practice:
        st.info("No practice data available for this event.")
    else:
        session_dir   = os.path.join(DATA_DIR, selected_series, selected_year, selected_event, "practice")
        session_files = event_sessions["practice"]
        from _pages.practice import show_practice
        show_practice(session_dir=session_dir, session_files=session_files, team_colors=TEAM_COLORS)

# ── Qualifying ──────────────────────────────────────────────────────────────
with qualifying_tab:
    if not has_qualifying:
        st.info("No qualifying data available for this event.")
    else:
        session_dir   = os.path.join(DATA_DIR, selected_series, selected_year, selected_event, "qualifying")
        session_files = event_sessions["qualifying"]
        from _pages.qualifying import show_qualifying
        show_qualifying(session_dir=session_dir, session_files=session_files, team_colors=TEAM_COLORS)

# ── Race ────────────────────────────────────────────────────────────────────
with race_tab:
    if _live_mode and (_df_filtered is None or (_df_filtered is not None and _df_filtered.empty)):
        st.info("Live mode active — waiting for race data.")
    elif not has_race and not _live_mode:
        st.info("No race data available for this event.")
    elif _df_filtered is None or _df_filtered.empty:
        st.warning("No data for the selected class.")
    else:
        df = _df_filtered
        race_start_date = _race_start_date

        if race_start_date is None and not _live_mode:
            st.warning(
                "Race start date not in filename — gap evolution unavailable. "
                "Run `add_dates_to_race_files.py` to fix."
            )

        results_tab, pace_tab, battle_tab, story_tab, analysis_tab, team_tab = st.tabs([
            "Results", "Pace", "Battle", "Story", "Analysis", "Team by team"
        ])

        with results_tab:
            from race_stats import show_race_stats
            from results_table import show_results_table
            from lap_position_chart import show_lap_position_chart
            if race_start_date:
                show_race_stats(df, race_start_date, series=selected_series)
            show_results_table(df, TEAM_COLORS)
            show_lap_position_chart(df, TEAM_COLORS)

        with pace_tab:
            from pace_chart import show_pace_chart
            from driver_pace_chart import show_driver_pace_chart
            from driver_pace_comparison_chart import show_driver_pace_comparison
            from stint_pace_chart import show_stint_pace_chart
            from pace_consistency_chart import show_pace_consistency_chart
            show_pace_chart(df, TEAM_COLORS)
            st.divider()
            show_pace_consistency_chart(df, TEAM_COLORS)
            st.divider()
            show_driver_pace_chart(df, TEAM_COLORS)
            st.divider()
            show_driver_pace_comparison(df, TEAM_COLORS)
            st.divider()
            show_stint_pace_chart(df, TEAM_COLORS)

        with battle_tab:
            from gap_evolution_chart import get_filtered_race_data, show_gap_evolution_chart, show_cumulative_time_chart
            if race_start_date is None and not _live_mode:
                st.info("Gap evolution requires a race start date in the filename.")
            else:
                if st.button("Generate gap evolution", key="gap_trigger"):
                    st.session_state["gap_active"] = True
                if st.session_state.get("gap_active"):
                    filtered_df, selected_class, selected_cars, lap_range = get_filtered_race_data(
                        df, race_start_date
                    )
                    if filtered_df is not None:
                        show_gap_evolution_chart(filtered_df, TEAM_COLORS, selected_class, selected_cars)
                        show_cumulative_time_chart(filtered_df, TEAM_COLORS, selected_class, selected_cars)
                else:
                    st.info("Click 'Generate gap evolution' to load the chart.")

        with story_tab:
            from story_chart import show_story
            show_story(df, TEAM_COLORS, race_start_date)

        with analysis_tab:
            from tyre_deg_chart import show_tyre_deg_chart
            from pit_delta_chart import show_pit_delta_chart
            from strategy_chart import show_strategy_chart

            analysis_sections = st.tabs(["Strategy", "Tyre Degradation", "Pit Stops"])

            with analysis_sections[0]:
                show_strategy_chart(df, TEAM_COLORS)

            with analysis_sections[1]:
                show_tyre_deg_chart(df, TEAM_COLORS)

            with analysis_sections[2]:
                show_pit_delta_chart(df, TEAM_COLORS)

        with team_tab:
            from driver_stint_chart import show_driver_stint_chart
            from _pages.team_by_team import show_team_by_team
            show_driver_stint_chart(df, TEAM_COLORS)
            st.divider()
            show_team_by_team(df, TEAM_COLORS)
