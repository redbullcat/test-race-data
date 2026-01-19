import pandas as pd
import plotly.express as px
import streamlit as st

def show_practice_long_runs(longest_stints_df, team_colors):
    st.subheader("Longest Run Pace by Car (Lap-by-Lap)")

    if longest_stints_df.empty:
        st.warning("No longest stint data available.")
        return

    # --- Filters ---
    classes = sorted(longest_stints_df["Class"].dropna().unique().tolist())
    selected_classes = st.multiselect(
        "Select Class(es):",
        options=classes,
        default=classes,
        key="practice_long_runs_class_filter"
    )

    filtered_df = longest_stints_df[longest_stints_df["Class"].isin(selected_classes)]

    available_cars = sorted(filtered_df["Car"].unique().tolist())
    selected_cars = st.multiselect(
        "Select Car(s):",
        options=available_cars,
        default=available_cars,
        key="practice_long_runs_car_filter"
    )

    filtered_df = filtered_df[filtered_df["Car"].isin(selected_cars)]

    if filtered_df.empty:
        st.warning("No data for selected filters.")
        return

    # --- Prepare data for plotting ---
    plot_data = []

    for _, row in filtered_df.iterrows():
        lap_nums = row["Lap_Numbers"]
        lap_times = row["Lap_Times"]
        car_label = f"{row['Car']} — {row['Team']}"

        for lap_num, lap_time in zip(lap_nums, lap_times):
            plot_data.append({
                "Car": car_label,
                "Lap": lap_num,
                "Lap Time (s)": lap_time
            })

    plot_df = pd.DataFrame(plot_data)

    # --- Get color mapping ---
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"

    car_to_color = {}
    for _, row in filtered_df.iterrows():
        car_to_color[f"{row['Car']} — {row['Team']}"] = get_team_color(row["Team"])

    # --- Plot line chart ---
    fig = px.line(
        plot_df,
        x="Lap",
        y="Lap Time (s)",
        color="Car",
        color_discrete_map=car_to_color,
        title="Lap-by-Lap Pace for Longest Stints",
        markers=True,
        labels={"Lap": "Lap Number", "Lap Time (s)": "Lap Time (seconds)"}
    )

    fig.update_yaxes(autorange="reversed")

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white", size=14),
        legend_title_text="Car — Team",
        title_font=dict(size=20),
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- Debug: Show raw data table below the chart ---
    st.markdown("#### Raw Data for Longest Stints")

    table_data = []
    for _, row in filtered_df.iterrows():
        table_data.append({
            "Car": row["Car"],
            "Team": row["Team"],
            "Manufacturer": row["Manufacturer"],
            "Class": row["Class"],
            "Drivers": row["Drivers"],
            "Session": row["Session"],
            "Stint Length (Laps)": row["Stint_Length"],
            "Lap Numbers": ", ".join(str(ln) for ln in row["Lap_Numbers"]),
            "Lap Times (s)": ", ".join(f"{lt:.3f}" for lt in row["Lap_Times"]),
            "Average 20% Pace (s)": (
                f"{row['Average_20_Percent_Pace']:.3f}"
                if pd.notnull(row["Average_20_Percent_Pace"])
                else "N/A"
            )
        })

    debug_df = pd.DataFrame(table_data)
    st.dataframe(debug_df, use_container_width=True)
