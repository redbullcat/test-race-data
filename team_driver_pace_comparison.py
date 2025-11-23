import streamlit as st
import pandas as pd
import plotly.express as px
import os

def show_team_driver_pace_comparison(team_colors):
    st.header("Team-by-Team Driver Pace Comparison")

    # --- Load race files correctly ---
    race_folder = "data"
    all_files = []

    for root, dirs, files in os.walk(race_folder):
        for f in files:
            if f.endswith(".csv"):
                all_files.append(os.path.join(root, f))

    if not all_files:
        st.error("No race CSV files found.")
        return

    # Clean race names for dropdown
    race_display_names = [f.replace(race_folder + "/", "") for f in all_files]

    selected_display = st.selectbox("Select Race", race_display_names)
    selected_file = all_files[race_display_names.index(selected_display)]

    # --- Load CSV ---
    df = pd.read_csv(selected_file, delimiter=';')
    df.columns = df.columns.str.strip()

    required_cols = {"TEAM", "DRIVER_NAME", "LAP_TIME", "CLASS", "NUMBER"}
    if not required_cols.issubset(df.columns):
        st.error("CSV missing required columns.")
        return

    # Convert lap times
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    df["LAP_TIME_SEC"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SEC"])

    # --- NEW: Class Tabs ---
    classes = sorted(df["CLASS"].dropna().unique())
    tabs = st.tabs(classes)

    for cls, tab in zip(classes, tabs):
        with tab:
            class_df = df[df["CLASS"] == cls]

            teams = sorted(class_df["TEAM"].dropna().unique())

            st.markdown(f"### {cls} Teams")
            st.write(", ".join(teams))
            st.markdown("---")

            # --- Team-by-team charts ---
            for team in teams:
                team_df = class_df[class_df["TEAM"] == team]

                driver_avgs = (
                    team_df.groupby("DRIVER_NAME")["LAP_TIME_SEC"]
                    .mean()
                    .reset_index()
                    .sort_values("LAP_TIME_SEC")
                )

                if driver_avgs.empty:
                    continue

                # Assign team color
                color = "#888888"
                for key, val in team_colors.items():
                    if key.lower() in team.lower():
                        color = val
                        break

                fig = px.bar(
                    driver_avgs,
                    x="DRIVER_NAME",
                    y="LAP_TIME_SEC",
                    title=f"{team} — Driver Comparison",
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
