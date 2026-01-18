import pandas as pd
import plotly.express as px
import streamlit as st


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

    if team_df.empty:
        st.warning("No data available for the selected team.")
        return

    # ----------------------------
    # ELAPSED → seconds conversion
    # ----------------------------
    def elapsed_to_seconds(x):
        try:
            parts = str(x).split(":")
            if len(parts) == 2:
                mins, secs = parts
                return int(mins) * 60 + float(secs)
            elif len(parts) == 3:
                hrs, mins, secs = parts
                return int(hrs) * 3600 + int(mins) * 60 + float(secs)
        except Exception:
            return None

    team_df["ELAPSED_SECONDS"] = team_df["ELAPSED"].apply(elapsed_to_seconds)
    team_df = team_df.dropna(subset=["ELAPSED_SECONDS"])

    # ----------------------------
    # Per-session charts
    # ----------------------------
    for session_name, session_df in team_df.groupby("PRACTICE_SESSION"):
        st.markdown(f"### {session_name}")

        # True session duration (on-track)
        session_duration = session_df["ELAPSED_SECONDS"].max()

        runs = []

        for car_number, car_df in session_df.groupby("NUMBER"):
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

            start_time = run_df["ELAPSED_SECONDS"].min()
            end_time = run_df["ELAPSED_SECONDS"].max()
            duration = end_time - start_time
            lap_count = len(run_df)

            run_rows.append({
                "Run Start": start_time,
                "Run Duration": duration,
                "Laps": lap_count,
                "Car": run_df.iloc[0]["NUMBER"],
            })

        runs_df = pd.DataFrame(run_rows)

        if runs_df.empty:
            st.info("No plottable runs in this session.")
            continue

        # ----------------------------
        # Plot
        # ----------------------------
        fig = px.bar(
            runs_df,
            x="Run Start",
            y="Laps",
            width=duration if duration > 0 else None,
            color="Car",
            title=f"{selected_team} – Runs in {session_name}",
        )

        fig.update_traces(
            width=runs_df["Run Duration"],
            hovertemplate=(
                "Car: %{customdata[0]}<br>"
                "Laps: %{y}<br>"
                "Start: %{x:.1f}s<br>"
                "Duration: %{customdata[1]:.1f}s"
            ),
            customdata=runs_df[["Car", "Run Duration"]].values,
        )

        fig.update_xaxes(
            title="Session Time (seconds)",
            range=[0, session_duration]
        )

        fig.update_yaxes(
            title="Laps in Run"
        )

        fig.update_layout(
            plot_bgcolor="#2b2b2b",
            paper_bgcolor="#2b2b2b",
            font=dict(color="white", size=14),
            showlegend=True,
        )

        st.plotly_chart(fig, use_container_width=True)
