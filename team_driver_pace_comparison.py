import streamlit as st
import pandas as pd
import plotly.express as px

def show_team_driver_pace_comparison(df, team_colors):
    st.header("Team Driver Pace Comparison (Per Team)")

    # Basic validation
    required_cols = {"TEAM", "DRIVER_NAME", "LAP_TIME", "CLASS", "NUMBER"}
    if not required_cols.issubset(df.columns):
        st.error("Data missing required columns.")
        return

    # Convert lap times to seconds
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    df["LAP_TIME_SEC"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SEC"])

    # List of teams in this data
    teams = sorted(df["TEAM"].dropna().unique())

    st.markdown("### Teams in this race")
    st.write(", ".join(teams))
    st.markdown("---")

    # Process each team separately
    for team in teams:
        team_df = df[df["TEAM"] == team]

        # Average lap time per driver
        driver_avgs = (
            team_df.groupby("DRIVER_NAME")["LAP_TIME_SEC"]
            .mean()
            .reset_index()
            .sort_values("LAP_TIME_SEC")
        )

        if driver_avgs.empty:
            continue

        # Assign team color
        color = "#888888"
        for key, val in team_colors.items():
            if key.lower() in team.lower():
                color = val
                break

        # Build bar chart for this team
        fig = px.bar(
            driver_avgs,
            x="DRIVER_NAME",
            y="LAP_TIME_SEC",
            title=f"{team} — Driver Pace Comparison",
            labels={"LAP_TIME_SEC": "Average Lap Time (s)", "DRIVER_NAME": "Driver"},
            color_discrete_sequence=[color],
            text=driver_avgs["LAP_TIME_SEC"].round(3).astype(str),
        )

        fig.update_layout(
            plot_bgcolor="#2b2b2b",
            paper_bgcolor="#2b2b2b",
            font=dict(color="white"),
            yaxis=dict(autorange=True),
            title_font=dict(size=22),
        )

        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
