import plotly.graph_objects as go
import pandas as pd
import streamlit as st
import re

def show_stint_pace_chart(df, team_colors):

    classes = df['CLASS'].dropna().unique()
    if len(classes) == 0:
        st.warning("No classes available in data.")
        return

    selected_classes = st.multiselect("Select Classes", options=classes)

    if not selected_classes:
        st.info("Please select at least one class to see the chart.")
        return

    tabs = st.tabs(selected_classes)

    for cls, tab in zip(selected_classes, tabs):
        with tab:
            class_df = df[df['CLASS'] == cls]

            available_cars = class_df['NUMBER'].unique()
            selected_cars = st.multiselect(f"Select Cars for {cls}", options=available_cars, key=f"cars_{cls}")

            if not selected_cars:
                st.info(f"Select cars to see stint pace chart for {cls}.")
                continue

            stint_dfs = []

            for car in selected_cars:
                car_df = class_df[class_df['NUMBER'] == car].sort_values('LAP_NUMBER')
                pit_lap_indices = car_df.index[car_df['CROSSING_FINISH_LINE_IN_PIT'] == 'B'].tolist()
                # Add start and end indices for stint splitting
                pit_lap_indices = [-1] + pit_lap_indices + [car_df.index[-1]+1]

                for i in range(len(pit_lap_indices)-1):
                    stint_start = pit_lap_indices[i] + 1
                    stint_end = pit_lap_indices[i+1] - 1
                    stint_df = car_df.loc[stint_start:stint_end]

                    if stint_df.empty:
                        continue

                    # Remove out-lap (first lap after pitstop)
                    if i > 0 and len(stint_df) > 1:
                        stint_df = stint_df.iloc[1:]

                    if stint_df.empty:
                        continue

                    # Convert LAP_TIME to seconds
                    try:
                        lap_times_sec = pd.to_timedelta(stint_df["LAP_TIME"]).dt.total_seconds()
                    except Exception:
                        # fallback if LAP_TIME not timedelta format
                        lap_times_sec = stint_df["LAP_TIME"].apply(
                            lambda x: sum(int(t) * 60 ** i for i, t in enumerate(reversed(x.split(":"))))
                        )

                    stint_df = stint_df.assign(LAP_TIME_SEC=lap_times_sec)

                    top_n = max(1, int(len(stint_df) * 0.2))
                    top_laps = stint_df.nsmallest(top_n, 'LAP_TIME_SEC')

                    avg_lap_time = top_laps['LAP_TIME_SEC'].mean()
                    stint_start_time = stint_df.iloc[0]['ELAPSED'] if 'ELAPSED' in stint_df.columns else None
                    stint_laps = len(stint_df)

                    stint_dfs.append({
                        "Car": car,
                        "Stint": i + 1,
                        "Stint Avg (Top 20%)": avg_lap_time,
                        "Stint Start Time": stint_start_time,
                        "Laps in Stint": stint_laps
                    })

            if not stint_dfs:
                st.info(f"No stint data to display for {cls}.")
                continue

            stint_df_final = pd.DataFrame(stint_dfs)

            # Sort by stint number then car number
            stint_df_final.sort_values(by=["Stint", "Car"], inplace=True)

            fig = go.Figure()

            for stint_num in stint_df_final["Stint"].unique():
                stint_subset = stint_df_final[stint_df_final["Stint"] == stint_num]

                for _, row in stint_subset.iterrows():
                    car = row["Car"]
                    avg_time = row["Stint Avg (Top 20%)"]
                    laps = row["Laps in Stint"]
                    start_time = row["Stint Start Time"]

                    color = team_colors.get(
                        df.loc[(df['NUMBER'] == car) & (df['CLASS'] == cls), 'TEAM'].iloc[0],
                        "#888888"
                    )

                    fig.add_trace(go.Bar(
                        x=[str(stint_num)],  # use stint number as categorical x to group bars side by side
                        y=[avg_time],
                        name=f"Car {car}",
                        marker_color=color,
                        text=[laps],
                        textposition="auto",
                        hovertemplate=(
                            f"Car: {car}<br>Stint: {stint_num}<br>"
                            f"Avg Lap Time (Top 20%): {avg_time:.3f}s<br>"
                            f"Laps in Stint: {laps}<extra></extra>"
                        )
                    ))

            # Calculate dynamic y-axis range with padding
            y_min = stint_df_final["Stint Avg (Top 20%)"].min() - 0.5
            y_max = stint_df_final["Stint Avg (Top 20%)"].max() + 0.5

            fig.update_layout(
                plot_bgcolor="#2b2b2b",
                paper_bgcolor="#2b2b2b",
                font=dict(color="white", size=14),
                xaxis=dict(title="Stint Number", type="category", dtick=1),
                yaxis_title="Average Lap Time (s)",
                yaxis=dict(range=[y_min, y_max]),
                legend_title="Team",
                title=f"Stint Pace Chart - {cls}",
                title_font=dict(size=22),
                barmode='group'
            )

            st.plotly_chart(fig, use_container_width=True)
