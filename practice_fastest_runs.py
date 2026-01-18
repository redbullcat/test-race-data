import pandas as pd
import plotly.express as px
import streamlit as st

def show_practice_fastest_runs(df, team_colors):
    st.subheader("Fastest Run Average Pace by Car")

    # --- Classes filter ---
    classes = df["CLASS"].dropna().unique().tolist()
    selected_classes = st.multiselect(
        "Select Class(es):",
        options=classes,
        default=classes,
        key="practice_fastest_runs_class_filter"
    )

    filtered_df = df[df["CLASS"].isin(selected_classes)]

    # --- Cars filter ---
    available_cars = sorted(filtered_df["NUMBER"].unique().tolist())
    selected_cars = st.multiselect(
        "Select Car(s):",
        options=available_cars,
        default=available_cars,
        key="practice_fastest_runs_car_filter"
    )

    # --- Top lap % slider ---
    top_percent = st.slider(
        "Select Top Lap Percentage:",
        0,
        100,
        100,
        step=20,
        key="practice_fastest_runs_top_lap_filter",
        help="Use 0% to hide all data."
    )

    if top_percent == 0:
        st.warning("You selected 0%. You won't see any data.")
        return

    # --- Filter by selected classes and cars ---
    filtered_df = filtered_df[filtered_df["NUMBER"].isin(selected_cars)]

    # --- Convert LAP_TIME to seconds ---
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except Exception:
            return None

    filtered_df["LAP_TIME_SECONDS"] = filtered_df["LAP_TIME"].apply(lap_to_seconds)
    filtered_df = filtered_df.dropna(subset=["LAP_TIME_SECONDS"])

    # --- Filter top X% fastest laps per car ---
    def filter_top_percent_laps(df, percent):
        filtered_dfs = []
        for car_number, group in df.groupby("NUMBER"):
            group_sorted = group.sort_values("LAP_TIME_SECONDS")
            n_laps = len(group_sorted)
            n_keep = max(1, int(n_laps * percent / 100))
            filtered_dfs.append(group_sorted.head(n_keep))
        return pd.concat(filtered_dfs)

    filtered_df = filter_top_percent_laps(filtered_df, top_percent)

    # --- Find fastest no-pit stint per car (minimum 7 laps) ---
    fastest_runs = []

    for car_number, group in filtered_df.groupby("NUMBER"):
        group = group.sort_values("LAP_NUMBER").reset_index(drop=True)

        max_avg_lap_time = None
        fastest_stint = None

        current_stint = []
        skip_next = False

        for idx, row in group.iterrows():
            if skip_next:
                skip_next = False
                continue

            if str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B":
                if current_stint:
                    stint_df = pd.DataFrame(current_stint)
                    avg_lap_time = stint_df["LAP_TIME_SECONDS"].mean()

                    if (max_avg_lap_time is None) or (avg_lap_time < max_avg_lap_time):
                        max_avg_lap_time = avg_lap_time
                        fastest_stint = current_stint

                    current_stint = []
                skip_next = True
                continue

            current_stint.append(row)

        # Final check at end of group
        if current_stint:
            stint_df = pd.DataFrame(current_stint)
            avg_lap_time = stint_df["LAP_TIME_SECONDS"].mean()

            if (max_avg_lap_time is None) or (avg_lap_time < max_avg_lap_time):
                max_avg_lap_time = avg_lap_time
                fastest_stint = current_stint

        if fastest_stint:
            stint_df = pd.DataFrame(fastest_stint)
            stint_length = len(stint_df)

            # Only keep if stint length >= 7 laps
            if stint_length >= 7:
                avg_lap_time = stint_df["LAP_TIME_SECONDS"].mean()
                stint_laps = stint_df["LAP_NUMBER"].tolist()
                team = stint_df.iloc[0]["TEAM"] if "TEAM" in stint_df.columns else ""
                manufacturer = stint_df.iloc[0]["MANUFACTURER"] if "MANUFACTURER" in stint_df.columns else ""
                race_class = stint_df.iloc[0]["CLASS"] if "CLASS" in stint_df.columns else ""

                drivers = stint_df["DRIVER_NAME"].dropna().unique()
                drivers_str = " / ".join(drivers)

                fastest_runs.append({
                    "Car": car_number,
                    "Team": team,
                    "Manufacturer": manufacturer,
                    "Class": race_class,
                    "Drivers": drivers_str,
                    "Average_Lap_Time_Seconds": avg_lap_time,
                    "Lap_Numbers": stint_laps,
                    "Stint_Length": stint_length,
                })

    if not fastest_runs:
        st.warning("No valid fastest runs of at least 7 laps found for the selected filters.")
        return

    fastest_runs_df = pd.DataFrame(fastest_runs)

    # --- Color mapping ---
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"

    fastest_runs_df["color"] = fastest_runs_df["Team"].apply(get_team_color)
    fastest_runs_df["Label"] = fastest_runs_df["Car"].astype(str) + " — " + fastest_runs_df["Team"]

    # --- Plot fastest run average pace bar chart ---
    fig = px.bar(
        fastest_runs_df.sort_values("Average_Lap_Time_Seconds"),
        y="Label",
        x="Average_Lap_Time_Seconds",
        color="Team",
        orientation="h",
        color_discrete_map={team: col for team, col in zip(fastest_runs_df["Team"], fastest_runs_df["color"])},
        title="Fastest Run Average Pace by Car (Min 7 Laps)",
        labels={"Average_Lap_Time_Seconds": "Average Lap Time (s)", "Label": "Car — Team"},
    )

    fig.update_yaxes(
        type='category',
        categoryorder='array',
        categoryarray=fastest_runs_df.sort_values("Average_Lap_Time_Seconds")["Label"]
    )

    x_min = fastest_runs_df["Average_Lap_Time_Seconds"].min() - 0.5 if not fastest_runs_df.empty else 0
    x_max = fastest_runs_df["Average_Lap_Time_Seconds"].max() + 0.5 if not fastest_runs_df.empty else 1
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

    # --- Prepare and show detailed tables per class ---
    def format_lap_time(seconds):
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}:{secs:06.3f}"

    fastest_runs_df = fastest_runs_df.sort_values("Average_Lap_Time_Seconds").reset_index(drop=True)
    fastest_runs_df["Position"] = fastest_runs_df.index + 1
    fastest_runs_df["Average Fastest Run Lap Time"] = fastest_runs_df["Average_Lap_Time_Seconds"].apply(format_lap_time)
    fastest_runs_df["Lap Numbers"] = fastest_runs_df["Lap_Numbers"].apply(lambda laps: ", ".join(map(str, laps)))

    display_cols = [
        "Position",
        "Car",
        "Team",
        "Manufacturer",
        "Drivers",
        "Average Fastest Run Lap Time",
        "Lap Numbers",
        "Stint_Length"
    ]

    for cls in fastest_runs_df["Class"].unique():
        st.markdown(f"### Class: {cls}")
        class_df = fastest_runs_df[fastest_runs_df["Class"] == cls][display_cols].rename(
            columns={"Stint_Length": "Stint Length (laps)"}
        )
        st.dataframe(class_df, use_container_width=True)
