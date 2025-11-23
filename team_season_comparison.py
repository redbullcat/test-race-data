import streamlit as st
import pandas as pd
import os
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

    # --- 3. Get all classes and teams for the year (collect from all races) ---
    classes_set = set()
    for race_file in race_files:
        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        classes_set.update(df["CLASS"].dropna().unique())
    classes = sorted(list(classes_set))

    # --- 4. Class selection dropdown ---
    selected_class = st.selectbox("Select Class", classes)

    # --- Filter teams by selected class ---
    teams_set = set()
    for race_file in race_files:
        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        teams_set.update(df[df["CLASS"] == selected_class]["TEAM"].dropna().unique())
    teams = sorted(list(teams_set))

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
                    textangle=90,
                )
            )

        # Calculate y-axis range with padding of 1 second
        all_y_values = []
        for trace in fig.data:
            all_y_values.extend(trace.y)
        if all_y_values:
            min_y = min(all_y_values)
            max_y = max(all_y_values)
            y_range = [min_y - 1 if min_y - 1 > 0 else 0, max_y + 1]
        else:
            y_range = None

        fig.update_layout(
            barmode="group",
            plot_bgcolor="#2b2b2b",
            paper_bgcolor="#2b2b2b",
            font=dict(color="white"),
            yaxis=dict(autorange=False, range=y_range, title="Average Lap Time (s)"),
            title=dict(text=f"{selected_team} - Driver Average Lap Times", font=dict(size=18)),
        )

        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")

    # --- 8. Season summary chart: Driver average lap times across all races ---
    st.subheader(f"{selected_team} - Season Summary ({selected_class})")

    # Prepare data for all races combined
    summary_records = []

    for race_file in sorted(race_files):
        race_name = race_file.replace(".csv", "")

        df = pd.read_csv(os.path.join(year_path, race_file), delimiter=";")
        df.columns = df.columns.str.strip()

        # Filter by team and class
        team_class_df = df[(df["TEAM"] == selected_team) & (df["CLASS"] == selected_class)]

        if team_class_df.empty:
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

        # For each pace %, compute average lap time per driver for this race
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
            )

            for _, row in driver_avgs.iterrows():
                summary_records.append({
                    "Race": race_name,
                    "Driver": row["DRIVER_NAME"],
                    "AverageLapTime": row["LAP_TIME_SEC"],
                    "PacePercent": pct,
                })

    if not summary_records:
        st.info("No data available for season summary chart.")
        return

    summary_df = pd.DataFrame(summary_records)

    # Pivot for grouped bar chart: x=Race, y=AvgLapTime, group=Driver (and PacePercent for pattern)
    fig = go.Figure()

    # Get team color once
    color = "#888888"
    for key, val in team_colors.items():
        if key.lower() in selected_team.lower():
            color = val
            break

    # Plot bars: one trace per driver and pace percent combination
    for (driver, pct), group_df in summary_df.groupby(["Driver", "PacePercent"]):
        fig.add_trace(
            go.Bar(
                x=group_df["Race"],
                y=group_df["AverageLapTime"],
                name=f"{driver} - Top {pct}%",
                marker=dict(color=color, pattern=dict(shape=pattern_shapes.get(pct, ""))),
                text=group_df["AverageLapTime"].round(3).astype(str),
                textposition="outside",
                textangle=90,
            )
        )

    # Calculate y-axis range with 1s padding
    all_y_values = summary_df["AverageLapTime"].tolist()
    min_y = min(all_y_values)
    max_y = max(all_y_values)
    y_range = [min_y - 1 if min_y - 1 > 0 else 0, max_y + 1]

    fig.update_layout(
        barmode="group",
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white"),
        yaxis=dict(autorange=False, range=y_range, title="Average Lap Time (s)"),
        xaxis=dict(title="Race"),
        title=dict(text=f"{selected_team} - Driver Average Lap Times Across Season", font=dict(size=18)),
        legend_title_text="Driver - Pace %",
        legend=dict(font=dict(size=10)),
    )

    st.plotly_chart(fig, use_container_width=True)
