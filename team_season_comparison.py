import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go

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

    # --- 3. Get all teams for the year (collect from all races) ---
    teams_set = set()
    classes_set = set()
    for race_file in race_files:
        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        teams_set.update(df["TEAM"].dropna().unique())
        classes_set.update(df["CLASS"].dropna().unique())
    teams = sorted(list(teams_set))
    classes = sorted(list(classes_set))

    # --- 4. Class selection dropdown ---
    selected_class = st.selectbox("Select Class", classes)

    # --- 5. Team selection dropdown ---
    selected_team = st.selectbox("Select Team", teams)

    # --- 6. Pace % checkboxes ---
    st.markdown("### Select Pace Percentages to Display")
    pace_percents = [20, 40, 60, 80, 100]
    pace_selected = []
    cols = st.columns(len(pace_percents))
    for i, pct in enumerate(pace_percents):
        if cols[i].checkbox(f"Top {pct}%", value=True):
            pace_selected.append(pct)

    if not pace_selected:
        st.warning("Select at least one pace percentage to display.")
        return

    # Define pattern shapes for each pace segment
    pattern_shapes = {
        20: "",
        40: "/",
        60: "x",
        80: ".",
        100: "+"
    }

    # --- 7. Show charts for each race ---
    for race_file in sorted(race_files):
        race_name = race_file.replace(".csv", "")
        st.subheader(f"{race_name} — {selected_team} — {selected_class}")

        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        df.columns = df.columns.str.strip()

        # Filter to selected team and class
        team_class_df = df[(df["TEAM"] == selected_team) & (df["CLASS"] == selected_class)]

        # Defensive: skip empty data
        if team_class_df.empty:
            st.info(f"No data available for {selected_team} in {race_name} ({selected_class})")
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

        # Start building figure with multiple traces (one per selected pace%)
        fig = go.Figure()

        # For each selected pace%, calculate average lap time per driver and add a trace
        for pct in pace_selected:
            top_count = max(1, int(len(team_class_df) * pct / 100))
            filtered_df = (
                team_class_df.sort_values("LAP_TIME_SEC")
                .groupby("DRIVER_NAME")
                .head(top_count)
            )

            driver_avgs = (
                filtered_df.groupby("DRIVER_NAME")["LAP_TIME_SEC"]
                .mean()
                .reset_index()
                .sort_values("LAP_TIME_SEC")
            )

            if driver_avgs.empty:
                continue

            # Get team color
            color = "#888888"
            for key, val in team_colors.items():
                if key.lower() in selected_team.lower():
                    color = val
                    break

            fig.add_trace(
                go.Bar(
                    x=driver_avgs["DRIVER_NAME"],
                    y=driver_avgs["LAP_TIME_SEC"],
                    name=f"Top {pct}%",
                    marker=dict(
                        color=color,
                        pattern=dict(shape=pattern_shapes.get(pct, ""))
                    ),
                    text=driver_avgs["LAP_TIME_SEC"].round(3).astype(str),
                    textposition="outside",
                )
            )

        fig.update_layout(
            barmode="group",
            plot_bgcolor="#2b2b2b",
            paper_bgcolor="#2b2b2b",
            font=dict(color="white"),
            yaxis=dict(autorange=True, title="Average Lap Time (s)"),
            title=dict(text=f"{selected_team} - Driver Average Lap Times", font=dict(size=18)),
        )

        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
