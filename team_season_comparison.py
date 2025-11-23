import streamlit as st
import pandas as pd
import os
import plotly.express as px

def show_team_season_comparison(_, team_colors):
    st.header("Team Season Comparison")

    DATA_DIR = "data"

    # --- 1. Select Year ---
    years = sorted([d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))])
    selected_year = st.selectbox("Select Year", years)

    # --- 2. Load all race files for the selected year ---
    year_path = os.path.join(DATA_DIR, selected_year)
    race_files = [f for f in os.listdir(year_path) if f.endswith(".csv")]
    if not race_files:
        st.error(f"No race data found for year {selected_year}")
        return

    # --- 3. Get all classes for the year (collect from all races) ---
    classes_set = set()
    for race_file in race_files:
        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        classes_set.update(df["CLASS"].dropna().unique())
    classes = sorted(list(classes_set))
    selected_class = st.selectbox("Select Class", classes)

    # --- 4. Get all teams for the year and class (collect from all races) ---
    teams_set = set()
    for race_file in race_files:
        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        df = df[df["CLASS"] == selected_class]
        teams_set.update(df["TEAM"].dropna().unique())
    teams = sorted(list(teams_set))
    selected_team = st.selectbox("Select Team", teams)

    # --- 5. Select pace segments via checkboxes ---
    st.markdown("### Select Pace Segments (Top X% of laps per driver)")
    pace_options = [20, 40, 60, 80, 100]
    selected_paces = []
    cols = st.columns(len(pace_options))
    for i, pct in enumerate(pace_options):
        if cols[i].checkbox(f"{pct}%", value=(pct == 100)):
            selected_paces.append(pct)

    if not selected_paces:
        st.warning("Please select at least one pace segment to display charts.")
        return

    # --- 6. Show charts for each race ---
    for race_file in sorted(race_files):
        race_name = race_file.replace(".csv", "")
        st.subheader(f"{race_name} — {selected_team} — Class: {selected_class}")

        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        df.columns = df.columns.str.strip()

        # Filter to selected class and team
        team_class_df = df[(df["TEAM"] == selected_team) & (df["CLASS"] == selected_class)]

        if team_class_df.empty:
            st.info(f"No data available for {selected_team} in {race_name} for class {selected_class}")
            continue

        # Convert lap times to seconds
        def lap_to_seconds(x):
            try:
                mins, secs = x.split(":")
                return int(mins) * 60 + float(secs)
            except:
                return None

        team_class_df["LAP_TIME_SEC"] = team_class_df["LAP_TIME"].apply(lap_to_seconds)
        team_class_df = team_class_df.dropna(subset=["LAP_TIME_SEC"])

        if team_class_df.empty:
            st.info(f"No valid lap times for {selected_team} in {race_name} for class {selected_class}")
            continue

        # For each selected pace segment, compute avg lap times of top X% laps per driver and plot chart
        for pct in sorted(selected_paces):
            driver_avgs_list = []

            # Process each driver individually
            for driver in team_class_df["DRIVER_NAME"].unique():
                driver_laps = team_class_df[team_class_df["DRIVER_NAME"] == driver].copy()
                # Sort laps ascending (fastest first)
                driver_laps = driver_laps.sort_values("LAP_TIME_SEC")

                # Calculate number of laps for top X%
                n_laps = max(1, int(len(driver_laps) * (pct / 100)))
                top_laps = driver_laps.head(n_laps)

                avg_lap = top_laps["LAP_TIME_SEC"].mean()
                driver_avgs_list.append({"DRIVER_NAME": driver, "LAP_TIME_SEC": avg_lap})

            driver_avgs = pd.DataFrame(driver_avgs_list).sort_values("LAP_TIME_SEC")

            if driver_avgs.empty:
                st.info(f"No lap data to show for top {pct}% pace segment.")
                continue

            # Get color for this team
            color = "#888888"
            for key, val in team_colors.items():
                if key.lower() in selected_team.lower():
                    color = val
                    break

            fig = px.bar(
                driver_avgs,
                x="DRIVER_NAME",
                y="LAP_TIME_SEC",
                title=f"{selected_team} - Driver Average Lap Times (Top {pct}%)",
                labels={"LAP_TIME_SEC": "Average Lap Time (s)", "DRIVER_NAME": "Driver"},
                color_discrete_sequence=[color],
                text=driver_avgs["LAP_TIME_SEC"].round(3).astype(str),
            )
            fig.update_layout(
                plot_bgcolor="#2b2b2b",
                paper_bgcolor="#2b2b2b",
                font=dict(color="white"),
                yaxis=dict(autorange=True),
                title_font=dict(size=18),
            )

            st.plotly_chart(fig, use_container_width=True)
            st.markdown("---")
