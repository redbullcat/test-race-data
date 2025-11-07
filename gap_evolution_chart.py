import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------
#  GAP EVOLUTION CHART
#  Shows gap between selected cars relative to fastest finisher
# ---------------------------------------------------------------

def show_gap_evolution_chart(df, team_colors):
    st.header("📉 Gap Evolution Chart")

    # Ensure required columns exist
    required_cols = {'CLASS', 'NUMBER', 'LAP_TIME', 'LAP_NUMBER', 'TEAM', 'ELAPSED'}
    if not required_cols.issubset(df.columns):
        st.warning(f"Required columns missing: {required_cols - set(df.columns)}")
        return

    # Dropdown for class selection
    selected_class = st.selectbox(
        "Select class:",
        sorted(df['CLASS'].dropna().unique())
    )

    class_df = df[df['CLASS'] == selected_class].copy()

    # Dropdown for car selection
    car_numbers = sorted(class_df['NUMBER'].dropna().unique())
    selected_cars = st.multiselect(
        "Select cars to compare:",
        options=car_numbers,
        default=car_numbers[:3] if len(car_numbers) >= 3 else car_numbers
    )

    if not selected_cars:
        st.info("Please select at least one car to display.")
        return

    selected_df = class_df[class_df['NUMBER'].isin(selected_cars)].copy()

    # Convert LAP_TIME to seconds (same logic as results_table)
    def time_to_seconds(time_str):
        try:
            parts = str(time_str).split(':')
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
            else:
                return float(time_str)
        except:
            return None

    selected_df['LAP_TIME_SEC'] = selected_df['LAP_TIME'].apply(time_to_seconds)

    # Ensure LAP_NUMBER is numeric and drop rows with missing laps or lap times
    selected_df = selected_df.dropna(subset=['LAP_TIME_SEC', 'LAP_NUMBER'])
    selected_df['LAP_NUMBER'] = pd.to_numeric(selected_df['LAP_NUMBER'], errors='coerce')

    # Lap range filter slider
    min_lap = int(selected_df['LAP_NUMBER'].min())
    max_lap = int(selected_df['LAP_NUMBER'].max())
    lap_range = st.slider(
        "Select lap range to display",
        min_value=min_lap,
        max_value=max_lap,
        value=(min_lap, max_lap)
    )

    # Filter selected_df by lap range
    selected_df = selected_df[
        (selected_df['LAP_NUMBER'] >= lap_range[0]) & (selected_df['LAP_NUMBER'] <= lap_range[1])
    ]

    # Compute cumulative time per car
    selected_df['CUM_TIME'] = selected_df.groupby('NUMBER')['LAP_TIME_SEC'].cumsum()

    # Find fastest finisher (lowest final cumulative time)
    final_times = selected_df.groupby('NUMBER')['CUM_TIME'].max()
    fastest_car = final_times.idxmin()

    # Reference laps and cumulative times for fastest car
    ref_df = selected_df[selected_df['NUMBER'] == fastest_car][['LAP_NUMBER', 'CUM_TIME']].rename(
        columns={'CUM_TIME': 'FASTEST_CUM'}
    )

    # Merge and compute gap to fastest car per lap
    merged = selected_df.merge(ref_df, on='LAP_NUMBER', how='left')
    merged['GAP_TO_FASTEST'] = merged['CUM_TIME'] - merged['FASTEST_CUM']

    # Build Plotly figure
    fig = go.Figure()

    for car in selected_cars:
        car_data = merged[merged['NUMBER'] == car]
        if car_data.empty:
            continue

        team_name = car_data['TEAM'].iloc[0] if 'TEAM' in car_data.columns else ''
        color = team_colors.get(team_name, "#AAAAAA")

        fig.add_trace(go.Scatter(
            x=car_data['LAP_NUMBER'],
            y=car_data['GAP_TO_FASTEST'],
            mode='lines',
            name=f"{car} – {team_name}",
            line=dict(width=2, color=color)
        ))

    fig.update_layout(
        title=f"Gap Evolution – {selected_class}",
        xaxis_title="Lap Number",
        yaxis_title="Gap to Fastest (seconds)",
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white"),
        xaxis=dict(color='white', gridcolor="#444"),
        yaxis=dict(color='white', gridcolor="#444"),
        legend=dict(bgcolor='rgba(0,0,0,0)')
    )

    st.plotly_chart(fig, use_container_width=True)
