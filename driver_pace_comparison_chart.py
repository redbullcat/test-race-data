import plotly.express as px
import streamlit as st

def show_driver_pace_comparison(df, team_colors):
    st.markdown("## 🏁 Driver Pace Comparison")

    # Get classes available in the data
    available_classes = df['CLASS'].dropna().unique().tolist()
    selected_classes = st.multiselect("Select class(es) to compare", available_classes)

    # Collect selected drivers from each class
    selected_drivers = []
    for race_class in selected_classes:
        class_drivers = df[df['CLASS'] == race_class]['DRIVER_NAME'].dropna().unique().tolist()
        chosen = st.multiselect(f"Select drivers from {race_class}", class_drivers, key=f"drivers_{race_class}")
        selected_drivers.extend(chosen)

    if len(selected_drivers) < 2:
        st.info("Please select at least two drivers to compare.")
        return

    # Filter dataframe to only selected drivers
    filtered_df = df[df['DRIVER_NAME'].isin(selected_drivers)]

    # Convert LAP_TIME to seconds if needed
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    filtered_df["LAP_TIME_SECONDS"] = filtered_df["LAP_TIME"].apply(lap_to_seconds)
    filtered_df = filtered_df.dropna(subset=["LAP_TIME_SECONDS"])

    # Calculate average lap time per driver and get team info
    driver_pace = (
        filtered_df.groupby(['DRIVER_NAME', 'TEAM', 'CLASS'], as_index=False)['LAP_TIME_SECONDS']
        .mean()
        .sort_values('LAP_TIME_SECONDS', ascending=True)
    )

    # Map team colors using your team_colors dict (case-insensitive)
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return '#888888'

    driver_pace['color'] = driver_pace['TEAM'].apply(get_team_color)

    # Build color map for plotly using unique teams in filtered data
    unique_teams = driver_pace['TEAM'].unique()
    color_map = {team: get_team_color(team) for team in unique_teams}

    # Create bar chart
    fig_driver_pace = px.bar(
        driver_pace,
        x='DRIVER_NAME',
        y='LAP_TIME_SECONDS',
        color='TEAM',
        color_discrete_map=color_map,
        title='Driver Average Pace Comparison',
        labels={'LAP_TIME_SECONDS': 'Average Lap Time (s)', 'DRIVER_NAME': 'Driver'},
        text=driver_pace['LAP_TIME_SECONDS'].round(3).astype(str),
    )

    # Style the plot for dark theme and reverse y-axis so fastest on top
    fig_driver_pace.update_layout(
        plot_bgcolor='#2b2b2b',
        paper_bgcolor='#2b2b2b',
        font_color='white',
        title_font_color='white',
        xaxis_title_font_color='white',
        yaxis_title_font_color='white',
    )

    st.plotly_chart(fig_driver_pace, use_container_width=True)
