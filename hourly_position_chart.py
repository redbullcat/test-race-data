"""hourly_position_chart.py — Position at each race hour elapsed.

Shows each car's position at 0 h, 1 h, 2 h … N h of elapsed race time.
Hour 0 = position after lap 1 (earliest available snapshot).
Hour N = position at the N-hour mark (based on laps completed + elapsed time).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import get_team_color, apply_dark_layout, sort_cars, chart_export_buttons

try:
    from utils import trace_border
except ImportError:
    def trace_border(color: str, threshold: float = 0.06) -> dict:  # type: ignore[misc]
        h = color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        try:
            r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
            if 0.2126 * r + 0.7152 * g + 0.0722 * b < threshold:
                return {"line": dict(color="white", width=1.5)}
        except Exception:
            pass
        return {}


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _positions_at_hour(df: pd.DataFrame, hour: int) -> pd.DataFrame:
    """Return a ranked DataFrame at the given race-hour mark.

    Ranking: most laps completed → earliest elapsed seconds (for ties).
    """
    cutoff = hour * 3600.0
    snapshot = (
        df[df["ELAPSED_SECONDS"] <= cutoff]
        .sort_values(["LAP_NUMBER", "ELAPSED_SECONDS"], ascending=[False, True])
        .drop_duplicates(subset=["NUMBER"], keep="first")
    )
    if snapshot.empty:
        return pd.DataFrame()
    snapshot = snapshot.sort_values(
        ["LAP_NUMBER", "ELAPSED_SECONDS"], ascending=[False, True]
    ).reset_index(drop=True)
    snapshot["POSITION"] = range(1, len(snapshot) + 1)
    return snapshot[["NUMBER", "TEAM", "LAP_NUMBER", "ELAPSED_SECONDS", "POSITION"]]


def _positions_at_hour_0(df: pd.DataFrame) -> pd.DataFrame:
    """Hour 0 = starting order inferred from lap-1 crossing times."""
    lap1 = (
        df[df["LAP_NUMBER"] == 1]
        .sort_values("ELAPSED_SECONDS")
        .drop_duplicates(subset=["NUMBER"], keep="first")
        .reset_index(drop=True)
    )
    if lap1.empty:
        return pd.DataFrame()
    lap1["POSITION"] = range(1, len(lap1) + 1)
    return lap1[["NUMBER", "TEAM", "LAP_NUMBER", "ELAPSED_SECONDS", "POSITION"]]


def _build_hourly_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, list[int]]:
    """Build an (hour × car) position matrix.

    Returns:
        matrix  — DataFrame with columns = car numbers, index = hour
        hours   — list of hour integers plotted
    """
    if "ELAPSED_SECONDS" not in df.columns or "LAP_NUMBER" not in df.columns:
        return pd.DataFrame(), []

    df = df.copy()
    df["ELAPSED_SECONDS"] = pd.to_numeric(df["ELAPSED_SECONDS"], errors="coerce")
    df["LAP_NUMBER"] = pd.to_numeric(df["LAP_NUMBER"], errors="coerce")
    df = df.dropna(subset=["ELAPSED_SECONDS", "LAP_NUMBER", "NUMBER"])

    max_elapsed = df["ELAPSED_SECONDS"].max()
    max_hour = int(max_elapsed // 3600)

    rows: dict[int, dict[str, int]] = {}

    # Hour 0 — start / lap-1 order
    h0 = _positions_at_hour_0(df)
    if not h0.empty:
        rows[0] = dict(zip(h0["NUMBER"].astype(str), h0["POSITION"]))

    # Hours 1 … max_hour
    for h in range(1, max_hour + 1):
        snap = _positions_at_hour(df, h)
        if not snap.empty:
            rows[h] = dict(zip(snap["NUMBER"].astype(str), snap["POSITION"]))

    if not rows:
        return pd.DataFrame(), []

    hours = sorted(rows.keys())
    all_cars = sorted({car for r in rows.values() for car in r})
    matrix = pd.DataFrame(
        {car: [rows[h].get(car) for h in hours] for car in all_cars},
        index=hours,
    )
    return matrix, hours


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def show_hourly_position_chart(df: pd.DataFrame, team_colors: dict, df_full: pd.DataFrame | None = None) -> None:
    """Render the hourly position chart.

    df      — default DataFrame (may be class-filtered).
    df_full — all classes; used when scope == 'Overall'.
    """
    st.subheader("Position by Race Hour")

    if "ELAPSED_SECONDS" not in df.columns:
        st.info("Elapsed time data not available — hourly position chart requires ELAPSED_SECONDS.")
        return

    if df_full is None:
        df_full = df

    scope = st.radio(
        "Position scope",
        ["Within class", "Overall"],
        horizontal=True,
        key="hourly_pos_scope",
        help="'Overall' ranks every car together regardless of class — useful for single-class series like GTWC.",
    )

    if scope == "Overall":
        rank_df = df_full.copy()
        title_suffix = "Overall"
    else:
        classes = sorted(df["CLASS"].dropna().unique())
        selected_class = st.selectbox("Class", classes, key="hourly_pos_class")
        rank_df = df[df["CLASS"] == selected_class].copy()
        title_suffix = selected_class

    all_cars = sort_cars(rank_df["NUMBER"].dropna().unique())
    selected_cars = st.multiselect(
        "Cars to display",
        all_cars,
        default=all_cars,
        key="hourly_pos_cars",
    )
    if not selected_cars:
        return

    matrix, hours = _build_hourly_matrix(rank_df)
    if matrix.empty or not hours:
        st.info("Not enough data to build hourly positions.")
        return

    # Car → team colour
    car_color: dict[str, str] = {}
    for _, row in rank_df[["NUMBER", "TEAM"]].drop_duplicates().iterrows():
        car_color[str(row["NUMBER"])] = get_team_color(row["TEAM"], team_colors)

    class_df = rank_df  # used below for hover lap lookups

    # How many cars share a colour (for dash differentiation)
    from collections import defaultdict
    color_idx: dict[str, int] = defaultdict(int)
    dash_styles = ["solid", "dash", "dot", "dashdot"]

    fig = go.Figure()
    for car in sort_cars(selected_cars):
        car_str = str(car)
        if car_str not in matrix.columns:
            continue
        positions = matrix[car_str].tolist()
        color = car_color.get(car_str, "#888888")
        brd = trace_border(color)

        col_key = color
        dash = dash_styles[color_idx[col_key] % len(dash_styles)]
        color_idx[col_key] += 1

        # Build hover: show lap count at each hour
        hover_parts = []
        for h in hours:
            snap = _positions_at_hour(class_df, h) if h > 0 else _positions_at_hour_0(class_df)
            if not snap.empty:
                row = snap[snap["NUMBER"].astype(str) == car_str]
                laps = int(row["LAP_NUMBER"].iloc[0]) if not row.empty else "—"
            else:
                laps = "—"
            hover_parts.append(laps)

        fig.add_trace(go.Scatter(
            x=hours,
            y=positions,
            mode="lines+markers",
            name=f"#{car}",
            line=dict(color=color if not brd else "white", width=2, dash=dash),
            marker=dict(
                color=color,
                size=8,
                **({"line": dict(color="white", width=1)} if brd else {}),
            ),
            customdata=list(zip([car_str] * len(hours), hover_parts)),
            hovertemplate=(
                "<b>Car %{customdata[0]}</b><br>"
                "Hour %{x}<br>"
                "Position: P%{y}<br>"
                "Laps: %{customdata[1]}"
                "<extra></extra>"
            ),
            connectgaps=False,
        ))

    n_cars = rank_df["NUMBER"].nunique()
    apply_dark_layout(
        fig,
        title=f"Position at Each Race Hour — {title_suffix}",
        xaxis=dict(
            title="Race elapsed (hours)",
            tickmode="array",
            tickvals=hours,
            ticktext=[f"H{h}" if h > 0 else "Start" for h in hours],
        ),
        yaxis=dict(
            title="Position",
            autorange="reversed",
            dtick=1,
            range=[0.5, n_cars + 0.5],
        ),
        height=max(400, n_cars * 28),
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(
        fig=fig,
        filename=f"hourly_position_{title_suffix.lower().replace(' ', '_')}",
        height=max(400, n_cars * 28),
    )

    # Snapshot table — positions at each hour for quick reference
    with st.expander("Position table", expanded=False):
        display_cols = {"index": "Hour"}
        table = matrix[[str(c) for c in sort_cars(selected_cars) if str(c) in matrix.columns]].copy()
        table.index.name = "Hour"
        table.index = [f"Start" if h == 0 else f"H{h}" for h in table.index]
        st.dataframe(table, width="stretch")
        chart_export_buttons(df=table.reset_index(), filename="hourly_positions_table")
