"""pages/overview.py — Overview page: race stats, results table, position chart, pace, gaps."""

import streamlit as st

from race_stats import show_race_stats
from results_table import show_results_table
from lap_position_chart import show_lap_position_chart
from pace_chart import show_pace_chart
from driver_pace_chart import show_driver_pace_chart
from driver_pace_comparison_chart import show_driver_pace_comparison
from gap_evolution_chart import get_filtered_race_data, show_gap_evolution_chart, show_cumulative_time_chart
from stint_pace_chart import show_stint_pace_chart
from race_tyre_analysis import show_tyre_analysis


def show_overview(df, race_start_date, team_colors):
    if df is None:
        st.error("No race data loaded.")
        return

    if race_start_date is None:
        st.warning(
            "Race start date not found in filename (expected format: `RaceName_YYYYMMDD.csv`). "
            "Gap evolution and race stats will be unavailable."
        )

    overview_tab, gap_tab, pace_tab, pits_tab = st.tabs(
        ["Overview", "Gap evolution", "Race pace", "Pit stops"]
    )

    with overview_tab:
        if race_start_date:
            show_race_stats(df, race_start_date)
        show_results_table(df, team_colors)
        show_lap_position_chart(df, team_colors)

    with pace_tab:
        show_pace_chart(df, team_colors)
        show_driver_pace_chart(df, team_colors)
        show_driver_pace_comparison(df, team_colors)

    with gap_tab:
        if race_start_date is None:
            st.info("Gap evolution requires a race start date in the filename.")
        else:
            filtered_df, selected_class, selected_cars, lap_range = get_filtered_race_data(
                df, race_start_date
            )
            if filtered_df is not None:
                show_gap_evolution_chart(filtered_df, team_colors, selected_class, selected_cars)
                show_cumulative_time_chart(filtered_df, team_colors, selected_class, selected_cars)
                show_stint_pace_chart(df, team_colors)

    with pits_tab:
        show_tyre_analysis()
