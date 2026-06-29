import pandas as pd
import plotly.express as px
import streamlit as st
from utils import sort_cars, chart_export_buttons
from theme import apply_ota_layout


def parse_hour_time(series: pd.Series) -> pd.Series:
    """
    Parse HOUR column (hh:mm:ss.000) into datetime and handle midnight rollover.
    """
    dt = pd.to_datetime(series, format="%H:%M:%S.%f", errors="coerce")

    rollover = dt.diff().dt.total_seconds() < -12 * 3600
    dt += pd.to_timedelta(rollover.cumsum(), unit="D")

    return dt


def show_practice_team_run_analysis(df, team_colors, key_prefix="prac"):
    st.subheader("Team Run Analysis by Session")

    # ----------------------------
    # Filters
    # ----------------------------
    classes = sorted(df["CLASS"].dropna().unique().tolist())
    selected_class = st.selectbox(
        "Select Class:",
        options=classes,
        key=f"{key_prefix}_trun_class"
    )

    class_df = df[df["CLASS"] == selected_class]

    teams = sorted(class_df["TEAM"].dropna().unique().tolist())
    selected_team = st.selectbox(
        "Select Team:",
        options=teams,
        key=f"{key_prefix}_trun_team"
    )

    team_df = class_df[class_df["TEAM"] == selected_team]

    cars = sort_cars(team_df["NUMBER"].dropna().unique())
    selected_car = st.selectbox(
        "Select Car:",
        options=cars,
        key=f"{key_prefix}_trun_car"
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

    # ----------------------------
    # Manual session duration inputs
    # ----------------------------
    sessions_in_data = sorted(team_df["PRACTICE_SESSION"].dropna().unique())
    if not sessions_in_data:
        st.info("No session data available.")
        return

    # Try to get auto-detected durations from session state as defaults
    auto_durations = st.session_state.get("session_durations", {})

    st.markdown("**Session durations (minutes)** — edit if auto-detection is wrong:")
    dur_cols = st.columns(min(len(sessions_in_data), 4))
    manual_durations: dict[str, float] = {}
    for i, session_name in enumerate(sessions_in_data):
        col = dur_cols[i % len(dur_cols)]
        # Try to match auto-detected duration by session name substring
        auto_val = 60.0
        for fname, dur in auto_durations.items():
            if session_name.lower().replace(" ", "") in fname.lower().replace("_", ""):
                auto_val = dur
                break
        manual_durations[session_name] = col.number_input(
            session_name,
            min_value=1.0,
            max_value=1440.0,
            value=auto_val,
            step=5.0,
            key=f"{key_prefix}_trun_dur_{session_name}",
        )

    # ----------------------------
    # Per-session charts
    # ----------------------------
    for session_name, session_df in team_df.groupby("PRACTICE_SESSION"):
        st.markdown(f"### {session_name}")

        session_duration_min = manual_durations.get(session_name, 60.0)

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

        apply_ota_layout(fig)

        fig.update_layout(
            
            
            
            showlegend=False,
        )

        st.plotly_chart(fig, width='stretch')
        chart_export_buttons(fig=fig, filename="practice_team_run_analysis", height=500)
