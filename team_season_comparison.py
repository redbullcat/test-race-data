"""team_season_comparison.py — Team season pace comparison across all races."""

import plotly.graph_objects as go
import streamlit as st

from data_loader import load_season_races
from utils import get_team_color, apply_dark_layout, chart_export_buttons


def show_team_season_comparison(df, team_colors, year: str, series: str):
    """
    Parameters
    ----------
    df      : the currently-selected race df (used only to seed the class list)
    year    : from the sidebar
    series  : from the sidebar (folder name, e.g. 'WEC' or 'IMSA')
    """
    st.subheader("Team Season Comparison")

    race_dfs = load_season_races(year, series)
    if not race_dfs:
        st.error(f"No race data found for {year} {series}.")
        return

    # Collect classes and teams across all races
    import pandas as pd
    all_data = pd.concat(race_dfs.values(), ignore_index=True)

    classes = sorted(all_data["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select class:", classes, key="season_class")

    class_data = all_data[all_data["CLASS"] == selected_class]
    teams = sorted(class_data["TEAM"].dropna().unique())
    selected_team = st.selectbox("Select team:", teams, key="season_team")

    pace_percents = [20, 40, 60, 80, 100]
    st.markdown("**Select pace percentages to display:**")
    cols = st.columns(len(pace_percents))
    pace_selected = [
        p for i, p in enumerate(pace_percents)
        if cols[i].checkbox(f"Top {p}%", value=True, key=f"season_pct_{p}")
    ]
    if not pace_selected:
        st.warning("Select at least one pace percentage.")
        return

    pattern_shapes = {20: "", 40: "/", 60: "x", 80: ".", 100: "+"}
    color = get_team_color(selected_team, team_colors)

    summary_records = []

    for race_name, race_df in sorted(race_dfs.items()):
        team_df = race_df[
            (race_df["TEAM"] == selected_team) & (race_df["CLASS"] == selected_class)
        ].dropna(subset=["LAP_TIME_SECONDS"])

        if team_df.empty:
            continue

        st.markdown(f"### {race_name}")
        fig = go.Figure()

        for pct in pace_selected:
            n_keep = max(1, int(len(team_df) * pct / 100))
            filtered = (
                team_df.sort_values("LAP_TIME_SECONDS")
                .groupby("DRIVER_NAME")
                .head(n_keep)
            )
            driver_avgs = (
                filtered.groupby("DRIVER_NAME")["LAP_TIME_SECONDS"]
                .mean()
                .reset_index()
                .sort_values("LAP_TIME_SECONDS")
            )
            if driver_avgs.empty:
                continue

            fig.add_trace(go.Bar(
                x=driver_avgs["DRIVER_NAME"],
                y=driver_avgs["LAP_TIME_SECONDS"],
                name=f"Top {pct}%",
                marker=dict(color=color, pattern=dict(shape=pattern_shapes.get(pct, ""))),
                text=driver_avgs["LAP_TIME_SECONDS"].round(3).astype(str),
                textposition="outside",
                textangle=90,
            ))

            for _, row in driver_avgs.iterrows():
                summary_records.append({
                    "Driver": row["DRIVER_NAME"],
                    "Race": race_name,
                    "AverageLapTime": row["LAP_TIME_SECONDS"],
                    "PacePercent": pct,
                })

        all_y = [v for trace in fig.data for v in trace.y if v is not None]
        if all_y:
            fig.update_layout(
                barmode="group",
                yaxis=dict(
                    autorange=False,
                    range=[max(0, min(all_y) - 1), max(all_y) + 1],
                    title="Avg Lap Time (s)"
                ),
                title=f"{selected_team} — {race_name}",
            )
            apply_dark_layout(fig)
            st.plotly_chart(fig, width='stretch')
            chart_export_buttons(fig=fig, filename="team_season_comparison", height=500)

    # Season summary
    if not summary_records:
        st.info("No data for season summary.")
        return

    import pandas as pd
    summary_df = pd.DataFrame(summary_records)
    season_avg = (
        summary_df.groupby(["Driver", "PacePercent"])["AverageLapTime"]
        .mean()
        .reset_index()
    )

    st.markdown(f"### Season Average — {selected_team}")
    fig = go.Figure()
    for pct in pace_selected:
        df_pct = season_avg[season_avg["PacePercent"] == pct]
        if df_pct.empty:
            continue
        fig.add_trace(go.Bar(
            x=df_pct["Driver"],
            y=df_pct["AverageLapTime"],
            name=f"Top {pct}%",
            marker=dict(color=color, pattern=dict(shape=pattern_shapes.get(pct, ""))),
            text=df_pct["AverageLapTime"].round(3).astype(str),
            textposition="outside",
            textangle=90,
        ))

    all_y = season_avg["AverageLapTime"].tolist()
    if all_y:
        fig.update_layout(
            barmode="group",
            yaxis=dict(
                autorange=False,
                range=[max(0, min(all_y) - 1), max(all_y) + 1],
                title="Avg Lap Time (s)",
            ),
            xaxis_title="Driver",
            title=f"{selected_team} — Season Average",
            legend_title="Pace %",
        )
        apply_dark_layout(fig)
        st.plotly_chart(fig, width='stretch')
        chart_export_buttons(fig=fig, filename='team_season_avg_pace', height=500)
