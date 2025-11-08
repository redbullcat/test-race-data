import plotly.graph_objects as go
import pandas as pd
import streamlit as st

def show_lap_position_chart(df, team_colors):
    # --- Independent Class selector ---
    available_classes = sorted(df['CLASS'].dropna().unique())
    if not available_classes:
        st.warning("No classes available in data for lap position chart.")
        return

    selected_classes = st.multiselect("Select Class for Lap Position Chart", available_classes, default=available_classes)
    if not selected_classes:
        st.warning("No classes selected for lap position chart.")
        return

    st.subheader("Lap-by-Lap Position Chart")

    tabs = st.tabs(selected_classes)

    for tab, cls in zip(tabs, selected_classes):
        with tab:
            st.markdown(f"### {cls}")

            class_df = df[df['CLASS'] == cls]

            # --- Independent Car selector for this class ---
            available_cars = sorted(class_df['NUMBER'].unique())
            selected_cars = st.multiselect(f"Select Cars for {cls}", available_cars, default=available_cars, key=f"cars_{cls}")
            if not selected_cars:
                st.write(f"No cars selected for class {cls}.")
                continue

            max_lap = class_df["LAP_NUMBER"].max()
            if pd.isna(max_lap) or max_lap < 1:
                st.write(f"No lap data for class {cls}.")
                continue

            # --- Lap range slider ---
            lap_range = st.slider(
                f"Select lap range for {cls}",
                min_value=1,
                max_value=int(max_lap),
                value=(1, int(max_lap)),
                step=1,
                key=f"lap_range_{cls}"
            )

            start_lap, end_lap = lap_range

            # Prepare lap positions dict for selected range
            # Max position for any lap in range:
            max_position = class_df[class_df['LAP_NUMBER'].between(start_lap, end_lap)]\
                .groupby("LAP_NUMBER")["NUMBER"].nunique().max()

            lap_positions = {f'Lap {i}': [None] * max_position for i in range(start_lap, end_lap + 1)}

            for lap in range(start_lap, end_lap + 1):
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

            for car_number in selected_cars:
                positions = []
                laps = []
                for lap in range(start_lap, end_lap + 1):
                    col = f'Lap {lap}'
                    if car_number in position_df[col].values:
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

            st.plotly_chart(fig_lap, width='stretch')
