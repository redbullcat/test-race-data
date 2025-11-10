import plotly.graph_objects as go
import pandas as pd
import streamlit as st
import re

def sanitize_key(s):
    return re.sub(r'\W+', '_', s)

def show_stint_pace_chart(df, team_colors):
    # Apply your own filters inside the chart; no global filters here

    available_classes = df["CLASS"].dropna().unique().tolist()
    if not available_classes:
        st.warning("No classes available.")
        return

    st.header("Stint Pace Chart")

    tabs = st.tabs(available_classes)

    for tab, cls in zip(tabs, available_classes):
        with tab:
            st.markdown(f"### {cls}")

            df_class = df[df["CLASS"] == cls]

            available_cars = sorted(df_class["NUMBER"].unique().tolist())

            selected_cars = st.multiselect(
                f"Select Cars for {cls}",
                options=available_cars,
                key=f"stint_pace_cars_{sanitize_key(cls)}"
            )

            if not selected_cars:
                st.info("Select one or more cars to see stint pace.")
                continue

            # Compute stints by finding pit stops (CROSSING_FINISH_LINE_IN_PIT == 'B')
            stints_data = []

            for car in selected_cars:
                car_df = df_class[df_class["NUMBER"] == car].sort_values("LAP_NUMBER").reset_index(drop=True)

                # Identify pit stop laps
                pit_laps = car_df[car_df["CROSSING_FINISH_LINE_IN_PIT"] == "B"]["LAP_NUMBER"].tolist()
                # Add start lap 0 and last lap+1 to simplify stint slicing
                stint_boundaries = [0] + pit_laps + [car_df["LAP_NUMBER"].max() + 1]

                for i in range(len(stint_boundaries) - 1):
                    start_lap = stint_boundaries[i] + 1  # exclude pit lap itself
                    end_lap = stint_boundaries[i + 1] - 1  # exclude out lap

                    # Select laps for this stint, exclude pit lap and out lap
                    stint_df = car_df[(car_df["LAP_NUMBER"] >= start_lap) & (car_df["LAP_NUMBER"] <= end_lap)]
                    if stint_df.empty:
                        continue

                    # Convert LAP_TIME to seconds
                    def lap_time_to_sec(x):
                        try:
                            mins, secs = x.split(":")
                            return int(mins) * 60 + float(secs)
                        except:
                            return None

                    stint_df["LAP_TIME_SEC"] = stint_df["LAP_TIME"].apply(lap_time_to_sec)
                    stint_df = stint_df.dropna(subset=["LAP_TIME_SEC"])

                    if stint_df.empty:
                        continue

                    # Calculate top 20% laps
                    n_laps = len(stint_df)
                    n_top = max(1, int(n_laps * 0.2))
                    top_laps = stint_df.nsmallest(n_top, "LAP_TIME_SEC")

                    avg_lap_time = top_laps["LAP_TIME_SEC"].mean()
                    stint_length = len(stint_df)
                    race_time = stint_df["ELAPSED"].min()  # earliest elapsed time in stint

                    stint_info = {
                        "CAR": car,
                        "STINT": i + 1,
                        "AVG_LAP_TIME": avg_lap_time,
                        "STINT_LENGTH": stint_length,
                        "RACE_TIME": race_time,
                        "TEAM": stint_df["TEAM"].iloc[0] if not stint_df["TEAM"].empty else "Unknown",
                    }
                    stints_data.append(stint_info)

            if not stints_data:
                st.info("No stint data available for selected cars.")
                continue

            stint_df = pd.DataFrame(stints_data)
            stint_df = stint_df.sort_values(["STINT", "CAR"])

            # Map colors using team_colors dict, fallback to gray
            def get_team_color(team):
                for key, color in team_colors.items():
                    if key.lower() in team.lower():
                        return color
                return "#888888"

            stint_df["COLOR"] = stint_df["TEAM"].apply(get_team_color)

            fig = go.Figure()

            max_y = 0

            for stint_num in sorted(stint_df["STINT"].unique()):
                df_stint = stint_df[stint_df["STINT"] == stint_num]

                for idx, row in df_stint.iterrows():
                    fig.add_trace(go.Bar(
                        x=[row["RACE_TIME"]],
                        y=[row["AVG_LAP_TIME"]],
                        name=f"Stint {row['STINT']} - Car {row['CAR']}",
                        marker_color=row["COLOR"],
                        width=200,  # fixed bar width (milliseconds in ELAPSED)
                        hovertemplate=(
                            f"Car: {row['CAR']}<br>"
                            f"Stint: {row['STINT']}<br>"
                            f"Avg Lap Time: {row['AVG_LAP_TIME']:.2f} s<br>"
                            f"Stint Length: {row['STINT_LENGTH']} laps<br>"
                            f"Race Time: {row['RACE_TIME']} s"
                        ),
                    ))

                    if row["AVG_LAP_TIME"] > max_y:
                        max_y = row["AVG_LAP_TIME"]

            fig.update_layout(
                barmode="group",
                title=f"Stint Pace Chart - {cls}",
                xaxis_title="Race Time (seconds elapsed)",
                yaxis_title="Average Lap Time (seconds)",
                plot_bgcolor="#2b2b2b",
                paper_bgcolor="#2b2b2b",
                font=dict(color="white"),
                yaxis=dict(range=[0, max_y * 1.1]),
                legend_title="Stint - Car",
                margin=dict(l=60, r=10, t=50, b=50),
            )

            st.plotly_chart(fig, use_container_width=True)
