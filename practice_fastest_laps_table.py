import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def show_practice_fastest_laps(df: pd.DataFrame):
    """
    Displays fastest lap classification per practice session.

    One table per session, ranked by overall fastest lap.
    """

    required_columns = {
        "PRACTICE_SESSION",
        "NUMBER",
        "CLASS",
        "LAP_TIME",
        "DRIVER_NAME"
    }

    missing = required_columns - set(df.columns)
    if missing:
        st.error(
            "Missing required columns for fastest lap table: "
            + ", ".join(sorted(missing))
        )
        return

    # Ensure lap time is numeric (seconds)
    lap_times = df.copy()
    lap_times["LAP_TIME"] = pd.to_timedelta(lap_times["LAP_TIME"]).dt.total_seconds()

    sessions = sorted(lap_times["PRACTICE_SESSION"].unique())

    for session in sessions:
        st.markdown(f"### {session}")

        session_df = lap_times[lap_times["PRACTICE_SESSION"] == session]

        # --- Fastest lap per car ---
        fastest_laps = (
            session_df
            .loc[session_df.groupby("NUMBER")["LAP_TIME"].idxmin()]
            .copy()
        )

        # --- Overall position ---
        fastest_laps = fastest_laps.sort_values("LAP_TIME")
        fastest_laps["Overall position"] = range(1, len(fastest_laps) + 1)

        # --- Position in class ---
        fastest_laps["Position in class"] = (
            fastest_laps
            .groupby("CLASS")["LAP_TIME"]
            .rank(method="min")
            .astype(int)
        )

        # --- Gap to leader ---
        leader_time = fastest_laps["LAP_TIME"].min()
        fastest_laps["Gap to leader"] = fastest_laps["LAP_TIME"] - leader_time
        fastest_laps.loc[
            fastest_laps["Gap to leader"] == 0, "Gap to leader"
        ] = 0.0

        # --- Driver formatting ---
        driver_map = (
            session_df
            .groupby("NUMBER")["DRIVER_NAME"]
            .unique()
            .to_dict()
        )

        formatted_drivers = []

        for _, row in fastest_laps.iterrows():
            car = row["NUMBER"]
            fastest_driver = row["DRIVER_NAME"]

            drivers = []
            for d in driver_map.get(car, []):
                if d == fastest_driver:
                    drivers.append(f"<i>{d}</i>")
                else:
                    drivers.append(d)

            formatted_drivers.append(", ".join(drivers))

        fastest_laps["Drivers"] = formatted_drivers

        # --- Format output ---
        output_df = fastest_laps[
            [
                "Overall position",
                "Position in class",
                "NUMBER",
                "CLASS",
                "Drivers",
                "LAP_TIME",
                "Gap to leader"
            ]
        ].rename(
            columns={
                "NUMBER": "Car",
                "CLASS": "Class",
                "LAP_TIME": "Fastest lap (s)"
            }
        )

        output_df["Fastest lap (s)"] = output_df["Fastest lap (s)"].map(
            lambda x: f"{x:.3f}"
        )

        output_df["Gap to leader"] = output_df["Gap to leader"].map(
            lambda x: "—" if x == 0 else f"+{x:.3f}"
        )

        # --- Plotly table ---
        fig = go.Figure(
            data=[
                go.Table(
                    header=dict(
                        values=list(output_df.columns),
                        fill_color="#2b2b2b",
                        font=dict(color="white", size=12),
                        align="left"
                    ),
                    cells=dict(
                        values=[output_df[col] for col in output_df.columns],
                        fill_color="#1f1f1f",
                        font=dict(color="white", size=11),
                        align="left"
                    )
                )
            ]
        )

        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0)
        )

        st.plotly_chart(fig, use_container_width=True)
