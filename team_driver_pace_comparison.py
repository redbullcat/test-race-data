import streamlit as st
import pandas as pd
import plotly.express as px
import os

def show_team_driver_pace_comparison(df, team_colors):
    st.header("Team Driver Pace Comparison (Per Team, Per Race)")

    # --- 1. Race selection (from CSV files in folders by year) ---
    race_folder = "data"   # << change if needed

    # Collect all CSV files recursively (from year subfolders)
    race_files = []
    for year_folder in sorted(os.listdir(race_folder)):
        year_path = os.path.join(race_folder, year_folder)
        if os.path.isdir(year_path):
            for file in os.listdir(year_path):
                if file.endswith(".csv"):
                    race_files.append(os.path.join(year_folder, file))

    if not race_files:
        st.error("No race CSV files found.")
        return

    selected_race = st.selectbox("Select Race", race_files)

    # Load the selected race file
    df = pd.read_csv(os.path.join(race_folder, selected_race))

    # Strip whitespace from headers to avoid key errors
    df.columns = df.columns.str.strip()
    st.write("Columns loaded from CSV:", df.columns.tolist())

    # Validate required columns exist
    required_cols = {"TEAM", "DRIVER_NAME", "LAP_TIME", "CLASS", "NUMBER"}
    if not required_cols.issubset(df.columns):
        st.error("CSV missing required columns.")
        return

    # Convert lap times to seconds
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    df["LAP_TIME_SEC"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SEC"])

    # Get teams for the selected race
    teams = sorted(df["TEAM"].dropna().unique())

    st.markdown("### Teams in this race")
    st.write(", ".join(teams))
    st.markdown("---")

    # Show pace comparison per team
    for team in teams:
        team_df = df[df["TEAM"] == team]

        driver_avgs = (
            team_df.groupby("DRIVER_NAME")["LAP_TIME_SEC"]
            .mean()
            .reset_index()
            .sort_values("LAP_TIME_SEC")
        )

        if driver_avgs.empty:
            continue

        color = "#888888"
        for key, val in team_colors.items():
            if key.lower() in team.lower():
                color = val
                break

        fig = px.bar(
            driver_avgs,
            x="DRIVER_NAME",
            y="LAP_TIME_SEC",
            title=f"{team} — Driver Pace Comparison ({selected_race})",
            labels={"LAP_TIME_SEC": "Average Lap Time (s)", "DRIVER_NAME": "Driver"},
            color_discrete_sequence=[color],
            text=driver_avgs["LAP_TIME_SEC"].round(3).astype(str),
        )

        fig.update_layout(
            plot_bgcolor="#2b2b2b",
            paper_bgcolor="#2b2b2b",
            font=dict(color="white"),
            yaxis=dict(autorange=True),
            title_font=dict(size=22),
        )

        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
