import plotly.express as px
import pandas as pd
import streamlit as st

def show_practice_pace_chart(df, team_colors):
    st.subheader("Average Practice Pace by Car")

    # --- Classes filter ---
    classes = df["CLASS"].dropna().unique().tolist()
    selected_classes = st.multiselect(
        "Select Class(es):",
        options=classes,
        default=classes,
        key="practice_pace_class_filter"
    )

    filtered_df = df[df["CLASS"].isin(selected_classes)]

    # --- Cars filter ---
    available_cars = sorted(filtered_df["NUMBER"].unique().tolist())
    selected_cars = st.multiselect(
        "Select Car(s):",
        options=available_cars,
        default=available_cars,
        key="practice_pace_car_filter"
    )

    # --- Top lap % slider ---
    top_percent = st.slider(
        "Select Top Lap Percentage:",
        0,
        100,
        100,
        step=20,
        key="practice_pace_top_lap_filter",
        help="Use 0% to hide all data."
    )

    if top_percent == 0:
        st.warning("You selected 0%. You won't see any data.")
        return

    # --- Filter by selected classes and cars ---
    df = df[df["CLASS"].isin(selected_classes)]
    df = df[df["NUMBER"].isin(selected_cars)]

    # --- Lap time conversion function ---
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except Exception:
            return None

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SECONDS"])

    # --- Filter top X% fastest laps per car ---
    def filter_top_percent_laps(df, percent):
        filtered_dfs = []
        for car_number, group in df.groupby("NUMBER"):
            group_sorted = group.sort_values("LAP_TIME_SECONDS")
            n_laps = len(group_sorted)
            n_keep = max(1, int(n_laps * percent / 100))
            filtered_dfs.append(group_sorted.head(n_keep))
        return pd.concat(filtered_dfs)

    filtered_df = filter_top_percent_laps(df, top_percent)

    # --- Average lap times per car ---
    avg_df = (
        filtered_df.groupby(["NUMBER", "TEAM", "CLASS"], as_index=False)["LAP_TIME_SECONDS"]
        .mean()
        .sort_values("LAP_TIME_SECONDS", ascending=True)
    )

    # --- Map team colors ---
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"

    avg_df["color"] = avg_df["TEAM"].apply(get_team_color)
    avg_df["Label"] = avg_df["NUMBER"] + " — " + avg_df["TEAM"]

    # --- Plotly bar chart ---
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

    x_min = avg_df["LAP_TIME_SECONDS"].min() - 0.5 if not avg_df.empty else 0
    x_max = avg_df["LAP_TIME_SECONDS"].max() + 0.5 if not avg_df.empty else 1
    fig.update_xaxes(range=[x_min, x_max])

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white", size=14),
        xaxis_title="Average Lap Time (s)",
        yaxis_title="Car Number — Team",
        title="Average Practice Pace by Car",
        title_font=dict(size=22),
        showlegend=True,
    )

    st.plotly_chart(fig, use_container_width=True)
