import plotly.graph_objects as go
import streamlit as st
import pandas as pd

def show_driver_pace_comparison(df, team_colors):
    st.markdown("## 🏁 Driver Pace Comparison by Top Lap Percentiles")

    # Select classes
    available_classes = df['CLASS'].dropna().unique().tolist()
    selected_classes = st.multiselect("Select class(es) to compare", available_classes)
    if not selected_classes:
        st.info("Please select at least one class.")
        return

    # Select drivers by class
    selected_drivers = []
    for race_class in selected_classes:
        class_drivers = df[df['CLASS'] == race_class]['DRIVER_NAME'].dropna().unique().tolist()
        chosen = st.multiselect(f"Select drivers from {race_class}", class_drivers, key=f"drivers_{race_class}")
        selected_drivers.extend(chosen)
    if len(selected_drivers) < 2:
        st.info("Please select at least two drivers to compare.")
        return

    # Checkbox for lap percentiles
    st.markdown("### Select Lap Percentiles to Display")
    percentile_options = [20, 40, 60, 80, 100]
    selected_percentiles = []
    for p in percentile_options:
        if st.checkbox(f"Top {p}%", value=(p==100)):
            selected_percentiles.append(p)
    if not selected_percentiles:
        st.warning("Select at least one percentile range to display.")
        return

    # Convert lap times to seconds helper
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SECONDS"])

    filtered_df = df[df['DRIVER_NAME'].isin(selected_drivers)]

    # Prepare data for each percentile group
    data = []
    for p in selected_percentiles:
        avg_pace = []
        for driver in selected_drivers:
            driver_laps = filtered_df[filtered_df['DRIVER_NAME'] == driver].sort_values("LAP_TIME_SECONDS")
            n_laps = len(driver_laps)
            n_keep = max(1, int(n_laps * p / 100))
            top_laps = driver_laps.head(n_keep)
            avg_time = top_laps["LAP_TIME_SECONDS"].mean()
            avg_pace.append(avg_time)
        data.append((p, avg_pace))

    # Build bar traces
    fig = go.Figure()
    for (p, avg_pace) in data:
        fig.add_trace(go.Bar(
            name=f"Top {p}%",
            x=selected_drivers,
            y=avg_pace,
            text=[f"{t:.3f}" for t in avg_pace],
            textposition='auto',
        ))

    # Layout
    fig.update_layout(
        barmode='group',
        title="Driver Average Pace by Lap Percentiles",
        xaxis_title="Driver",
        yaxis_title="Average Lap Time (seconds)",
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font_color="white",
        legend_title="Percentile Range",
    )
    fig.update_yaxes(autorange="reversed")  # so fastest times are on top

    st.plotly_chart(fig, use_container_width=True)
