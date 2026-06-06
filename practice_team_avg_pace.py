"""
practice_team_avg_pace.py

Two team-level practice pace charts:

Chart 1 — Team Combined Average Pace
  Pool all valid laps from all cars in the team, compute average lap time
  per lap-in-stint position, plot one line per team.

Chart 2 — Team Best Car Average (bar chart)
  For each team, compute each car's average pace across selected laps,
  take the fastest car as the team representative, rank teams fastest→slowest.

Both charts share:
  - Class filter
  - Lap percentage slider (filter to fastest N% of laps, same logic as
    practice_average_long_run_pace.py)
  - Minimum stint length filter (only count stints with >= N laps)
  - Team colours from config
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import apply_dark_layout, build_color_map, chart_export_buttons, get_team_color, lap_to_seconds, seconds_to_laptime


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _extract_stints(df: pd.DataFrame, min_laps: int = 3) -> list[pd.DataFrame]:
    """
    Split df (already filtered to a class) into individual stints.
    A stint ends when CROSSING_FINISH_LINE_IN_PIT == 'B'.
    Returns list of DataFrames, each being one stint, with a
    Lap_In_Stint column added.
    Only includes stints with >= min_laps laps.
    """
    stints = []
    df = df.sort_values(["NUMBER", "TEAM", "PRACTICE_SESSION", "LAP_NUMBER"])

    for (car, team, session), grp in df.groupby(
        ["NUMBER", "TEAM", "PRACTICE_SESSION"], sort=False
    ):
        grp = grp.reset_index(drop=True)
        current: list = []
        skip_next = False

        for _, row in grp.iterrows():
            if skip_next:
                skip_next = False
                continue
            in_pit = str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B"
            if in_pit:
                if len(current) >= min_laps:
                    s = pd.DataFrame(current).copy()
                    s["Lap_In_Stint"] = range(1, len(s) + 1)
                    stints.append(s)
                current = []
                skip_next = True
            else:
                current.append(row)

        if len(current) >= min_laps:
            s = pd.DataFrame(current).copy()
            s["Lap_In_Stint"] = range(1, len(s) + 1)
            stints.append(s)

    return stints


def _apply_pct_filter(
    lap_df: pd.DataFrame,
    pct: int,
    group_cols: list[str],
) -> pd.DataFrame:
    """
    For each group in group_cols, keep only the fastest pct% of laps
    by LAP_TIME_SECONDS. Returns filtered DataFrame.
    """
    if pct >= 100:
        return lap_df
    out = []
    for _, grp in lap_df.groupby(group_cols):
        n = max(1, int(len(grp) * pct / 100))
        out.append(grp.nsmallest(n, "LAP_TIME_SECONDS"))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


# ---------------------------------------------------------------------------
# Chart 1: Team Combined Average Pace (line chart)
# ---------------------------------------------------------------------------

def _chart1_team_combined(
    df_cls: pd.DataFrame,
    team_colors: dict,
    pct: int,
    min_laps: int,
    key_prefix: str,
):
    st.markdown("#### Chart 1 — Team Combined Average Pace")
    st.caption(
        "Pools laps from all cars in the team to produce one average "
        "pace line per team across lap-in-stint position."
    )

    stints = _extract_stints(df_cls, min_laps=min_laps)
    if not stints:
        st.info(f"No stints with ≥ {min_laps} laps found.")
        return

    all_laps = pd.concat(stints, ignore_index=True)
    all_laps["LAP_TIME_SECONDS"] = pd.to_numeric(
        all_laps["LAP_TIME_SECONDS"], errors="coerce"
    )
    all_laps = all_laps.dropna(subset=["LAP_TIME_SECONDS", "TEAM"])

    # Apply pct filter per team
    all_laps = _apply_pct_filter(all_laps, pct, ["TEAM"])
    if all_laps.empty:
        st.info("No data after percentage filter.")
        return

    # Average by team + lap-in-stint
    grouped = (
        all_laps.groupby(["TEAM", "Lap_In_Stint"])["LAP_TIME_SECONDS"]
        .mean()
        .reset_index()
    )

    teams = sorted(grouped["TEAM"].unique())
    if not teams:
        st.info("No team data available.")
        return

    fig = go.Figure()
    for team in teams:
        team_data = grouped[grouped["TEAM"] == team].sort_values("Lap_In_Stint")
        color = get_team_color(team, team_colors)
        fig.add_trace(go.Scatter(
            x=team_data["Lap_In_Stint"],
            y=team_data["LAP_TIME_SECONDS"],
            mode="lines+markers",
            name=team,
            line=dict(color=color, width=2),
            marker=dict(size=5),
            hovertemplate=(
                f"<b>{team}</b><br>"
                "Lap in stint: %{x}<br>"
                "Avg pace: %{customdata}<extra></extra>"
            ),
            customdata=[
                seconds_to_laptime(v)
                for v in team_data["LAP_TIME_SECONDS"]
            ],
        ))

    fig.update_layout(
        title="Team Combined Average Pace",
        xaxis_title="Lap in stint",
        yaxis_title="Avg lap time (s)",
        hovermode="x unified",
        height=500,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )
    apply_dark_layout(fig)

    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(
        fig=fig, filename="team_combined_avg_pace", height=500
    )

    # Summary table
    summary = (
        all_laps.groupby("TEAM")["LAP_TIME_SECONDS"]
        .mean()
        .reset_index()
        .rename(columns={"LAP_TIME_SECONDS": "Avg Lap Time (s)"})
        .sort_values("Avg Lap Time (s)")
    )
    summary["Avg Lap Time"] = summary["Avg Lap Time (s)"].apply(seconds_to_laptime)
    with st.expander("Summary table", expanded=False):
        st.dataframe(
            summary[["TEAM", "Avg Lap Time", "Avg Lap Time (s)"]]
            .rename(columns={"TEAM": "Team"})
            .style.format({"Avg Lap Time (s)": "{:.3f}"}),
            hide_index=True,
            width="stretch",
        )
        chart_export_buttons(df=summary, filename="team_combined_avg_pace_summary")


# ---------------------------------------------------------------------------
# Chart 2: Team Best Car Average (bar chart)
# ---------------------------------------------------------------------------

def _chart2_team_best_car(
    df_cls: pd.DataFrame,
    team_colors: dict,
    pct: int,
    min_laps: int,
    key_prefix: str,
):
    st.markdown("#### Chart 2 — Team Best Car Average Pace")
    st.caption(
        "For each team, computes each car's average pace, then uses the "
        "fastest car as the team representative. Ranked fastest → slowest."
    )

    stints = _extract_stints(df_cls, min_laps=min_laps)
    if not stints:
        st.info(f"No stints with ≥ {min_laps} laps found.")
        return

    all_laps = pd.concat(stints, ignore_index=True)
    all_laps["LAP_TIME_SECONDS"] = pd.to_numeric(
        all_laps["LAP_TIME_SECONDS"], errors="coerce"
    )
    all_laps = all_laps.dropna(subset=["LAP_TIME_SECONDS", "TEAM", "NUMBER"])

    # Apply pct filter per car
    all_laps = _apply_pct_filter(all_laps, pct, ["NUMBER", "TEAM"])
    if all_laps.empty:
        st.info("No data after percentage filter.")
        return

    # Average per car
    car_avg = (
        all_laps.groupby(["TEAM", "NUMBER"])["LAP_TIME_SECONDS"]
        .mean()
        .reset_index()
        .rename(columns={"LAP_TIME_SECONDS": "Car_Avg"})
    )

    # Best (fastest) car per team
    team_best = (
        car_avg.sort_values("Car_Avg")
        .groupby("TEAM", sort=False)
        .first()
        .reset_index()
        .sort_values("Car_Avg")
    )

    if team_best.empty:
        st.info("No team data available.")
        return

    colors = [get_team_color(t, team_colors) for t in team_best["TEAM"]]
    hover = [
        f"<b>{row['TEAM']}</b><br>"
        f"Best car: #{row['NUMBER']}<br>"
        f"Avg: {seconds_to_laptime(row['Car_Avg'])}"
        for _, row in team_best.iterrows()
    ]

    fig = go.Figure(go.Bar(
        x=team_best["TEAM"],
        y=team_best["Car_Avg"],
        marker_color=colors,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover,
        text=[seconds_to_laptime(v) for v in team_best["Car_Avg"]],
        textposition="outside",
    ))

    # Y-axis range: just below fastest, just above slowest
    y_min = team_best["Car_Avg"].min()
    y_max = team_best["Car_Avg"].max()
    margin = (y_max - y_min) * 0.4 if y_max > y_min else 2.0

    fig.update_layout(
        title="Team Best Car Average Pace",
        xaxis_title="Team",
        yaxis=dict(
            title="Avg lap time (s)",
            range=[y_min - margin, y_max + margin],
        ),
        height=500,
        showlegend=False,
    )
    apply_dark_layout(fig)

    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(
        fig=fig, filename="team_best_car_avg_pace", height=500
    )

    # Summary table
    with st.expander("Summary table", expanded=False):
        display = team_best[["TEAM", "NUMBER", "Car_Avg"]].copy()
        display["Avg Lap Time"] = display["Car_Avg"].apply(seconds_to_laptime)
        display = display.rename(columns={
            "TEAM": "Team", "NUMBER": "Best Car", "Car_Avg": "Avg Lap Time (s)"
        })
        st.dataframe(
            display.style.format({"Avg Lap Time (s)": "{:.3f}"}),
            hide_index=True,
            width="stretch",
        )
        chart_export_buttons(df=display, filename="team_best_car_avg_pace_summary")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def show_practice_team_avg_pace(df: pd.DataFrame, team_colors: dict, key_prefix: str = "prac"):
    """Render both team average pace charts."""

    # ── Class filter ──────────────────────────────────────────────────────
    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox(
        "Class",
        classes,
        key=f"{key_prefix}_tavg_class",
    )
    df_cls = df[df["CLASS"] == selected_class].copy()

    if df_cls.empty:
        st.info("No data for selected class.")
        return

    # ── Shared controls ───────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    pct = col1.slider(
        "Fastest % of laps to include",
        min_value=10, max_value=100, value=100, step=10,
        format="%d%%",
        key=f"{key_prefix}_tavg_pct",
        help="Filters each car/team to their fastest N% of laps before averaging.",
    )
    min_laps = col2.slider(
        "Min stint length (laps)",
        min_value=1, max_value=20, value=3, step=1,
        key=f"{key_prefix}_tavg_minlaps",
        help="Only include stints of at least this many laps.",
    )

    st.divider()

    _chart1_team_combined(df_cls, team_colors, pct, min_laps, key_prefix)
    st.divider()
    _chart2_team_best_car(df_cls, team_colors, pct, min_laps, key_prefix)
