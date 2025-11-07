import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------
#  GAP EVOLUTION CHART
#  Shows gap between selected cars relative to fastest finisher
# ---------------------------------------------------------------

def show_gap_evolution_chart(df, team_colors):
    st.header("📉 Gap Evolution Chart")

    # Ensure correct column types
    if 'CLASS' not in df.columns or 'NUMBER' not in df.columns or 'LAP_TIME' not in df.columns:
        st.warning("Required columns missing: CLASS, NUMBER, LAP_TIME")
        return

    # Dropdown for class selection
    selected_class = st.selectbox(
        "Select class:",
        sorted(df['CLASS'].unique())
    )

    class_df = df[df['CLASS'] == selected_class].copy()

    # Dropdown for car selection
    car_numbers = sorted(class_df['NUMBER'].unique())
    selected_cars = st.multiselect(
        "Select cars to compare:",
        options=car_numbers,
        default=car_numbers[:3] if len(car_numbers) >= 3 else car_numbers
    )

    if not selected_cars:
        st.info("Please select at least one car to display.")
        return

    # Filter data for selected cars
    selected_df = class_df[class_df['NUMBER'].isin(selected_cars)].copy()

    # Compute cumulative race time per car
    selected_df['LAP_TIME_SEC'] = (
        pd.to_timedelta(selected_df['LAP_TIME']).dt.total_seconds()
    )

    selected_df['CUM_TIME'] = selected_df.groupby('NUMBER')['LAP_TIME_SEC'].cumsum()

    # Determine fastest finisher (lowest final cumulative time)
    final_times = selected_df.groupby('NUMBER')['CUM_TIME'].max()
    fastest_car = final_times.idxmin()

    # Compute gap to fastest car per lap
    ref_df = selected_df[selected_df['NUMBER'] == fastest_car][['LAP_NUMBER', 'CUM_TIME']].rename(
        columns={'CUM_TIME': 'FASTEST_CUM'}
    )

    merged = selected_df.merge(ref_df, on='LAP_NUMBER', how='left')
    merged['GAP_TO_FASTEST'] = merged['CUM_TIME'] - merged['FASTEST_CUM']

    # Plotly chart
    fig = go.Figure()

    for car in selected_cars:
        car_data = merged[merged['NUMBER'] == car]
        team_name = car_data['TEAM'].iloc[0] if 'TEAM' in car_data.columns else ''
        color = team_colors.get(team_name, team_colors.get(str(car), None))

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
        xaxis=dict(color='white'),
        yaxis=dict(color='white'),
        legend=dict(bgcolor='rgba(0,0,0,0)')
    )

    st.plotly_chart(fig, use_container_width=True)
