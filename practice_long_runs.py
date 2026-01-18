import pandas as pd
import plotly.express as px
import streamlit as st

def show_practice_long_runs(df, team_colors):
    st.subheader("Longest Run Average Lap Time by Car")

    # --- Classes filter ---
    classes = df["CLASS"].dropna().unique().tolist()
    selected_classes = st.multiselect(
        "Select Class(es):",
        options=classes,
        default=classes,
        key="practice_longrun_class_filter"
    )

    filtered_df = df[df["CLASS"].isin(selected_classes)]

    # --- Cars filter ---
    available_cars = sorted(filtered_df["NUMBER"].unique().tolist())
    selected_cars = st.multiselect(
        "Select Car(s):",
        options=available_cars,
        default=available_cars,
        key="practice_longrun_car_filter"
    )

    # --- Top lap % slider ---
    top_percent = st.slider(
        "Select Top Lap Percentage:",
        0,
        100,
        100,
        step=20,
        key="practice_longrun_top_lap_filter",
        help="Use 0% to hide all data."
    )

    if top_percent == 0:
        st.warning("You selected 0%. You won't see any data.")
        return

    # --- Filter by selected classes and cars ---
    filtered_df = filtered_df[filtered_df["NUMBER"].isin(selected_cars)].copy()

    # --- Lap time conversion function ---
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except Exception:
            return None

    filtered_df["LAP_TIME_SECONDS"] = filtered_df["LAP_TIME"].apply(lap_to_seconds)
    filtered_df = filtered_df.dropna(subset=["LAP_TIME_SECONDS"])

    # --- Function to find longest no-pit run for a car ---
    def longest_no_pit_run_laps(car_df):
        car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)

        # Identify pit laps: 'B' in CROSSING_FINISH_LINE_IN_PIT means pit lap
        pit_indices = car_df.index[car_df["CROSSING_FINISH_LINE_IN_PIT"] == "B"].tolist()

        # Runs are sequences between pit laps, excluding pit lap and the following lap (out lap)
        excluded_indices = set()
        for idx in pit_indices:
            excluded_indices.add(idx)  # Pit lap
            if idx + 1 < len(car_df):
                excluded_indices.add(idx + 1)  # Out lap

        # Build runs by splitting laps excluding excluded_indices
        runs = []
        current_run = []
        for i in range(len(car_df)):
            if i in excluded_indices:
                # End current run if exists
                if current_run:
                    runs.append(current_run)
                    current_run = []
            else:
                current_run.append(i)
        # Add last run
        if current_run:
            runs.append(current_run)

        if not runs:
            return pd.DataFrame()  # No valid runs

        # Find longest run (max laps)
        longest_run_indices = max(runs, key=len)

        # Return subset of car_df for longest run laps
        return car_df.loc[longest_run_indices]

    # --- Find longest runs for each car ---
    longest_runs = []
    for car_number, group in filtered_df.groupby("NUMBER"):
        longest_run_df = longest_no_pit_run_laps(group)
        if not longest_run_df.empty:
            # Filter top X% laps in longest run by lap time
            n_laps = len(longest_run_df)
            n_keep = max(1, int(n_laps * top_percent / 100))
            longest_run_df_sorted = longest_run_df.sort_values("LAP_TIME_SECONDS")
            top_laps_df = longest_run_df_sorted.head(n_keep)
            # Average lap time over these laps
            avg_lap_time = top_laps_df["LAP_TIME_SECONDS"].mean()
            team = top_laps_df["TEAM"].iloc[0] if "TEAM" in top_laps_df.columns else "Unknown"
            car_class = top_laps_df["CLASS"].iloc[0] if "CLASS" in top_laps_df.columns else "Unknown"

            longest_runs.append({
                "NUMBER": car_number,
                "TEAM": team,
                "CLASS": car_class,
                "AVG_LAP_TIME_SECONDS": avg_lap_time
            })

    if not longest_runs:
        st.warning("No longest runs found for selected filters.")
        return

    avg_df = pd.DataFrame(longest_runs).sort_values("AVG_LAP_TIME_SECONDS")

    # --- Map team colors ---
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"

    avg_df["color"] = avg_df["TEAM"].apply(get_team_color)
    avg_df["Label"] = avg_df["NUMBER"].astype(str) + " — " + avg_df["TEAM"]

    # --- Plotly bar chart ---
    fig = px.bar(
        avg_df,
        y="Label",
        x="AVG_LAP_TIME_SECONDS",
        color="TEAM",
        orientation="h",
        color_discrete_map={team: col for team, col in zip(avg_df["TEAM"], avg_df["color"])},
    )

    fig.update_yaxes(
        type='category',
        categoryorder='array',
        categoryarray=avg_df["Label"]
    )

    x_min = avg_df["AVG_LAP_TIME_SECONDS"].min() - 0.5 if not avg_df.empty else 0
    x_max = avg_df["AVG_LAP_TIME_SECONDS"].max() + 0.5 if not avg_df.empty else 1
    fig.update_xaxes(range=[x_min, x_max])

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white", size=14),
        xaxis_title="Average Lap Time (s)",
        yaxis_title="Car Number — Team",
        title="Longest Run Average Lap Time by Car",
        title_font=dict(size=22),
        showlegend=True,
    )

    st.plotly_chart(fig, use_container_width=True)
