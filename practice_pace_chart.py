import plotly.express as px
import pandas as pd
import streamlit as st
from utils import lap_to_seconds, sort_cars, chart_export_buttons, get_team_color
from theme import apply_ota_layout

def show_practice_pace_chart(df, team_colors, key_prefix="prac"):
    st.subheader("Average Practice Pace by Car")

    # --- Classes filter ---
    classes = df["CLASS"].dropna().unique().tolist()
    selected_classes = st.multiselect(
        "Select Class(es):",
        options=classes,
        default=classes,
        key=f"{key_prefix}_pace_class"
    )

    filtered_df = df[df["CLASS"].isin(selected_classes)]

    # --- Cars filter ---
    available_cars = sort_cars(filtered_df["NUMBER"].unique())
    selected_cars = st.multiselect(
        "Select Car(s):",
        options=available_cars,
        default=available_cars,
        key=f"{key_prefix}_pace_car"
    )

    # --- Top lap % slider ---
    top_percent = st.slider(
        "Select Top Lap Percentage:",
        0,
        100,
        100,
        step=20,
        key=f"{key_prefix}_pace_top_lap",
        help="Use 0% to hide all data."
    )

    if top_percent == 0:
        st.warning("You selected 0%. You won't see any data.")
        return

    # --- Filter by selected classes and cars ---
    df = df[df["CLASS"].isin(selected_classes)]
    df = df[df["NUMBER"].isin(selected_cars)]

    # --- Lap time conversion function ---

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
        if not filtered_dfs:
            return pd.DataFrame()
        return pd.concat(filtered_dfs)

    filtered_df = filter_top_percent_laps(df, top_percent)

    if filtered_df.empty:
        st.info("No lap data available for the selected filters.")
        return

    # --- Average lap times per car ---
    avg_df = (
        filtered_df.groupby(["NUMBER", "TEAM", "CLASS"], as_index=False)["LAP_TIME_SECONDS"]
        .mean()
        .sort_values("LAP_TIME_SECONDS", ascending=True)
    )

    avg_df["color"] = avg_df["TEAM"].apply(lambda t: get_team_color(t, team_colors))
    avg_df["Label"] = avg_df["NUMBER"].astype(str) + " — " + avg_df["TEAM"]

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

    apply_ota_layout(fig)

    fig.update_layout(
        
        
        
        xaxis_title="Average Lap Time (s)",
        yaxis_title="Car Number — Team",
        title="Average Practice Pace by Car",
        title_font=dict(size=22),
        showlegend=True,
    )

    st.plotly_chart(fig, width='stretch')
    chart_export_buttons(fig=fig, filename="practice_pace_chart", height=500)
