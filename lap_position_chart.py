import plotly.graph_objects as go
import pandas as pd
import streamlit as st

def show_lap_position_chart(df, selected_cars, selected_classes, team_colors):
    classes = df['CLASS'].unique()
    classes = [cls for cls in classes if cls in selected_classes]

    if not classes:
        st.warning("No classes selected for lap position chart.")
        return

    # 🔹 Add lap range slider (applies globally across all classes)
    min_lap = int(df["LAP_NUMBER"].min())
    max_lap = int(df["LAP_NUMBER"].max())
    selected_laps = st.slider(
        "Select Lap Range",
        min_value=min_lap,
        max_value=max_lap,
        value=(min_lap, max_lap),
        step=1
    )

    tabs = st.tabs(classes)

    for tab, cls in zip(tabs, classes):
        with tab:
            st.subheader(f"Lap-by-Lap Position Chart for {cls}")

            # Filter by class and lap range
            class_df = df[df['CLASS'] == cls]
            class_df = class_df[
                (class_df["LAP_NUMBER"] >= selected_laps[0]) &
                (class_df["LAP_NUMBER"] <= selected_laps[1])
            ]

            # Filter selected cars for this class
            class_cars = [car for car in selected_cars if car in class_df['NUMBER'].unique()]
            if not class_cars:
                st.write(f"No cars selected for class {cls}.")
                continue

            max_lap = class_df["LAP_NUMBER"].max()
            max_position = class_df.groupby("LAP_NUMBER")["NUMBER"].nunique().max()

            # Prepare lap positions dict: keys = lap names, values = lists of cars by position
            lap_positions = {f'Lap {i}': [None] * max_position for i in range(selected_laps[0], max_lap + 1)}

            for lap in range(selected_laps[0], max_lap + 1):
                lap_df = class_df[class_df['LAP_NUMBER'] == lap].sort_values("ELAPSED").reset_index(drop=True)
                unique_cars_in_lap = lap_df["NUMBER"].unique()
                for pos, car_number in enumerate(unique_cars_in_lap, start=1):
                    if pos - 1 < max_position:
                        lap_positions[f'Lap {lap}'][pos - 1] = car_number

            position_df = pd.DataFrame(lap_positions)
            position_df.index.name = 'Position'
            position_df.index = position_df.index + 1

            # Map colors for cars based on their team
            car_colors = {}
            for team, color in team_colors.items():
                cars_in_team = class_df[class_df["TEAM"].str.lower() == team.lower()]["NUMBER"].unique()
                for car in cars_in_team:
                    car_colors[car] = color

            # Fallback color for cars without a team color
            for car in position_df.values.flatten():
                if car and car not in car_colors:
                    car_colors[car] = "#888888"

            fig_lap = go.Figure()

            for car_number in class_cars:
                positions = []
                laps = []
                for lap in range(selected_laps[0], max_lap + 1):
                    col = f'Lap {lap}'
                    if col in position_df.columns and car_number in position_df[col].values:
                        pos = position_df.index[position_df[col] == car_number][0]
                        positions.append(pos)
                        laps.append(lap)
                    else:
                        positions.append(None)
                        laps.append(lap)

                if not any(p is not None for p in positions):
                    continue

                fig_lap.add_trace(go.Scatter(
                    x=laps,
                    y=positions,
                    mode='lines+markers',
                    name=f"Car {car_number}",
                    line_shape='hv',
                    line=dict(color=car_colors.get(car_number, '#888888'), width=2),
                    connectgaps=False,
                    hovertemplate='Lap %{x}<br>Position %{y}<br>Car %{text}',
                    text=[car_number]*len(laps),
                ))

            fig_lap.update_layout(
                title=f"Lap-by-Lap Position Chart - {cls}",
                xaxis_title="Lap Number",
                yaxis_title="Race Position",
                yaxis_autorange="reversed",
                yaxis=dict(dtick=1),
                plot_bgcolor="#2b2b2b",
                paper_bgcolor="#2b2b2b",
                font=dict(color="white"),
                legend=dict(title="Car Number", yanchor="top", y=0.99, xanchor="left", x=0.01),
                margin=dict(l=60, r=10, t=50, b=50),
                hovermode="x unified",
            )

            st.plotly_chart(fig_lap, use_container_width=True)
