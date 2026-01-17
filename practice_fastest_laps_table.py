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

    # Driver formatting
    fastest["Driver"] = fastest["DRIVER_NAME"]

    # Format fastest lap time for display
    def format_lap_time(td):
        if pd.isna(td):
            return ""
        total_seconds = td.total_seconds()
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:06.3f}"

    fastest["Fastest Lap"] = fastest["LAP_TIME_TD"].apply(format_lap_time)

    # Prepare display dataframe including the session column and fastest lap
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
