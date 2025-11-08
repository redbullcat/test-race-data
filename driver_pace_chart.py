import plotly.express as px
import pandas as pd
import streamlit as st

def show_driver_pace_chart(df, team_colors):
    # --- Independent Class selector ---
    available_classes = sorted(df['CLASS'].dropna().unique())
    if not available_classes:
        st.warning("No classes available in data for driver pace chart.")
        return

    selected_classes = st.multiselect("Select Class for Driver Pace Chart", available_classes, default=available_classes)
    if not selected_classes:
        st.warning("No classes selected for driver pace chart.")
        return

    # Filter df by selected classes
    class_df = df[df['CLASS'].isin(selected_classes)]

    # --- Independent Car selector ---
    available_cars = sorted(class_df['NUMBER'].unique())
    selected_cars = st.multiselect("Select Cars for Driver Pace Chart", available_cars, default=available_cars)
    if not selected_cars:
        st.warning("No cars selected for driver pace chart.")
        return

    # --- Top percent slider ---
    top_percent = st.slider(
        "Select Top Lap Percentage (per driver)",
        0,
        100,
        100,
        step=5,
        help="Filter top percentage of fastest laps per driver."
    )
    if top_percent == 0:
        st.warning("You selected 0%. No data will be displayed.")

    # Filter df by selected cars
    filtered_df = class_df[class_df["NUMBER"].isin(selected_cars)]

    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    filtered_df["LAP_TIME_SECONDS"] = filtered_df["LAP_TIME"].apply(lap_to_seconds)
    filtered_df = filtered_df.dropna(subset=["LAP_TIME_SECONDS"])

    # Filter top X% laps per driver (within each car)
    def filter_top_percent_laps(df, percent):
        filtered_dfs = []
        for (car_number, driver), group in df.groupby(["NUMBER", "DRIVER_NAME"]):
            group_sorted = group.sort_values("LAP_TIME_SECONDS")
            n_laps = len(group_sorted)
            n_keep = max(1, int(n_laps * percent / 100))
            filtered_dfs.append(group_sorted.head(n_keep))
        return pd.concat(filtered_dfs)

    filtered_df = filter_top_percent_laps(filtered_df, top_percent)

    # Compute average lap time per driver
    avg_df = (
        filtered_df.groupby(["DRIVER_NAME", "TEAM", "NUMBER", "CLASS"], as_index=False)["LAP_TIME_SECONDS"]
        .mean()
        .sort_values("LAP_TIME_SECONDS", ascending=True)
    )

    # Assign team colors
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"

    avg_df["color"] = avg_df["TEAM"].apply(get_team_color)
    avg_df["Label"] = (
        avg_df["DRIVER_NAME"]
        + " — "
        + avg_df["TEAM"]
        + " (#"
        + avg_df["NUMBER"].astype(str)
        + ")"
    )

    # Create the bar chart
    fig = px.bar(
        avg_df,
        y="Label",
        x="LAP_TIME_SECONDS",
        color="TEAM",
        orientation="h",
        color_discrete_map={team: col for team, col in zip(avg_df["TEAM"], avg_df["color"])},
    )

    fig.update_yaxes(
        type='category',
        categoryorder='array',
        categoryarray=avg_df["Label"]
    )

    # Dynamic x-axis range
    x_min = avg_df["LAP_TIME_SECONDS"].min() - 0.5 if not avg_df.empty else 0
    x_max = avg_df["LAP_TIME_SECONDS"].max() + 0.5 if not avg_df.empty else 1
    fig.update_xaxes(range=[x_min, x_max])

    # Dark theme layout
    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white", size=14),
        xaxis_title="Average Lap Time (s)",
        yaxis_title="Driver — Team (Car #)",
        title="Average Race Pace by Driver",
        title_font=dict(size=22),
        showlegend=True,
    )

    st.plotly_chart(fig, use_container_width=True)
