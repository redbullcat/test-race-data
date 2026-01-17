import pandas as pd
import streamlit as st

def parse_lap_time(lap_time_str):
    """
    Parse a lap time string like 'm:ss.xxx' or 'mm:ss.xxx' into a pd.Timedelta.
    Returns None if parsing fails.
    """
    if pd.isna(lap_time_str):
        return None
    lap_time_str = str(lap_time_str).strip()
    if lap_time_str == "" or lap_time_str.lower() in {"nan", "na", "none"}:
        return None
    parts = lap_time_str.split(":")
    try:
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            total_seconds = minutes * 60 + seconds
            return pd.Timedelta(seconds=total_seconds)
    except Exception:
        return None
    return None

def show_practice_fastest_laps(df: pd.DataFrame):
    st.markdown("### Practice Sessions - Fastest Laps")

    # Defensive copy
    df = df.copy()

    # Required columns
    required_columns = {
        "NUMBER",
        "LAP_TIME",
        "PRACTICE_SESSION",
        "CLASS",
        "DRIVER_NAME",
        "LAP_NUMBER",
        "TEAM",
        "MANUFACTURER",
    }

    missing = required_columns - set(df.columns)
    if missing:
        st.error(
            "Fastest laps table missing required columns: "
            + ", ".join(sorted(missing))
        )
        return

    # Clean LAP_TIME values
    df["LAP_TIME"] = (
        df["LAP_TIME"]
        .astype(str)
        .str.strip()
        .replace({
            "": None,
            "nan": None,
            "NaN": None,
            "00:00.000": None,
        })
    )

    # Parse LAP_TIME into Timedelta
    df["LAP_TIME_TD"] = df["LAP_TIME"].apply(parse_lap_time)

    # Drop invalid laps
    df = df.dropna(subset=["LAP_TIME_TD"])

    if df.empty:
        st.error("No valid lap times found after parsing LAP_TIME.")
        return

    # Exclude pit laps if column exists
    if "CROSSING_FINISH_LINE_IN_PIT" in df.columns:
        df = df[df["CROSSING_FINISH_LINE_IN_PIT"] != 1]

    if df.empty:
        st.warning("All valid laps were pit laps.")
        return

    # Calculate total laps per car across all sessions
    laps_completed = df.groupby("NUMBER")["LAP_NUMBER"].nunique().rename("Laps Completed")

    # Find fastest lap per car across all sessions combined
    idx = df.groupby("NUMBER")["LAP_TIME_TD"].idxmin()
    fastest = df.loc[idx].copy()

    # Sort fastest laps by lap time ascending
    fastest = fastest.sort_values("LAP_TIME_TD")
    fastest["Overall Position"] = range(1, len(fastest) + 1)

    # Class ranking
    fastest["Class Position"] = (
        fastest.groupby("CLASS")["LAP_TIME_TD"]
        .rank(method="min")
        .astype(int)
    )

    # Gap to leader
    leader_time = fastest.iloc[0]["LAP_TIME_TD"]
    fastest["Gap"] = fastest["LAP_TIME_TD"] - leader_time

    def format_gap(td):
        if td == pd.Timedelta(0):
            return "—"
        return f"+{td.total_seconds():.3f}s"

    fastest["Gap"] = fastest["Gap"].apply(format_gap)

    # Create a map: car -> all unique drivers sorted alphabetically
    drivers_map = (
        df.groupby("NUMBER")["DRIVER_NAME"]
        .unique()
        .apply(lambda names: sorted(set(names)))
        .to_dict()
    )

    # Build the Driver column with all drivers per car, italicizing the fastest lap setter
    def format_drivers(row):
        car = row["NUMBER"]
        fastest_driver = row["DRIVER_NAME"]
        drivers = drivers_map.get(car, [])
        formatted_drivers = []
        for d in drivers:
            if d == fastest_driver:
                formatted_drivers.append(f"*{d}*")
            else:
                formatted_drivers.append(d)
        return " / ".join(formatted_drivers)

    fastest["Driver"] = fastest.apply(format_drivers, axis=1)

    # Calculate interval to the car ahead
    fastest = fastest.sort_values("LAP_TIME_TD").reset_index(drop=True)
    intervals = []
    for i, row in fastest.iterrows():
        if i == 0:
            intervals.append("—")
        else:
            prev_time = fastest.loc[i-1, "LAP_TIME_TD"]
            gap = row["LAP_TIME_TD"] - prev_time
            intervals.append(f"+{gap.total_seconds():.3f}s")

    fastest["Interval"] = intervals

    # Add laps completed column
    fastest = fastest.merge(laps_completed, left_on="NUMBER", right_index=True, how="left")

    # Format fastest lap time for display
    def format_lap_time(td):
        if pd.isna(td):
            return ""
        total_seconds = td.total_seconds()
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:06.3f}"

    fastest["Fastest Lap"] = fastest["LAP_TIME_TD"].apply(format_lap_time)

    # Extract team and manufacturer info for each car
    team_manuf = (
        df.groupby("NUMBER")
        .agg({
            "TEAM": "first",
            "MANUFACTURER": "first"
        })
        .rename(columns={"TEAM": "Team", "MANUFACTURER": "Manufacturer"})
    )

    fastest = fastest.merge(team_manuf, left_on="NUMBER", right_index=True, how="left")

    # Prepare display dataframe including the session column and new columns
    display_df = fastest[
        [
            "Overall Position",
            "Class Position",
            "NUMBER",
            "CLASS",
            "Driver",
            "PRACTICE_SESSION",
            "Fastest Lap",
            "Gap",
            "Interval",
            "Laps Completed",
            "Team",
            "Manufacturer",
        ]
    ].rename(columns={
        "NUMBER": "Car",
        "CLASS": "Class",
        "PRACTICE_SESSION": "Session",
    })

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True
    )
