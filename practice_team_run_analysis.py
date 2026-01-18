import math
import pandas as pd
import plotly.express as px
import streamlit as st


def parse_hour_time(series: pd.Series) -> pd.Series:
    """
    Parse HOUR column (hh:mm:ss.000) into datetime and handle midnight rollover.
    """
    dt = pd.to_datetime(series, format="%H:%M:%S.%f", errors="coerce")

    rollover = dt.diff().dt.total_seconds() < -12 * 3600
    dt += pd.to_timedelta(rollover.cumsum(), unit="D")

    return dt


def show_practice_team_run_analysis(df, team_colors):
    st.subheader("Team Run Analysis by Session")

    # ----------------------------
    # Filters
    # ----------------------------
    classes = sorted(df["CLASS"].dropna().unique().tolist())
    selected_class = st.selectbox(
        "Select Class:",
        options=classes,
        key="team_run_class_filter"
    )

    class_df = df[df["CLASS"] == selected_class]

    teams = sorted(class_df["TEAM"].dropna().unique().tolist())
    selected_team = st.selectbox(
        "Select Team:",
        options=teams,
        key="team_run_team_filter"
    )

    team_df = class_df[class_df["TEAM"] == selected_team]

    cars = sorted(team_df["NUMBER"].dropna().unique().tolist())
    selected_car = st.selectbox(
        "Select Car:",
        options=cars,
        key="team_run_car_filter"
    )

    team_df = team_df[team_df["NUMBER"] == selected_car]

    if team_df.empty:
        st.warning("No data available for the selected team and car.")
        return

    # ----------------------------
    # Canonical session clock (HOUR only used for relative offsets)
    # ----------------------------
    team_df["HOUR_DT"] = parse_hour_time(team_df["HOUR"])
    team_df = team_df.dropna(subset=["HOUR_DT"])

    session_durations = st.session_state.get("session_durations", {})

    # ----------------------------
    # Per-session charts
    # ----------------------------
    for session_name, session_df in team_df.groupby("PRACTICE_SESSION"):
        st.markdown(f"### {session_name}")

        # Extract session number from "Session X"
        try:
            session_number = int(session_name.split()[-1])
        except Exception:
            st.warning(f"Could not determine duration for {session_name}.")
            continue

        if session_number not in session_durations:
            st.warning(f"No timing data available for {session_name}.")
            continue

        # Use canonical session duration (rounded up for display)
        session_duration_min = math.ceil(session_durations[session_number])

        # Session-relative zero (first car to cross line in this session)
        session_start_dt = session_df["HOUR_DT"].min()

        runs = []

        for _, car_df in session_df.groupby("NUMBER"):
            car_df = car_df.sort_values("LAP_NUMBER").reset_index(drop=True)

            current_run = []
            skip_next = False

            for _, row in car_df.iterrows():
                if skip_next:
                    skip_next = False
                    continue

                if str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B":
                    if current_run:
                        runs.append(current_run)
                        current_run = []
                    skip_next = True
                    continue

                current_run.append(row)

            if current_run:
                runs.append(current_run)

        if not runs:
            st.info("No valid runs found in this session.")
            continue

        run_rows = []

        for run in runs:
            run_df = pd.DataFrame(run)

            run_start_dt = run_df["HOUR_DT"].min()
            run_end_dt = run_df["HOUR_DT"].max()

            start_time_min = (
                (run_start_dt - session_start_dt).total_seconds() / 60
            )
            duration_min = (
                (run_end_dt - run_start_dt).total_seconds() / 60
            )

            run_rows.append({
                "Run Start": start_time_min,
                "Run Duration": duration_min,
                "Laps": len(run_df),
                "Car": run_df.iloc[0]["NUMBER"],
            })

        runs_df = pd.DataFrame(run_rows)

        if runs_df.empty:
            st.info("No plottable runs in this session.")
            continue

        # ----------------------------
        # Bar width scaling
        # ----------------------------
        min_width_min = 0.1
        scaled_widths = runs_df["Run Duration"].clip(lower=min_width_min)

        # ----------------------------
        # Plot
        # ----------------------------
        fig = px.bar(
            runs_df,
            x="Run Start",
            y="Laps",
            color="Car",
            title=f"{selected_team} – Runs in {session_name}",
        )

        fig.update_traces(
            width=scaled_widths,
            hovertemplate=(
                "Car: %{customdata[0]}<br>"
                "Laps: %{y}<br>"
                "Start: %{x:.2f} min<br>"
                "Duration: %{customdata[1]:.2f} min"
            ),
            customdata=runs_df[["Car", "Run Duration"]].values,
        )

        fig.update_xaxes(
            title="Session Time (minutes)",
            range=[0, session_duration_min]
        )

        fig.update_yaxes(
            title="Laps in Run"
        )

        fig.update_layout(
            plot_bgcolor="#2b2b2b",
            paper_bgcolor="#2b2b2b",
            font=dict(color="white", size=14),
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True)
