import pandas as pd
import plotly.express as px
import streamlit as st

def show_stint_pace_chart(df, team_colors):
    st.header("Stint Pace Chart (Top 20% Fastest Laps per Stint)")

    # --- Check required columns ---
    if "LAP_NUMBER" not in df.columns:
        st.error("No LAP_NUMBER column found in the dataset (used for lap numbering).")
        return
    if "LAP_TIME" not in df.columns:
        st.error("No LAP_TIME column found in the dataset (used for lap duration).")
        return

    # --- Helper: convert LAP_TIME string to seconds ---
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

    # --- Create tabs per class ---
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

                # --- Find pitstop rows ---
                pit_indices = car_df.index[car_df["CROSSING_FINISH_LINE_IN_PIT"] == "B"].tolist()

                # Define stint start/end indices (skip out-lap after stop)
                stint_starts = [0] + [p + 2 for p in pit_indices]
                stint_ends = pit_indices + [len(car_df)]

                for s, e in zip(stint_starts, stint_ends):
                    stint_df = car_df.iloc[s:e].copy()
                    if len(stint_df) < 3:
                        continue  # skip very short stints

                    # Convert LAP_TIME to seconds manually
                    stint_df["LAP_TIME_SEC"] = stint_df["LAP_TIME"].apply(lap_to_seconds)
                    stint_df = stint_df.dropna(subset=["LAP_TIME_SEC"])

                    if stint_df.empty:
                        continue

                    # Get top 20% fastest laps in the stint
                    top_count = max(1, int(0.2 * len(stint_df)))
                    top_laps = stint_df.nsmallest(top_count, "LAP_TIME_SEC")

                    stint_avg = top_laps["LAP_TIME_SEC"].mean()
                    stint_length = len(stint_df)

                    stint_data.append({
                        "NUMBER": car,
                        "TEAM": stint_df["TEAM"].iloc[0] if "TEAM" in stint_df.columns else "",
                        "CLASS": cls,
                        "Stint Avg (Top 20%)": stint_avg,
                        "Stint Length (laps)": stint_length
                    })

            if not stint_data:
                st.warning("No valid stint data found for the selected range.")
                continue

            stint_df_final = pd.DataFrame(stint_data)

            # --- Plot bar chart ---
            fig = px.bar(
                stint_df_final,
                x="NUMBER",
                y="Stint Avg (Top 20%)",
                color="NUMBER",
                text="Stint Length (laps)",
                color_discrete_map=team_colors,
                title=f"Average of Top 20% Fastest Laps per Stint ({cls})"
            )

            fig.update_layout(
                plot_bgcolor="#2b2b2b",
                paper_bgcolor="#2b2b2b",
                font_color="white",
                xaxis_title="Car Number",
                yaxis_title="Avg Lap Time (s)",
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)
