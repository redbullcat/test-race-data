import pandas as pd
import streamlit as st

def parse_lap_time(lap_time_str):
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
            return pd.Timedelta(seconds=minutes * 60 + seconds)
    except Exception:
        return None
    return None


def show_practice_fastest_laps(df: pd.DataFrame):
    st.markdown("### Practice Sessions - Fastest Laps")

    df = df.copy()

    required_columns = {
        "NUMBER",
        "TEAM",
        "LAP_TIME",
        "PRACTICE_SESSION",
        "CLASS",
        "DRIVER_NAME",
        "LAP_NUMBER",
        "MANUFACTURER",
    }

    missing = required_columns - set(df.columns)
    if missing:
        st.error(
            "Fastest laps table missing required columns: "
            + ", ".join(sorted(missing))
        )
        return

    # Clean LAP_TIME
    df["LAP_TIME"] = (
        df["LAP_TIME"]
        .astype(str)
        .str.strip()
        .replace({"": None, "nan": None, "NaN": None, "00:00.000": None})
    )

    df["LAP_TIME_TD"] = df["LAP_TIME"].apply(parse_lap_time)
    df = df.dropna(subset=["LAP_TIME_TD"])

    if df.empty:
        st.error("No valid lap times found after parsing LAP_TIME.")
        return

    if "CROSSING_FINISH_LINE_IN_PIT" in df.columns:
        df = df[df["CROSSING_FINISH_LINE_IN_PIT"] != 1]

    if df.empty:
        st.warning("All valid laps were pit laps.")
        return

    # ----------------------------
    # KEY CHANGE: group by NUMBER + TEAM
    # ----------------------------

    car_key = ["NUMBER", "TEAM"]

    # Total laps per car
    laps_completed = (
        df.groupby(car_key)["LAP_NUMBER"]
        .nunique()
        .rename("Laps Completed")
    )

    # Fastest lap per car
    idx = df.groupby(car_key)["LAP_TIME_TD"].idxmin()
    fastest = df.loc[idx].copy()

    fastest = fastest.sort_values("LAP_TIME_TD").reset_index(drop=True)
    fastest["Overall Position"] = range(1, len(fastest) + 1)

    fastest["Class Position"] = (
        fastest.groupby("CLASS")["LAP_TIME_TD"]
        .rank(method="min")
        .astype(int)
    )

    leader_time = fastest.iloc[0]["LAP_TIME_TD"]
    fastest["Gap"] = fastest["LAP_TIME_TD"] - leader_time

    def format_gap(td):
        return "—" if td == pd.Timedelta(0) else f"+{td.total_seconds():.3f}s"

    fastest["Gap"] = fastest["Gap"].apply(format_gap)

    # Drivers per (NUMBER, TEAM)
    drivers_map = (
        df.groupby(car_key)["DRIVER_NAME"]
        .unique()
        .apply(lambda x: sorted(set(x)))
        .to_dict()
    )

    def format_drivers(row):
        key = (row["NUMBER"], row["TEAM"])
        fastest_driver = row["DRIVER_NAME"]
        drivers = drivers_map.get(key, [])
        return " / ".join(
            f"*{d}*" if d == fastest_driver else d for d in drivers
        )

    fastest["Driver"] = fastest.apply(format_drivers, axis=1)

    # Interval to car ahead
    intervals = []
    for i in range(len(fastest)):
        if i == 0:
            intervals.append("—")
        else:
            gap = fastest.loc[i, "LAP_TIME_TD"] - fastest.loc[i - 1, "LAP_TIME_TD"]
            intervals.append(f"+{gap.total_seconds():.3f}s")

    fastest["Interval"] = intervals

    # Merge laps completed
    fastest = fastest.merge(
        laps_completed,
        left_on=car_key,
        right_index=True,
        how="left"
    )

    # Format lap time
    def format_lap_time(td):
        total = td.total_seconds()
        return f"{int(total // 60)}:{total % 60:06.3f}"

    fastest["Fastest Lap"] = fastest["LAP_TIME_TD"].apply(format_lap_time)

    # Team / Manufacturer lookup (now safe)
    team_manuf = (
        df.groupby(car_key)
        .agg({"TEAM": "first", "MANUFACTURER": "first"})
        .rename(columns={"TEAM": "Team", "MANUFACTURER": "Manufacturer"})
    )

    fastest = fastest.merge(
        team_manuf,
        left_on=car_key,
        right_index=True,
        how="left"
    )

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

    st.dataframe(display_df, width="stretch", hide_index=True)
