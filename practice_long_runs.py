import pandas as pd
import streamlit as st
import plotly.express as px

def show_practice_long_runs(df: pd.DataFrame, team_colors: dict):
    st.subheader("Practice Long Runs")

    # --- Filters (classes, cars, top lap %) ---
    classes = df["CLASS"].dropna().unique().tolist()
    selected_classes = st.multiselect(
        "Select Class(es):",
        options=classes,
        default=classes,
        key="practice_long_runs_class_filter"
    )

    filtered_df = df[df["CLASS"].isin(selected_classes)]

    available_cars = sorted(filtered_df["NUMBER"].unique().tolist())
    selected_cars = st.multiselect(
        "Select Car(s):",
        options=available_cars,
        default=available_cars,
        key="practice_long_runs_car_filter"
    )

    top_percent = st.slider(
        "Select Top Lap Percentage:",
        0,
        100,
        100,
        step=20,
        key="practice_long_runs_top_lap_filter",
        help="Use 0% to hide all data."
    )

    if top_percent == 0:
        st.warning("You selected 0%. You won't see any data.")
        return

    # Apply filters
    df = df[df["CLASS"].isin(selected_classes) & df["NUMBER"].isin(selected_cars)]

    # Convert lap times to seconds
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except Exception:
            return None

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SECONDS"])

    # Filter top X% fastest laps per car for pace calculation only (can skip this if you want the whole stint pace)
    def filter_top_percent_laps(df, percent):
        filtered_dfs = []
        for car_number, group in df.groupby("NUMBER"):
            group_sorted = group.sort_values("LAP_TIME_SECONDS")
            n_laps = len(group_sorted)
            n_keep = max(1, int(n_laps * percent / 100))
            filtered_dfs.append(group_sorted.head(n_keep))
        return pd.concat(filtered_dfs)

    filtered_df_for_pace = filter_top_percent_laps(df, top_percent)

    # --- Find longest continuous stint for each car across all sessions ---

    long_run_records = []

    for car_number, car_group in df.groupby("NUMBER"):
        # Sort by session and lap order (assuming 'LAP' or a lap order column is present)
        # If no lap order column, sort by session + index (best guess)
        car_group = car_group.sort_values(["PRACTICE_SESSION", "LAP"] if "LAP" in car_group.columns else ["PRACTICE_SESSION", car_group.index])

        # We will iterate through laps, splitting runs on pit laps ("B") and the lap after
        runs = []
        current_run = []
        skip_next = False

        for idx, row in car_group.iterrows():
            if skip_next:
                # skip this lap (out lap after pit)
                skip_next = False
                continue

            if "CROSSING_FINISH_LINE_IN_PIT" in car_group.columns and row["CROSSING_FINISH_LINE_IN_PIT"] == "B":
                # Pit lap found, close current run if not empty
                if current_run:
                    runs.append(current_run)
                    current_run = []
                # Skip this lap and next lap (out lap)
                skip_next = True
            else:
                current_run.append(row)

        # Add final run if exists
        if current_run:
            runs.append(current_run)

        # Find longest run
        if not runs:
            continue

        longest_run = max(runs, key=len)
        longest_run_df = pd.DataFrame(longest_run)

        # Average lap time for the longest run
        avg_lap_time = longest_run_df["LAP_TIME_SECONDS"].mean()

        # Get team, manufacturer, class (assume same for all laps in run)
        team = longest_run_df.iloc[0]["TEAM"]
        manufacturer = longest_run_df.iloc[0]["MANUFACTURER"] if "MANUFACTURER" in longest_run_df.columns else ""
        race_class = longest_run_df.iloc[0]["CLASS"]

        # Get unique drivers for the run
        drivers = longest_run_df["DRIVER_NAME"].unique().tolist()
        # Join driver names separated by " / "
        driver_str = " / ".join(drivers)

        # Get lap numbers in the run (if LAP column exists)
        if "LAP" in longest_run_df.columns:
            lap_numbers = longest_run_df["LAP"].tolist()
            lap_numbers_str = ", ".join(str(x) for x in lap_numbers)
        else:
            lap_numbers_str = "N/A"

        # Get session for the longest run (take session of first lap in run)
        session = longest_run_df.iloc[0]["PRACTICE_SESSION"]

        # Number of laps in the stint
        stint_length = len(longest_run)

        long_run_records.append({
            "NUMBER": car_number,
            "TEAM": team,
            "MANUFACTURER": manufacturer,
            "CLASS": race_class,
            "DRIVER": driver_str,
            "AVG_LAP_TIME": avg_lap_time,
            "LAPS_IN_STINT": stint_length,
            "LAP_NUMBERS": lap_numbers_str,
            "SESSION": session,
        })

    if not long_run_records:
        st.warning("No long runs found for selected filters.")
        return

    long_run_df = pd.DataFrame(long_run_records)

    # Sort by class and average lap time ascending
    long_run_df = long_run_df.sort_values(["CLASS", "AVG_LAP_TIME"], ascending=[True, True])

    # Plot bar chart for avg lap times per car (same as pace chart style)
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"

    long_run_df["color"] = long_run_df["TEAM"].apply(get_team_color)
    long_run_df["Label"] = long_run_df["NUMBER"].astype(str) + " — " + long_run_df["TEAM"]

    fig = px.bar(
        long_run_df,
        y="Label",
        x="AVG_LAP_TIME",
        color="TEAM",
        orientation="h",
        color_discrete_map={team: col for team, col in zip(long_run_df["TEAM"], long_run_df["color"])},
        title="Average Lap Time of Longest Run by Car"
    )

    fig.update_yaxes(
        type='category',
        categoryorder='array',
        categoryarray=long_run_df["Label"]
    )

    x_min = long_run_df["AVG_LAP_TIME"].min() - 0.5 if not long_run_df.empty else 0
    x_max = long_run_df["AVG_LAP_TIME"].max() + 0.5 if not long_run_df.empty else 1
    fig.update_xaxes(range=[x_min, x_max])

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white", size=14),
        xaxis_title="Average Lap Time (s)",
        yaxis_title="Car Number — Team",
        title_font=dict(size=22),
        showlegend=True,
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- Show data tables by class ---
    st.markdown("---")
    st.subheader("Longest Run Details by Class")

    classes = long_run_df["CLASS"].unique()

    for race_class in sorted(classes):
        class_df = long_run_df[long_run_df["CLASS"] == race_class].copy()
        class_df = class_df.reset_index(drop=True)
        class_df.index += 1  # Start index at 1 for position

        st.markdown(f"### Class: {race_class}")
        st.dataframe(
            class_df[[
                "NUMBER",
                "TEAM",
                "MANUFACTURER",
                "DRIVER",
                "AVG_LAP_TIME",
                "LAP_NUMBERS",
                "LAPS_IN_STINT",
                "SESSION"
            ]].rename(columns={
                "NUMBER": "Car Number",
                "TEAM": "Team",
                "MANUFACTURER": "Manufacturer",
                "DRIVER": "Driver(s)",
                "AVG_LAP_TIME": "Average Lap Time (s)",
                "LAP_NUMBERS": "Laps in Stint",
                "LAPS_IN_STINT": "Stint Length (laps)",
                "SESSION": "Session"
            }),
            use_container_width=True
        )
