import pandas as pd
import streamlit as st

def show_practice_fastest_laps(df: pd.DataFrame):
    st.subheader("⏱️ Practice Sessions - Fastest Laps")

    # Defensive copy
    df = df.copy()

    # Strip all column headers just in case
    df.columns = df.columns.str.strip()

    # Check required columns
    required_columns = {"NUMBER", "LAP_TIME", "PRACTICE_SESSION", "CLASS", "DRIVER_NAME"}
    missing = required_columns - set(df.columns)
    if missing:
        st.error("Missing required columns: " + ", ".join(missing))
        return

    # Strip whitespace from LAP_TIME and DRIVER_NAME columns
    df["LAP_TIME"] = df["LAP_TIME"].astype(str).str.strip()
    df["DRIVER_NAME"] = df["DRIVER_NAME"].astype(str).str.strip()

    # Robust lap time to seconds parser
    def lap_to_seconds(lap):
        if pd.isna(lap) or lap == "" or lap.lower() in {"nan", "na"}:
            return None
        lap = lap.strip()
        parts = lap.split(':')
        try:
            if len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
        except Exception:
            return None
        return None

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SECONDS"])

    if df.empty:
        st.warning("No valid lap times found.")
        return

    # Build driver list per car
    driver_map = (
        df.groupby("NUMBER")["DRIVER_NAME"]
        .unique()
        .apply(lambda x: " / ".join(sorted(x)))
        .to_dict()
    )

    # For each session, produce a fastest laps table
    sessions = sorted(df["PRACTICE_SESSION"].unique())
    for session in sessions:
        st.markdown(f"### {session}")

        session_df = df[df["PRACTICE_SESSION"] == session].copy()

        # Find fastest lap per car
        idx = session_df.groupby("NUMBER")["LAP_TIME_SECONDS"].idxmin()
        fastest = session_df.loc[idx].copy()

        # Overall position by fastest lap time
        fastest = fastest.sort_values("LAP_TIME_SECONDS")
        fastest["Overall Position"] = range(1, len(fastest) + 1)

        # Class position
        fastest["Class Position"] = (
            fastest.groupby("CLASS")["LAP_TIME_SECONDS"]
            .rank(method="min")
            .astype(int)
        )

        # Gap to leader
        leader_time = fastest.iloc[0]["LAP_TIME_SECONDS"]
        fastest["Gap (s)"] = fastest["LAP_TIME_SECONDS"] - leader_time
        fastest["Gap (s)"] = fastest["Gap (s)"].apply(lambda x: "—" if x == 0 else f"+{x:.3f}")

        # Drivers - full list and italicize driver with fastest lap
        def format_drivers(row):
            all_drivers = driver_map.get(row["NUMBER"], "")
            fastest_driver = row["DRIVER_NAME"]
            # Italicize fastest driver within all drivers
            if fastest_driver in all_drivers:
                return all_drivers.replace(fastest_driver, f"*{fastest_driver}*")
            return all_drivers

        fastest["Drivers"] = fastest.apply(format_drivers, axis=1)

        # Prepare display DataFrame
        display_df = fastest[
            [
                "Overall Position",
                "Class Position",
                "NUMBER",
                "CLASS",
                "Drivers",
                "LAP_TIME",
                "Gap (s)",
            ]
        ].rename(columns={
            "NUMBER": "Car",
            "CLASS": "Class",
            "LAP_TIME": "Fastest Lap"
        })

        # Set index as position for nicer display
        display_df = display_df.set_index("Overall Position")

        st.dataframe(display_df, width="stretch", hide_index=False)
