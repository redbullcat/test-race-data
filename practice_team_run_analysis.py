import pandas as pd
import plotly.express as px
import streamlit as st


def show_practice_team_run_analysis(df, team_colors):
    st.subheader("Team Run Analysis by Session")

    required_cols = {
        "CLASS",
        "TEAM",
        "NUMBER",
        "LAP_NUMBER",
        "PRACTICE_SESSION",
        "CROSSING_FINISH_LINE_IN_PIT"
    }

    if not required_cols.issubset(df.columns):
        st.error("Required columns missing for team run analysis.")
        return

    # --- Class selector ---
    classes = sorted(df["CLASS"].dropna().unique().tolist())
    selected_class = st.selectbox(
        "Select Class:",
        options=classes,
        key="team_run_class_selector"
    )

    class_df = df[df["CLASS"] == selected_class]

    # --- Team selector ---
    teams = sorted(class_df["TEAM"].dropna().unique().tolist())
    selected_team = st.selectbox(
        "Select Team:",
        options=teams,
        key="team_run_team_selector"
    )

    team_df = class_df[class_df["TEAM"] == selected_team]

    if team_df.empty:
        st.warning("No data available for this team.")
        return

    # --- Helper: extract runs from a car/session ---
    def extract_runs(car_df):
        car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)

        runs = []
        current_run = []
        skip_next = False

        for _, row in car_df.iterrows():
            if skip_next:
                skip_next = False
                continue

            if str(row["CROSSING_FINISH_LINE_IN_PIT"]).strip().upper() == "B":
                if current_run:
                    runs.append(current_run)
                    current_run = []
                skip_next = True
                continue

            current_run.append(row)

        if current_run:
            runs.append(current_run)

        return runs

    run_records = []

    # --- Process per session ---
    for session, session_df in team_df.groupby("PRACTICE_SESSION"):
        session_df = session_df.copy()

        # Normalise lap numbers per session (session start = 0)
        session_df["SESSION_LAP_INDEX"] = (
            session_df["LAP_NUMBER"] - session_df["LAP_NUMBER"].min()
        )

        for car, car_df in session_df.groupby("NUMBER"):
            runs = extract_runs(car_df)

            for run in runs:
                run_df = pd.DataFrame(run)

                if run_df.empty:
                    continue

                run_start = run_df["SESSION_LAP_INDEX"].min()
                run_length = len(run_df)

                run_records.append({
                    "Session": session,
                    "Team": selected_team,
                    "Car": car,
                    "Run_Start": run_start,
                    "Run_Length": run_length
                })

    if not run_records:
        st.warning("No valid runs found for this team.")
        return

    runs_df = pd.DataFrame(run_records)

    # --- Team color ---
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"

    team_color = get_team_color(selected_team)

    # --- Plot one chart per session ---
    for session in sorted(runs_df["Session"].unique()):
        st.markdown(f"### {session}")

        session_runs = runs_df[runs_df["Session"] == session]

        fig = px.bar(
            session_runs,
            x="Run_Start",
            y="Run_Length",
            color_discrete_sequence=[team_color],
            labels={
                "Run_Start": "Session Time (laps since start)",
                "Run_Length": "Run Length (laps)"
            },
        )

        fig.update_layout(
            plot_bgcolor="#2b2b2b",
            paper_bgcolor="#2b2b2b",
            font=dict(color="white", size=14),
            xaxis_title="Session Progress (laps)",
            yaxis_title="Run Length (laps)",
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True)
