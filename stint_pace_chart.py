import pandas as pd
import plotly.express as px
import streamlit as st

def show_stint_pace_chart(df, team_colors):
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    if df.empty:
        st.warning("No data available.")
        return

    classes = df['CLASS'].dropna().unique().tolist()
    if not classes:
        st.warning("No classes found in data.")
        return

    st.header("Average of Top 20% Fastest Laps per Stint")

    tabs = st.tabs(classes)

    for cls, tab in zip(classes, tabs):
        with tab:
            class_df = df[df['CLASS'] == cls]

            # Internal filters for cars (empty means no filter - empty UI)
            selected_cars = st.multiselect(
                f"Select Cars for {cls}",
                options=sorted(class_df["NUMBER"].unique()),
                key=f"cars_stint_{cls}"
            )
            if not selected_cars:
                st.info("Select one or more cars to see the chart.")
                continue

            filtered_df = class_df[class_df["NUMBER"].isin(selected_cars)].copy()

            stint_data = []

            for car, car_df in filtered_df.groupby("NUMBER"):
                car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)

                pit_indices = car_df.index[car_df["CROSSING_FINISH_LINE_IN_PIT"] == "B"].tolist()

                # Define stint start and end indices; outlaps removed by skipping lap after pitstop
                stint_starts = [0] + [p + 2 for p in pit_indices if (p + 2) < len(car_df)]
                stint_ends = pit_indices + [len(car_df)]

                for stint_num, (s, e) in enumerate(zip(stint_starts, stint_ends), start=1):
                    stint_df = car_df.iloc[s:e].copy()
                    if len(stint_df) < 3:
                        continue  # skip short stints

                    stint_df["LAP_TIME_SEC"] = stint_df["LAP_TIME"].apply(lap_to_seconds)
                    stint_df = stint_df.dropna(subset=["LAP_TIME_SEC"])

                    if stint_df.empty:
                        continue

                    top_count = max(1, int(0.2 * len(stint_df)))
                    top_laps = stint_df.nsmallest(top_count, "LAP_TIME_SEC")

                    stint_avg = top_laps["LAP_TIME_SEC"].mean()
                    stint_length = len(stint_df)
                    stint_start_time = stint_df["ELAPSED"].iloc[0]

                    team_name = stint_df["TEAM"].iloc[0]
                    color = "#888888"  # fallback color
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
                        "Stint Number": stint_num,
                        "Color": color
                    })

            if not stint_data:
                st.info("No stint data available for selected cars.")
                continue

            stint_df_final = pd.DataFrame(stint_data)

            # Sort so stint numbers appear in ascending order on x axis
            stint_df_final = stint_df_final.sort_values(["Stint Number", "NUMBER"])

            fig = px.bar(
                stint_df_final,
                x="Stint Number",
                y="Stint Avg (Top 20%)",
                color="TEAM",
                text="Stint Length (laps)",
                color_discrete_map={team: color for team, color in zip(stint_df_final["TEAM"], stint_df_final["Color"])},
                title=f"Average of Top 20% Fastest Laps per Stint ({cls})",
                labels={
                    "Stint Number": "Stint Number",
                    "Stint Avg (Top 20%)": "Average Lap Time (s)"
                },
                barmode="group",
                hover_data={
                    "NUMBER": True,
                    "TEAM": True,
                    "Stint Start Time": True,
                    "Stint Length (laps)": True,
                    "Stint Avg (Top 20%)": ':.3f',
                    "Stint Number": False  # hide duplicate x in hover
                }
            )

            fig.update_layout(
                plot_bgcolor="#2b2b2b",
                paper_bgcolor="#2b2b2b",
                font=dict(color="white", size=14),
                xaxis=dict(dtick=1),
                yaxis_title="Average Lap Time (s)",
                legend_title="Team",
                title_font=dict(size=22)
            )

            st.plotly_chart(fig, use_container_width=True)
