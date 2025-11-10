import pandas as pd
import plotly.express as px
import streamlit as st

def show_stint_pace_chart(df, team_colors):
    st.header("Stint Pace Chart (Top 20% Fastest Laps per Stint)")

    # Check for required columns
    required_cols = ["LAP_NUMBER", "LAP_TIME", "CROSSING_FINISH_LINE_IN_PIT", "ELAPSED", "TEAM", "NUMBER", "CLASS"]
    for col in required_cols:
        if col not in df.columns:
            st.error(f"Missing required column: {col}")
            return

    def lap_to_seconds(x):
        try:
            parts = x.split(":")
            if len(parts) == 2:
                mins, secs = parts
                return int(mins) * 60 + float(secs)
            elif len(parts) == 3:
                hrs, mins, secs = parts
                return int(hrs) * 3600 + int(mins) * 60 + float(secs)
        except:
            return None
        return None

    classes = sorted(df["CLASS"].dropna().unique())
    tabs = st.tabs(classes)

    for i, cls in enumerate(classes):
        with tabs[i]:
            df_class = df[df["CLASS"] == cls]

            cars = sorted(df_class["NUMBER"].unique())
            selected_cars = st.multiselect(
                f"Select cars ({cls})", cars, key=f"stint_cars_{cls}"
            )

            if len(df_class["LAP_NUMBER"].dropna()) == 0:
                st.warning(f"No lap data available for class {cls}.")
                continue

            min_lap, max_lap = int(df_class["LAP_NUMBER"].min()), int(df_class["LAP_NUMBER"].max())
            lap_range = st.slider(
                f"Select lap range ({cls})",
                min_value=min_lap,
                max_value=max_lap,
                value=(min_lap, max_lap),
                key=f"stint_laps_{cls}"
            )

            if not selected_cars:
                st.info("Please select one or more cars to view stint data.")
                continue

            filtered_df = df_class[
                (df_class["NUMBER"].isin(selected_cars)) &
                (df_class["LAP_NUMBER"].between(lap_range[0], lap_range[1]))
            ].copy()

            stint_data = []

            for car, car_df in filtered_df.groupby("NUMBER"):
                car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)

                pit_indices = car_df.index[car_df["CROSSING_FINISH_LINE_IN_PIT"] == "B"].tolist()

                stint_starts = [0] + [p + 2 for p in pit_indices]
                stint_ends = pit_indices + [len(car_df)]

                for s, e in zip(stint_starts, stint_ends):
                    stint_df = car_df.iloc[s:e].copy()
                    if len(stint_df) < 3:
                        continue

                    stint_df["LAP_TIME_SEC"] = stint_df["LAP_TIME"].apply(lap_to_seconds)
                    stint_df = stint_df.dropna(subset=["LAP_TIME_SEC"])

                    if stint_df.empty:
                        continue

                    top_count = max(1, int(0.2 * len(stint_df)))
                    top_laps = stint_df.nsmallest(top_count, "LAP_TIME_SEC")

                    stint_avg = top_laps["LAP_TIME_SEC"].mean()
                    stint_length = len(stint_df)
                    stint_start_time = stint_df["ELAPSED"].iloc[0]  # race time at start of stint

                    # Map team to color robustly
                    team_name = stint_df["TEAM"].iloc[0]
                    color = "#888888"  # fallback
                    for key, val in team_colors.items():
                        if key.lower() in team_name.lower():
                            color = val
                            break

                    stint_data.append({
                        "NUMBER": car,
                        "TEAM": team_name,
                        "CLASS": cls,
                        "Stint Avg (Top 20%)": stint_avg,
                        "Stint Length (laps)": stint_length,
                        "Stint Start Time": stint_start_time,
                        "Color": color
                    })

            if not stint_data:
                st.warning("No valid stint data found for the selected range.")
                continue

            stint_df_final = pd.DataFrame(stint_data)

            # Plot bar chart with x = Stint Start Time, y = Avg lap time
            fig = px.bar(
                stint_df_final,
                x="Stint Start Time",
                y="Stint Avg (Top 20%)",
                color="TEAM",
                text="Stint Length (laps)",
                color_discrete_map={team: color for team, color in zip(stint_df_final["TEAM"], stint_df_final["Color"])},
                title=f"Average of Top 20% Fastest Laps per Stint ({cls})",
                labels={
                    "Stint Start Time": "Race Time (Elapsed)",
                    "Stint Avg (Top 20%)": "Average Lap Time (s)"
                }
            )

            fig.update_layout(
                plot_bgcolor="#2b2b2b",
                paper_bgcolor="#2b2b2b",
                font_color="white",
                xaxis=dict(showgrid=False),
                yaxis=dict(title="Avg Lap Time (s)"),
                legend_title_text="Team"
            )

            fig.update_traces(textposition="outside")

            st.plotly_chart(fig, use_container_width=True)
