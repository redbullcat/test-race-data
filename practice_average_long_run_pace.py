import pandas as pd
import streamlit as st
import plotly.express as px

def show_practice_average_long_run_pace(df, team_colors):
    st.subheader("Average Long Run Pace")

    # Filters
    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select Class:", ["All"] + classes, index=0, key="avg_long_run_class")

    df_filtered = df.copy()
    if selected_class != "All":
        df_filtered = df_filtered[df_filtered["CLASS"] == selected_class]

    # Filter cars available after class filter
    cars = sorted(df_filtered["NUMBER"].dropna().unique())
    selected_car = st.selectbox("Select Car:", ["All"] + cars, index=0, key="avg_long_run_car")

    if selected_car != "All":
        df_filtered = df_filtered[df_filtered["NUMBER"] == selected_car]

    # Prepare long runs: stints with >= 8 laps
    # Group by NUMBER + TEAM + PRACTICE_SESSION + stint identification
    # We will identify stints by continuous runs without pit lap ('B') marks.

    # Sort data for reliable grouping
    df_filtered = df_filtered.sort_values(["NUMBER", "TEAM", "PRACTICE_SESSION", "LAP_NUMBER"])

    # Identify stint groups: for each car+team+session, group laps into stints separated by 'B'
    stint_groups = []
    for (car, team, session), group in df_filtered.groupby(["NUMBER", "TEAM", "PRACTICE_SESSION"]):
        group = group.reset_index(drop=True)
        stint_id = 0
        current_stint_rows = []

        skip_next = False
        for idx, row in group.iterrows():
            if skip_next:
                skip_next = False
                continue

            crossing_pit = str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B"

            if crossing_pit:
                # End current stint before pit lap
                if len(current_stint_rows) >= 8:
                    stint_groups.append(pd.DataFrame(current_stint_rows))
                current_stint_rows = []
                skip_next = True
                stint_id += 1
                continue

            current_stint_rows.append(row)

        # Append last stint if qualifies
        if len(current_stint_rows) >= 8:
            stint_groups.append(pd.DataFrame(current_stint_rows))

    if not stint_groups:
        st.warning("No long runs (8+ laps) found for the selected filters.")
        return

    # Build lap-indexed DataFrame per stint: lap position within stint, lap time
    lap_dfs = []
    for stint_df in stint_groups:
        stint_df = stint_df.reset_index(drop=True)
        stint_df = stint_df.copy()
        stint_df["Lap_in_Stint"] = stint_df.index + 1  # 1-based lap index
        lap_dfs.append(stint_df[["NUMBER", "TEAM", "MANUFACTURER", "Lap_in_Stint", "LAP_TIME"]])

    all_laps_df = pd.concat(lap_dfs, ignore_index=True)

    # Convert LAP_TIME to seconds (assuming mm:ss.sss format)
    def lap_time_to_seconds(x):
        try:
            parts = x.split(":")
            if len(parts) == 2:
                mins, secs = parts
                return int(mins) * 60 + float(secs)
            elif len(parts) == 3:
                hrs, mins, secs = parts
                return int(hrs) * 3600 + int(mins) * 60 + float(secs)
        except Exception:
            return None

    all_laps_df["Lap_Time_Seconds"] = all_laps_df["LAP_TIME"].apply(lap_time_to_seconds)
    all_laps_df = all_laps_df.dropna(subset=["Lap_Time_Seconds"])

    # Group by car (NUMBER + TEAM + MANUFACTURER) and lap_in_stint, average lap time
    avg_lap_times = (
        all_laps_df
        .groupby(["NUMBER", "TEAM", "MANUFACTURER", "Lap_in_Stint"])["Lap_Time_Seconds"]
        .mean()
        .reset_index()
    )

    # Create a helper DataFrame for filtering by lap coverage percentage per car
    # Count how many laps per car are present
    laps_per_car = avg_lap_times.groupby(["NUMBER", "TEAM"])["Lap_in_Stint"].max().reset_index()
    laps_per_car.rename(columns={"Lap_in_Stint": "Max_Laps"}, inplace=True)

    # Percentage filter slider (0% - 100% in 20% steps)
    perc_slider = st.slider(
        "Show best percentage of laps:",
        min_value=0,
        max_value=100,
        value=100,
        step=20,
        format="%d%%",
        key="avg_long_run_lap_percentage"
    )

    if perc_slider == 0:
        st.info("0% selected - no data to show.")
        return

    # Filter laps per car to best N% laps based on lap times (fastest laps)
    filtered_avg_lap_times_list = []

    for (number, team), group in avg_lap_times.groupby(["NUMBER", "TEAM"]):
        max_laps = laps_per_car[(laps_per_car["NUMBER"] == number) & (laps_per_car["TEAM"] == team)]["Max_Laps"].values[0]
        num_laps_to_keep = max(1, int(max_laps * perc_slider / 100))

        # Sort laps by average lap time ascending (fastest first)
        group_sorted = group.sort_values("Lap_Time_Seconds").reset_index(drop=True)

        # Select fastest laps only
        laps_to_keep = group_sorted.head(num_laps_to_keep)["Lap_in_Stint"].tolist()

        # Filter original group by these laps
        filtered_group = group[group["Lap_in_Stint"].isin(laps_to_keep)].copy()
        filtered_avg_lap_times_list.append(filtered_group)

    filtered_avg_lap_times = pd.concat(filtered_avg_lap_times_list, ignore_index=True)

    if filtered_avg_lap_times.empty:
        st.warning("No lap data after applying the percentage filter.")
        return

    # For plotting, we want to plot lap times vs lap index per car
    # To have continuous lap index on x-axis, order by Lap_in_Stint ascending
    # We also want to assign a color per car (use NUMBER + TEAM as key)

    # Assign a display label for hover (e.g. "Car 23 - Team X")
    filtered_avg_lap_times["Car_Team"] = filtered_avg_lap_times["NUMBER"].astype(str) + " - " + filtered_avg_lap_times["TEAM"]

    # Create line chart with plotly express
    fig = px.line(
        filtered_avg_lap_times,
        x="Lap_in_Stint",
        y="Lap_Time_Seconds",
        color="Car_Team",
        labels={
            "Lap_in_Stint": "Lap Number in Stint",
            "Lap_Time_Seconds": "Average Lap Time (s)",
            "Car_Team": "Car - Team"
        },
        title="Average Long Run Lap Times by Car",
        markers=True,
        color_discrete_map=team_colors
    )

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white"),
        legend_title_text="Car - Team"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary table with overall average lap time per car (filtered laps only)
    summary = (
        filtered_avg_lap_times
        .groupby(["NUMBER", "TEAM", "MANUFACTURER"])["Lap_Time_Seconds"]
        .mean()
        .reset_index()
        .rename(columns={"Lap_Time_Seconds": "Average Lap Time (s)"})
        .sort_values("Average Lap Time (s)")
    )

    st.markdown("### Summary Table")
    st.dataframe(summary.style.format({"Average Lap Time (s)": "{:.3f}"}))


if __name__ == "__main__":
    st.warning("This module is meant to be imported and used within the practice analysis app.")
