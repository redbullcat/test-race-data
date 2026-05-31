"""stint_pace_chart.py — Average of top 20% fastest laps per stint."""

import plotly.express as px
import streamlit as st

from utils import get_team_color, apply_dark_layout


@st.cache_data(show_spinner=False)
def _compute_stints(df, team_colors_tuple, cls):
    """
    Compute per-stint averages. team_colors_tuple is a tuple-of-tuples for hashability.
    """
    team_colors = dict(team_colors_tuple)
    stint_data = []

    for car, car_df in df.groupby("NUMBER"):
        car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)
        pit_col = "CROSSING_FINISH_LINE_IN_PIT"
        pit_idx = car_df.index[car_df[pit_col] == "B"].tolist() if pit_col in car_df.columns else []

        stint_starts = [0] + [p + 2 for p in pit_idx if p + 2 < len(car_df)]
        stint_ends = pit_idx + [len(car_df)]

        for stint_num, (s, e) in enumerate(zip(stint_starts, stint_ends), start=1):
            stint_df = car_df.iloc[s:e].dropna(subset=["LAP_TIME_SECONDS"])
            if len(stint_df) < 3:
                continue

            top_n = max(1, int(0.2 * len(stint_df)))
            avg = stint_df.nsmallest(top_n, "LAP_TIME_SECONDS")["LAP_TIME_SECONDS"].mean()
            team = stint_df["TEAM"].iloc[0]

            stint_data.append({
                "NUMBER": car,
                "TEAM": team,
                "CLASS": cls,
                "Stint Avg (Top 20%)": avg,
                "Stint Length (laps)": len(stint_df),
                "Stint Start Time": stint_df["ELAPSED"].iloc[0] if "ELAPSED" in stint_df.columns else "",
                "Stint Number": stint_num,
                "Color": get_team_color(team, team_colors),
            })

    import pandas as pd
    return pd.DataFrame(stint_data).assign(_num_sort=lambda d: pd.to_numeric(d["NUMBER"], errors="coerce")).sort_values(["Stint Number", "_num_sort"]).drop(columns=["_num_sort"])


def show_stint_pace_chart(df, team_colors):
    if df.empty:
        return

    classes = df["CLASS"].dropna().unique().tolist()
    st.subheader("Stint Pace (Top 20% Fastest Laps per Stint)")
    tabs = st.tabs(classes)

    for cls, tab in zip(classes, tabs):
        with tab:
            class_df = df[df["CLASS"] == cls]
            available_cars = sort_cars(class_df["NUMBER"].unique())
            selected_cars = st.multiselect(
                f"Select cars — {cls}:", available_cars, key=f"stint_cars_{cls}"
            )
            if not selected_cars:
                st.info("Select one or more cars to see the chart.")
                continue

            filtered = class_df[class_df["NUMBER"].isin(selected_cars)].copy()
            colors_tuple = tuple(team_colors.items())
            stint_df = _compute_stints(filtered, colors_tuple, cls)

            if stint_df.empty:
                st.info("No stint data for selected cars.")
                continue

            color_map = {team: color for team, color in zip(stint_df["TEAM"], stint_df["Color"])}

            fig = px.bar(
                stint_df,
                x="Stint Number",
                y="Stint Avg (Top 20%)",
                color="TEAM",
                text="Stint Length (laps)",
                color_discrete_map=color_map,
                barmode="group",
                title=f"Stint Pace — {cls}",
                hover_data={"NUMBER": True, "TEAM": True, "Stint Start Time": True,
                             "Stint Length (laps)": True, "Stint Avg (Top 20%)": ":.3f"},
            )
            y_min = stint_df["Stint Avg (Top 20%)"].min() - 0.5
            y_max = stint_df["Stint Avg (Top 20%)"].max() + 0.5
            fig.update_layout(yaxis=dict(range=[y_min, y_max]), xaxis=dict(dtick=1))
            apply_dark_layout(fig, title_font=dict(size=22))
            st.plotly_chart(fig, width='stretch')
