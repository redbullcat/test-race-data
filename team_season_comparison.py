import streamlit as st
import pandas as pd
import plotly.express as px
import os

def show_team_season_comparison(df_unused, team_colors):  # df_unused here because we'll load all races ourselves
    st.header("Team Season Driver Pace Comparison")

    # --- LOAD ALL CSVs across years in "data" folder ---
    race_folder = "data"
    all_files = []

    for root, dirs, files in os.walk(race_folder):
        for f in files:
            if f.endswith(".csv"):
                all_files.append(os.path.join(root, f))

    if not all_files:
        st.error("No race CSV files found in data folder.")
        return

    # Load and concatenate all CSVs
    dfs = []
    for file in all_files:
        tmp_df = pd.read_csv(file, delimiter=';')
        tmp_df.columns = tmp_df.columns.str.strip()
        
        # Add YEAR and RACE_NAME columns based on folder and file name
        parts = file.replace("\\", "/").split("/")
        # Example parts: ['data', '2024', 'race1.csv']
        if len(parts) >= 3:
            tmp_df["YEAR"] = parts[-2]
            tmp_df["RACE_NAME"] = parts[-1].replace(".csv", "")
        else:
            tmp_df["YEAR"] = "Unknown"
            tmp_df["RACE_NAME"] = file

        dfs.append(tmp_df)

    df = pd.concat(dfs, ignore_index=True)

    # --- VALIDATE REQUIRED COLUMNS ---
    required_cols = {"TEAM", "DRIVER_NAME", "LAP_TIME", "CLASS", "NUMBER", "RACE_NAME", "YEAR"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        st.error(f"CSV missing required columns: {', '.join(missing_cols)}")
        return

    # Convert lap times to seconds helper
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    df["LAP_TIME_SEC"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SEC"])

    # Classes & tabs
    classes = sorted(df["CLASS"].dropna().unique())
    tabs = st.tabs(classes)

    for cls, tab in zip(classes, tabs):
        with tab:
            class_df = df[df["CLASS"] == cls]

            teams = sorted(class_df["TEAM"].dropna().unique())
            if not teams:
                st.info(f"No teams available in class {cls}")
                continue

            selected_team = st.selectbox(f"Select Team for class {cls}", teams, key=f"team_select_{cls}")

            team_df = class_df[class_df["TEAM"] == selected_team]
            if team_df.empty:
                st.info(f"No data for team {selected_team} in class {cls}")
                continue

            avg_df = (
                team_df.groupby(["RACE_NAME", "DRIVER_NAME"])["LAP_TIME_SEC"]
                .mean()
                .reset_index()
                .sort_values(["RACE_NAME", "LAP_TIME_SEC"])
            )

            if avg_df.empty:
                st.info(f"No driver lap time data for team {selected_team} in class {cls}")
                continue

            color = "#888888"
            for key, val in team_colors.items():
                if key.lower() in selected_team.lower():
                    color = val
                    break

            fig = px.line(
                avg_df,
                x="RACE_NAME",
                y="LAP_TIME_SEC",
                color="DRIVER_NAME",
                title=f"{selected_team} — Driver Pace Across Season ({cls})",
                labels={"LAP_TIME_SEC": "Average Lap Time (s)", "RACE_NAME": "Race", "DRIVER_NAME": "Driver"},
                markers=True,
                color_discrete_sequence=px.colors.qualitative.Safe
            )

            fig.update_layout(
                plot_bgcolor="#2b2b2b",
                paper_bgcolor="#2b2b2b",
                font=dict(color="white"),
                yaxis=dict(autorange=True),
                title_font=dict(size=22),
                legend_title_text="Driver",
            )

            st.plotly_chart(fig, use_container_width=True)
