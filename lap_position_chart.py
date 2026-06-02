"""lap_position_chart.py — Lap-by-lap position chart."""

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from utils import get_team_color, apply_dark_layout, sort_cars, chart_export_buttons


def show_lap_position_chart(df, team_colors):
    classes = sorted(df["CLASS"].dropna().unique())
    selected_classes = st.multiselect(
        "Select class(es) for position chart:", classes, default=classes, key="pos_class"
    )
    if not selected_classes:
        st.warning("No classes selected.")
        return

    st.subheader("Lap-by-Lap Position Chart")
    tabs = st.tabs(selected_classes)

    for tab, cls in zip(tabs, selected_classes):
        with tab:
            class_df = df[df["CLASS"] == cls]
            available_cars = sort_cars(class_df["NUMBER"].unique())
            selected_cars = st.multiselect(
                f"Cars in {cls}:", available_cars, default=available_cars, key=f"pos_cars_{cls}"
            )
            if not selected_cars:
                st.info("No cars selected.")
                continue

            max_lap = class_df["LAP_NUMBER"].max()
            if pd.isna(max_lap) or max_lap < 1:
                st.info("No lap data available.")
                continue

            lap_range = st.slider(
                f"Lap range — {cls}:", 1, int(max_lap), (1, int(max_lap)), key=f"pos_laps_{cls}"
            )
            start_lap, end_lap = lap_range

            # Build position matrix
            laps_in_range = range(start_lap, end_lap + 1)
            n_cars = class_df["NUMBER"].nunique()
            lap_positions: dict[str, list] = {
                f"Lap {i}": [None] * n_cars for i in laps_in_range
            }

            for lap in laps_in_range:
                lap_df = (
                    class_df[class_df["LAP_NUMBER"] == lap]
                    .sort_values("ELAPSED")
                    .reset_index(drop=True)
                )
                for pos, car in enumerate(lap_df["NUMBER"].unique(), start=1):
                    if pos - 1 < n_cars:
                        lap_positions[f"Lap {lap}"][pos - 1] = car

            position_df = pd.DataFrame(lap_positions)
            position_df.index = range(1, len(position_df) + 1)

            # Colour map: car number → team colour
            car_colors: dict[str, str] = {}
            for _, row in class_df[["NUMBER", "TEAM"]].drop_duplicates().iterrows():
                car_colors[row["NUMBER"]] = get_team_color(row["TEAM"], team_colors)

            # Assign dash style: cars sharing a colour get solid / dash / dot
            # in ascending numeric order so the assignment is deterministic.
            DASH_STYLES   = ["solid", "dash",   "dot"]
            MARKER_SHAPES = ["circle", "square", "diamond"]
            color_to_cars: dict[str, list] = {}
            for car in sort_cars(selected_cars):
                col = car_colors.get(car, "#888888")
                color_to_cars.setdefault(col, []).append(car)
            car_style: dict[str, tuple] = {}  # car → (dash, marker_symbol)
            for col, cars_same_color in color_to_cars.items():
                for i, car in enumerate(cars_same_color):
                    idx = min(i, len(DASH_STYLES) - 1)
                    car_style[car] = (DASH_STYLES[idx], MARKER_SHAPES[idx])

            fig = go.Figure()
            for car in selected_cars:
                positions, laps = [], []
                for lap in laps_in_range:
                    col = f"Lap {lap}"
                    if car in position_df[col].values:
                        pos = position_df.index[position_df[col] == car][0]
                    else:
                        pos = None
                    positions.append(pos)
                    laps.append(lap)

                if not any(p is not None for p in positions):
                    continue

                dash, marker_symbol = car_style.get(car, ("solid", "circle"))
                fig.add_trace(go.Scatter(
                    x=laps,
                    y=positions,
                    mode="lines+markers",
                    name=f"Car {car}",
                    line_shape="hv",
                    line=dict(
                        color=car_colors.get(car, "#888888"),
                        width=2,
                        dash=dash,
                    ),
                    marker=dict(symbol=marker_symbol),
                    connectgaps=False,
                    hovertemplate="Lap %{x}<br>P%{y}<br>Car " + str(car),
                ))

            fig.update_layout(
                title=f"Lap-by-Lap Position – {cls}",
                xaxis_title="Lap",
                yaxis_title="Position",
                yaxis_autorange="reversed",
                yaxis=dict(dtick=1),
                legend=dict(title="Car", yanchor="top", y=0.99, xanchor="left", x=0.01),
                hovermode="x unified",
            )
            apply_dark_layout(fig)
            st.plotly_chart(fig, width='stretch')
            chart_export_buttons(fig=fig, filename="lap_position_chart", height=500)
