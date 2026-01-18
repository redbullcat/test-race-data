import pandas as pd
import streamlit as st
import plotly.express as px

def show_practice_long_runs(df: pd.DataFrame, team_colors: dict):
    st.subheader("Longest Practice Runs by Car")

    # --- Classes filter ---
    classes = df["CLASS"].dropna().unique().tolist()
    selected_classes = st.multiselect(
        "Select Class(es):",
        options=classes,
        default=classes,
        key="practice_long_runs_class_filter"
    )

    filtered_df = df[df["CLASS"].isin(selected_classes)]

    # --- Cars filter ---
    available_cars = sorted(filtered_df["NUMBER"].unique().tolist())
    selected_cars = st.multiselect(
        "Select Car(s):",
        options=available_cars,
        default=available_cars,
        key="practice_long_runs_car_filter"
    )

    filtered_df = filtered_df[filtered_df["NUMBER"].isin(selected_cars)]

    # --- Lap time conversion function ---
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except Exception:
            return None

    filtered_df["LAP_TIME_SECONDS"] = filtered_df["LAP_TIME"].apply(lap_to_seconds)
    filtered_df = filtered_df.dropna(subset=["LAP_TIME_SECONDS"])

    # --- Find longest runs per car ---
    longest_runs = []

    for car, car_group in filtered_df.groupby("NUMBER"):
        # Sort laps by session and lap number
        if "LAP_NUMBER" in car_group.columns:
            car_group = car_group.sort_values(["PRACTICE_SESSION", "LAP_NUMBER"])
        else:
            car_group = car_group.sort_values("PRACTICE_SESSION")
            car_group = car_group.sort_index()

        car_group = car_group.reset_index(drop=True)

        max_stint = []
        max_stint_len = 0
        max_stint_session = None

        current_stint = []
        current_stint_session = None

        i = 0
        while i < len(car_group):
            row = car_group.iloc[i]
            pit_val = row.get("CROSSING_FINISH_LINE_IN_PIT", "")
            if pit_val == "B":
                # Pit lap and next lap are excluded
                if len(current_stint) > max_stint_len:
                    max_stint = current_stint
                    max_stint_len = len(current_stint)
                    max_stint_session = current_stint_session

                current_stint = []
                current_stint_session = None
                i += 2  # Skip pit lap and out lap
                continue

            if not current_stint:
                current_stint_session = row["PRACTICE_SESSION"]

            current_stint.append(row)
            i += 1

        # Check last stint at end
        if len(current_stint) > max_stint_len:
            max_stint = current_stint
            max_stint_len = len(current_stint)
            max_stint_session = current_stint_session

        if not max_stint:
            continue

        stint_df = pd.DataFrame(max_stint)
        avg_lap_time = stint_df["LAP_TIME_SECONDS"].mean()
        team = stint_df.iloc[0]["TEAM"]
        manufacturer = stint_df.iloc[0]["MANUFACTURER"]
        drivers = stint_df["DRIVER_NAME"].unique()
        driver_str = " / ".join(drivers)
        laps_list = stint_df["LAP_NUMBER"].astype(str).tolist()

        longest_runs.append({
            "Car": car,
            "Team": team,
            "Manufacturer": manufacturer,
            "Driver(s)": driver_str,
            "Avg Long Run Lap Time (s)": avg_lap_time,
            "Stint Laps": ", ".join(laps_list),
            "Stint Length": max_stint_len,
            "Session": max_stint_session
        })

    if not longest_runs:
        st.warning("No long runs found with the current filters.")
        return

    longest_runs_df = pd.DataFrame(longest_runs)

    # --- Sort by average lap time ascending ---
    longest_runs_df = longest_runs_df.sort_values("Avg Long Run Lap Time (s)")

    # --- Plot bar chart ---
    fig = px.bar(
        longest_runs_df,
        y="Car",
        x="Avg Long Run Lap Time (s)",
        color="Team",
        hover_data=["Driver(s)", "Stint Length", "Session"],
        orientation="h",
        color_discrete_map={team: col for team, col in zip(longest_runs_df["Team"], longest_runs_df["Team"].map(lambda t: team_colors.get(t, "#888888")))}
    )

    fig.update_yaxes(
        type='category',
        categoryorder='total ascending'
    )

    x_min = longest_runs_df["Avg Long Run Lap Time (s)"].min() - 0.5
    x_max = longest_runs_df["Avg Long Run Lap Time (s)"].max() + 0.5
    fig.update_xaxes(range=[x_min, x_max])

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white", size=14),
        xaxis_title="Average Long Run Lap Time (s)",
        yaxis_title="Car Number",
        title="Longest Practice Runs by Car",
        title_font=dict(size=22),
        showlegend=True,
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- Show tables per class ---
    for race_class in sorted(longest_runs_df["Team"].unique()):
        class_df = longest_runs_df[longest_runs_df["Team"] == race_class]
        if class_df.empty:
            continue

        st.markdown(f"### Long Runs for Team: {race_class}")

        for class_name in sorted(selected_classes):
            st.markdown(f"#### Class: {class_name}")
            class_data = longest_runs_df[longest_runs_df["Team"] == race_class]
            if class_data.empty:
                st.info("No data for this class.")
            else:
                # Filter rows by class
                filtered_class_data = longest_runs_df[longest_runs_df["Team"] == race_class]
                st.dataframe(filtered_class_data)

