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

    # --- 4. Class selection dropdown ---
    selected_class = st.selectbox("Select Class", classes)

    # --- 5. Get all teams for the selected class in the year ---
    teams_set = set()
    for race_file in race_files:
        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        class_teams = df[df["CLASS"] == selected_class]["TEAM"].dropna().unique()
        teams_set.update(class_teams)
    teams = sorted(list(teams_set))

    # --- 6. Team selection dropdown ---
    selected_team = st.selectbox("Select Team", teams)

    # --- 7. Show charts for each race ---
    for race_file in sorted(race_files):
        race_name = race_file.replace(".csv", "")
        st.subheader(f"{race_name} — {selected_team} — {selected_class}")

        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        df.columns = df.columns.str.strip()

        # Filter to selected team and class
        team_df = df[(df["TEAM"] == selected_team) & (df["CLASS"] == selected_class)]

        # Defensive: skip empty data
        if team_df.empty:
            st.info(f"No data available for {selected_team} in {race_name} for class {selected_class}")
            continue

        # Convert lap times to seconds
        def lap_to_seconds(x):
            try:
                mins, secs = x.split(":")
                return int(mins) * 60 + float(secs)
            except:
                return None

        team_df["LAP_TIME_SEC"] = team_df["LAP_TIME"].apply(lap_to_seconds)
        team_df = team_df.dropna(subset=["LAP_TIME_SEC"])

        # Get average lap time per driver for this race
        driver_avgs = (
            team_df.groupby("DRIVER_NAME")["LAP_TIME_SEC"]
            .mean()
            .reset_index()
            .sort_values("LAP_TIME_SEC")
        )

        if driver_avgs.empty:
            st.info(f"No valid lap times for {selected_team} in {race_name} for class {selected_class}")
            continue

        # Get color for this team
        color = "#888888"
        for key, val in team_colors.items():
            if key.lower() in selected_team.lower():
                color = val
                break

        # Plot bar chart of driver average lap times
        fig = px.bar(
            driver_avgs,
            x="DRIVER_NAME",
            y="LAP_TIME_SEC",
            title=f"{selected_team} - Driver Average Lap Times",
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
