import plotly.express as px
import pandas as pd
import streamlit as st

def show_driver_pace_chart(df, selected_cars, top_percent, selected_classes, team_colors):

    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SECONDS"])

    # Apply filters for class and selected cars
    df = df[df["CLASS"].isin(selected_classes)]
    if selected_cars:
        df = df[df["NUMBER"].isin(selected_cars)]

    # Filter top X% laps per driver (within each car)
    def filter_top_percent_laps(df, percent):
        filtered_dfs = []
        for (car_number, driver), group in df.groupby(["NUMBER", "DRIVER_NAME"]):
            group_sorted = group.sort_values("LAP_TIME_SECONDS")
            n_laps = len(group_sorted)
            n_keep = max(1, int(n_laps * percent / 100))
            filtered_dfs.append(group_sorted.head(n_keep))
        return pd.concat(filtered_dfs)

    filtered_df = filter_top_percent_laps(df, top_percent)

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
