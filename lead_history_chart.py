"""lead_history_chart.py — Horizontal timeline of lead stints over race distance.

Shows which car held the lead at each lap, grouped into continuous stints and
rendered as a Gantt-style bar chart coloured by team.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import get_team_color, apply_dark_layout, chart_export_buttons, parse_hour_with_rollover

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

def _compute_leaders_elapsed(df: pd.DataFrame) -> pd.DataFrame:
    """Identify the lap leader at each lap using ELAPSED_SECONDS.

    Returns a DataFrame with columns:
        LAP_NUMBER, NUMBER, TEAM, CLASS, MANUFACTURER, DRIVER_NAME
    """
    if "ELAPSED_SECONDS" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["ELAPSED_SECONDS"] = pd.to_numeric(df["ELAPSED_SECONDS"], errors="coerce")
    df["LAP_NUMBER"] = pd.to_numeric(df["LAP_NUMBER"], errors="coerce")
    df = df.dropna(subset=["ELAPSED_SECONDS", "LAP_NUMBER", "NUMBER"])
    df = df.sort_values(["LAP_NUMBER", "ELAPSED_SECONDS"])

    rows = []
    for lap, lap_df in df.groupby("LAP_NUMBER"):
        first = lap_df.iloc[0]
        rows.append({
            "LAP_NUMBER": int(lap),
            "NUMBER": str(first["NUMBER"]),
            "TEAM": str(first.get("TEAM", "")),
            "CLASS": str(first.get("CLASS", "")),
            "MANUFACTURER": str(first.get("MANUFACTURER", first.get("TEAM", ""))),
            "DRIVER_NAME": str(first.get("DRIVER_NAME", "")),
        })
    return pd.DataFrame(rows)


def _compute_leaders_datetime(df: pd.DataFrame, race_start_date) -> pd.DataFrame:
    """Identify the lap leader using parse_hour_with_rollover (datetime-based).

    Falls back to ELAPSED_SECONDS-based ranking when race_start_date is None.
    """
    if race_start_date is None:
        return _compute_leaders_elapsed(df)

    df = df.copy()
    df["HOUR_DT"] = parse_hour_with_rollover(df, race_start_date, group_col="CAR_ID")
    df["LAP_NUMBER"] = pd.to_numeric(df["LAP_NUMBER"], errors="coerce")
    df = df.dropna(subset=["LAP_NUMBER", "HOUR_DT"])
    df = df.sort_values(["LAP_NUMBER", "HOUR_DT"])

    rows = []
    for lap, lap_df in df.groupby("LAP_NUMBER"):
        first = lap_df.iloc[0]
        rows.append({
            "LAP_NUMBER": int(lap),
            "NUMBER": str(first["NUMBER"]),
            "TEAM": str(first.get("TEAM", "")),
            "CLASS": str(first.get("CLASS", "")),
            "MANUFACTURER": str(first.get("MANUFACTURER", first.get("TEAM", ""))),
            "DRIVER_NAME": str(first.get("DRIVER_NAME", "")),
        })
    return pd.DataFrame(rows)


def _collapse_stints(leaders: pd.DataFrame) -> pd.DataFrame:
    """Collapse consecutive laps led by the same car into stints.

    Returns columns:
        NUMBER, TEAM, CLASS, MANUFACTURER, DRIVERS (comma-joined),
        START_LAP, END_LAP, LAPS_LED
    """
    if leaders.empty:
        return pd.DataFrame()

    leaders = leaders.sort_values("LAP_NUMBER").reset_index(drop=True)
    stints = []
    stint_start = 0

    for i in range(1, len(leaders)):
        if leaders.loc[i, "NUMBER"] != leaders.loc[i - 1, "NUMBER"]:
            # Close the previous stint
            stint_rows = leaders.iloc[stint_start:i]
            drivers = ", ".join(
                d for d in stint_rows["DRIVER_NAME"].unique() if d and d not in ("nan", "None")
            )
            stints.append({
                "NUMBER": leaders.loc[stint_start, "NUMBER"],
                "TEAM": leaders.loc[stint_start, "TEAM"],
                "CLASS": leaders.loc[stint_start, "CLASS"],
                "MANUFACTURER": leaders.loc[stint_start, "MANUFACTURER"],
                "DRIVERS": drivers,
                "START_LAP": int(stint_rows["LAP_NUMBER"].min()),
                "END_LAP": int(stint_rows["LAP_NUMBER"].max()),
                "LAPS_LED": len(stint_rows),
            })
            stint_start = i

    # Close final stint
    stint_rows = leaders.iloc[stint_start:]
    drivers = ", ".join(
        d for d in stint_rows["DRIVER_NAME"].unique() if d and d not in ("nan", "None")
    )
    stints.append({
        "NUMBER": leaders.loc[stint_start, "NUMBER"],
        "TEAM": leaders.loc[stint_start, "TEAM"],
        "CLASS": leaders.loc[stint_start, "CLASS"],
        "MANUFACTURER": leaders.loc[stint_start, "MANUFACTURER"],
        "DRIVERS": drivers,
        "START_LAP": int(stint_rows["LAP_NUMBER"].min()),
        "END_LAP": int(stint_rows["LAP_NUMBER"].max()),
        "LAPS_LED": len(stint_rows),
    })
    return pd.DataFrame(stints)


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def show_lead_history_chart(
    df: pd.DataFrame,
    team_colors: dict,
    race_start_date=None,
    df_full: pd.DataFrame | None = None,
) -> None:
    """Render the lead history Gantt chart."""
    st.subheader("Lead History")

    has_elapsed = "ELAPSED_SECONDS" in df.columns
    has_hour = "HOUR" in df.columns or "ELAPSED_TIME" in df.columns

    if not has_elapsed and race_start_date is None:
        st.info("Lead history requires either ELAPSED_SECONDS data or a race start date in the filename.")
        return

    if df_full is None:
        df_full = df

    scope = st.radio(
        "Lead scope",
        ["Within class", "Overall"],
        horizontal=True,
        key="lead_hist_scope",
        help="'Overall' shows the single race-wide leader regardless of class.",
    )

    if scope == "Overall":
        rank_df = df_full.copy()
        classes_to_show = ["Overall"]
    else:
        classes = sorted(df["CLASS"].dropna().unique())
        if not classes:
            st.info("No class data available.")
            return
        selected_classes = st.multiselect(
            "Classes",
            classes,
            default=classes,
            key="lead_hist_classes",
        )
        if not selected_classes:
            return
        rank_df = df.copy()
        classes_to_show = selected_classes

    # Compute leaders
    if race_start_date is not None and "CAR_ID" in rank_df.columns:
        leaders_all = _compute_leaders_datetime(rank_df, race_start_date)
    else:
        leaders_all = _compute_leaders_elapsed(rank_df)

    if leaders_all.empty:
        st.info("Not enough data to compute lead history.")
        return

    fig = go.Figure()
    y_labels: list[str] = []

    for cls in classes_to_show:
        if cls == "Overall":
            leaders = leaders_all.copy()
            y_label = "Overall"
        else:
            leaders = leaders_all[leaders_all["CLASS"] == cls].copy()
            y_label = cls

        if leaders.empty:
            continue

        y_labels.append(y_label)
        stints = _collapse_stints(leaders)
        if stints.empty:
            continue

        for _, stint in stints.iterrows():
            car = stint["NUMBER"]
            color = get_team_color(stint["TEAM"], team_colors)
            brd = trace_border(color)
            border_color = brd.get("line", {}).get("color", color)

            label = f"#{car}"
            hover = (
                f"<b>#{car} — {stint['TEAM']}</b><br>"
                f"Laps {stint['START_LAP']}–{stint['END_LAP']} "
                f"({stint['LAPS_LED']} lap{'s' if stint['LAPS_LED'] != 1 else ''})<br>"
                f"Manufacturer: {stint['MANUFACTURER']}<br>"
                f"Driver(s): {stint['DRIVERS'] or '—'}"
                "<extra></extra>"
            )

            fig.add_trace(go.Bar(
                orientation="h",
                y=[y_label],
                x=[stint["LAPS_LED"]],
                base=[stint["START_LAP"] - 1],
                name=label,
                marker=dict(
                    color=color,
                    line=dict(color=border_color, width=1),
                ),
                hovertemplate=hover,
                showlegend=False,
                text=label if stint["LAPS_LED"] >= 3 else "",
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color="white", size=11),
            ))

    if not y_labels:
        st.info("No lead data to display.")
        return

    total_laps = int(leaders_all["LAP_NUMBER"].max())

    apply_dark_layout(
        fig,
        title="Lead History by Lap",
        xaxis=dict(
            title="Lap number",
            range=[0, total_laps + 1],
            dtick=max(1, total_laps // 20),
        ),
        yaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=y_labels[::-1],
        ),
        height=max(200, len(y_labels) * 80 + 120),
        barmode="stack",
        hovermode="closest",
    )

    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(
        fig=fig,
        filename="lead_history",
        height=max(200, len(y_labels) * 80 + 120),
    )

    # Summary table
    with st.expander("Lead stints detail", expanded=False):
        display_rows = []
        for cls in classes_to_show:
            if cls == "Overall":
                leaders = leaders_all.copy()
            else:
                leaders = leaders_all[leaders_all["CLASS"] == cls].copy()
            if leaders.empty:
                continue
            stints = _collapse_stints(leaders)
            if stints.empty:
                continue
            stints["CLASS_LABEL"] = cls
            display_rows.append(stints)

        if display_rows:
            tbl = pd.concat(display_rows, ignore_index=True)
            tbl = tbl.rename(columns={
                "NUMBER": "Car",
                "TEAM": "Team",
                "CLASS_LABEL": "Class",
                "MANUFACTURER": "Manufacturer",
                "DRIVERS": "Driver(s)",
                "START_LAP": "From",
                "END_LAP": "To",
                "LAPS_LED": "Laps Led",
            })
            cols = ["Class", "Car", "Team", "Manufacturer", "Driver(s)", "From", "To", "Laps Led"]
            cols = [c for c in cols if c in tbl.columns]
            st.dataframe(tbl[cols], use_container_width=True)
            chart_export_buttons(df=tbl[cols], filename="lead_history_table")
