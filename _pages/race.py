"""_pages/race.py — Race session page: Overview | Results | Pace | Laps & Stints | Sectors | Battle."""
from __future__ import annotations

import streamlit as st


def show_race(
    df,
    df_full,
    race_start_date,
    team_colors: dict,
    selected_series: str = "",
    live_mode: bool = False,
) -> None:
    """Render the full race analysis with 6-tab layout."""
    if df is None or df.empty:
        st.warning("No data for the selected class.")
        return

    if race_start_date is None and not live_mode:
        st.warning(
            "Race start date not in filename — gap evolution and race stats unavailable. "
            "Run `add_dates_to_race_files.py` to fix."
        )

    ov_tab, res_tab, pace_tab, stints_tab, sectors_tab, battle_tab = st.tabs([
        "Overview", "Results", "Pace", "Laps & Stints", "Sectors", "Battle",
    ])

    # ── Overview ────────────────────────────────────────────────────────────────
    with ov_tab:
        from _pages.race_overview import show_race_overview
        show_race_overview(df, df_full, race_start_date, team_colors)

    # ── Results ─────────────────────────────────────────────────────────────────
    with res_tab:
        from results_table import show_results_table
        from race_stats import show_fastest_laps
        from top_speed_chart import show_top_speed_chart
        from lap_position_chart import show_lap_position_chart
        from hourly_position_chart import show_hourly_position_chart

        show_results_table(df, team_colors)
        st.divider()
        show_fastest_laps(df)
        st.divider()
        show_top_speed_chart(df, team_colors, key_prefix="res_ts", session_label="Race")
        st.divider()
        show_lap_position_chart(df, team_colors)
        st.divider()
        show_hourly_position_chart(df_full, team_colors)

    # ── Pace ────────────────────────────────────────────────────────────────────
    with pace_tab:
        from race_pace_distribution import show_race_pace_distribution
        from pace_chart import show_pace_chart
        from pace_consistency_chart import show_pace_consistency_chart
        from driver_pace_chart import show_driver_pace_chart
        from driver_pace_comparison_chart import show_driver_pace_comparison
        from stint_pace_chart import show_stint_pace_chart

        show_race_pace_distribution(df, team_colors, key_prefix="race_rpd")
        st.divider()
        show_pace_chart(df, team_colors)
        st.divider()
        show_pace_consistency_chart(df, team_colors)
        st.divider()
        show_driver_pace_chart(df, team_colors)
        st.divider()
        show_driver_pace_comparison(df, team_colors)
        st.divider()
        show_stint_pace_chart(df, team_colors)

    # ── Laps & Stints ───────────────────────────────────────────────────────────
    with stints_tab:
        from strategy_chart import show_strategy_chart
        from tyre_deg_chart import show_tyre_deg_chart
        from pit_delta_chart import show_pit_delta_chart
        from driver_stint_chart import show_driver_stint_chart
        from _pages.team_by_team import show_team_by_team

        show_strategy_chart(df, team_colors)
        st.divider()
        show_tyre_deg_chart(df, team_colors)
        st.divider()
        show_pit_delta_chart(df, team_colors)
        st.divider()
        show_driver_stint_chart(df, team_colors)
        st.divider()
        show_team_by_team(df, team_colors)

    # ── Sectors ─────────────────────────────────────────────────────────────────
    with sectors_tab:
        from sector_analysis import show_sector_analysis
        show_sector_analysis(df, team_colors, key_prefix="race_sec")

    # ── Battle ──────────────────────────────────────────────────────────────────
    with battle_tab:
        from race_stats import show_race_stats
        from gap_evolution_chart import get_filtered_race_data, show_gap_evolution_chart, show_cumulative_time_chart
        from story_chart import show_story
        from manufacturer_battle import show_manufacturer_battle

        if race_start_date:
            show_race_stats(df, race_start_date, series=selected_series, df_full=df_full)
        else:
            st.info("Lead changes and laps led require a race start date in the filename.")

        st.divider()
        st.subheader("Gap Evolution")
        if race_start_date is None and not live_mode:
            st.info("Gap evolution requires a race start date in the filename.")
        else:
            if st.button("Generate gap evolution", key="gap_trigger"):
                st.session_state["gap_active"] = True
            if st.session_state.get("gap_active"):
                filtered_df, selected_class, selected_cars, lap_range = get_filtered_race_data(
                    df, race_start_date
                )
                if filtered_df is not None:
                    show_gap_evolution_chart(filtered_df, team_colors, selected_class, selected_cars)
                    show_cumulative_time_chart(filtered_df, team_colors, selected_class, selected_cars)
            else:
                st.info("Click 'Generate gap evolution' to load the chart.")

        st.divider()
        show_story(df, team_colors, race_start_date)

        st.divider()
        show_manufacturer_battle(df, team_colors, key_prefix="race_mfr")
