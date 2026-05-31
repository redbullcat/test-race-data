"""
strategy_chart.py — Stint / strategy Gantt chart.

Shows each car as a horizontal bar divided into stints, making the strategic
picture of a race immediately readable.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import apply_dark_layout, build_color_map, sort_cars


@st.cache_data(show_spinner=False)
def _build_stints(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reconstruct stints for each car from the lap data.
    Returns a DataFrame with one row per stint:
        NUMBER, TEAM, CLASS, Stint, Start Lap, End Lap, Laps, Avg Pace (s)
    """
    if "CROSSING_FINISH_LINE_IN_PIT" not in df.columns:
        return pd.DataFrame()

    df = df.dropna(subset=["LAP_NUMBER"]).copy()
    df["LAP_NUMBER"] = df["LAP_NUMBER"].astype(int)

    rows = []
    for (number, team, cls), car_df in df.groupby(["NUMBER", "TEAM", "CLASS"]):
        car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)

        stint_num = 1
        stint_start = car_df.iloc[0]["LAP_NUMBER"]
        stint_laps = []

        for _, row in car_df.iterrows():
            stint_laps.append(row["LAP_TIME_SECONDS"] if pd.notna(row.get("LAP_TIME_SECONDS")) else None)
            in_pit = str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B"
            if in_pit:
                valid_times = [t for t in stint_laps if t is not None]
                rows.append({
                    "NUMBER": number,
                    "TEAM": team,
                    "CLASS": cls,
                    "Stint": stint_num,
                    "Start Lap": int(stint_start),
                    "End Lap": int(row["LAP_NUMBER"]),
                    "Laps": len(stint_laps),
                    "Avg Pace (s)": round(sum(valid_times) / len(valid_times), 3) if valid_times else None,
                })
                stint_num += 1
                stint_start = row["LAP_NUMBER"] + 1
                stint_laps = []

        # Final stint (no pit at end)
        if stint_laps:
            valid_times = [t for t in stint_laps if t is not None]
            last_lap = car_df.iloc[-1]["LAP_NUMBER"]
            rows.append({
                "NUMBER": number,
                "TEAM": team,
                "CLASS": cls,
                "Stint": stint_num,
                "Start Lap": int(stint_start),
                "End Lap": int(last_lap),
                "Laps": len(stint_laps),
                "Avg Pace (s)": round(sum(valid_times) / len(valid_times), 3) if valid_times else None,
            })

    return pd.DataFrame(rows)


def show_strategy_chart(df: pd.DataFrame, team_colors: dict) -> None:
    st.subheader("Race Strategy")
    st.caption("Each bar represents a stint. Gaps between bars are pit stops.")

    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Class:", classes, key="strategy_class")

    class_df = df[df["CLASS"] == selected_class].copy()
    stints = _build_stints(class_df)

    if stints.empty:
        st.info("No stint data available. This requires CROSSING_FINISH_LINE_IN_PIT data in the CSV.")
        return

    stints = stints[stints["CLASS"] == selected_class]

    # Order cars by total laps (= finishing order)
    car_order = (
        stints.groupby("NUMBER")["End Lap"].max()
        .sort_values(ascending=False)
        .index.tolist()
    )
    car_order = sort_cars(car_order)  # stable within same-lap ties

    color_map = build_color_map(stints, team_colors)

    # Colour stints alternately light/dark per car to distinguish them
    fig = go.Figure()

    # Use a pastel variant for alternate stints
    def _lighten(hex_color: str, factor: float = 0.5) -> str:
        try:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            r2 = int(r + (255 - r) * factor)
            g2 = int(g + (255 - g) * factor)
            b2 = int(b + (255 - b) * factor)
            return f"rgb({r2},{g2},{b2})"
        except Exception:
            return hex_color

    for car in car_order:
        car_stints = stints[stints["NUMBER"] == car].sort_values("Stint")
        if car_stints.empty:
            continue
        team = car_stints["TEAM"].iloc[0]
        base_color = color_map.get(team, "#888888")
        label = f"{car} — {team}"

        for _, stint_row in car_stints.iterrows():
            color = base_color if stint_row["Stint"] % 2 == 1 else _lighten(base_color, 0.35)
            fig.add_trace(go.Bar(
                y=[label],
                x=[stint_row["Laps"]],
                base=stint_row["Start Lap"] - 1,
                orientation="h",
                marker_color=color,
                marker_line=dict(color="#222", width=1),
                name=f"Car {car} Stint {int(stint_row['Stint'])}",
                showlegend=False,
                customdata=[[
                    int(stint_row["Stint"]),
                    int(stint_row["Start Lap"]),
                    int(stint_row["End Lap"]),
                    int(stint_row["Laps"]),
                    stint_row["Avg Pace (s)"] or "N/A",
                ]],
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "Stint %{customdata[0]}<br>"
                    "Laps %{customdata[1]}–%{customdata[2]} "
                    "(%{customdata[3]} laps)<br>"
                    "Avg pace: %{customdata[4]}s"
                    "<extra></extra>"
                ),
            ))

    fig.update_layout(
        title=f"Stint Strategy — {selected_class}",
        barmode="overlay",
        xaxis_title="Lap",
        yaxis=dict(
            categoryorder="array",
            categoryarray=[f"{c} — {stints[stints['NUMBER']==c]['TEAM'].iloc[0]}" for c in car_order if not stints[stints['NUMBER']==c].empty],
        ),
        height=max(400, len(car_order) * 35),
    )
    apply_dark_layout(fig, title_font=dict(size=22))
    st.plotly_chart(fig, width="stretch")

    # Pit count summary
    pit_counts = (
        stints.groupby(["NUMBER", "TEAM"])["Stint"]
        .max()
        .reset_index()
        .rename(columns={"Stint": "Pit Stops"})
    )
    pit_counts["Pit Stops"] = pit_counts["Pit Stops"] - 1  # stints - 1 = stops
    pit_counts["Label"] = pit_counts["NUMBER"] + " — " + pit_counts["TEAM"]
    pit_counts = pit_counts.sort_values("Pit Stops", ascending=False)

    with st.expander("Pit stop count summary", expanded=False):
        st.dataframe(
            pit_counts[["Label", "Pit Stops"]].rename(columns={"Label": "Car"}),
            hide_index=True, width="stretch"
        )
