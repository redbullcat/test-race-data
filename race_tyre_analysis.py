import pandas as pd
import streamlit as st

def detect_pit_laps(df: pd.DataFrame) -> pd.Series:
    """
    Identify pit laps using multiple signals.
    """
    # Convert PIT_TIME to seconds (handle string times like '0:01:31.090')
    def parse_pit_time(val):
        if pd.isna(val):
            return 0.0
        s = str(val).strip()
        if s == "" or s.lower() in {"nan", "na", "none"}:
            return 0.0
        try:
            # mm:ss.xxx or hh:mm:ss.xxx
            parts = s.split(":")
            if len(parts) == 2:
                mins, rest = parts
                return int(mins) * 60 + float(rest)
            elif len(parts) == 3:
                hrs, mins, rest = parts
                return int(hrs) * 3600 + int(mins) * 60 + float(rest)
            else:
                return float(s)
        except ValueError:
            return 0.0

    pit_time_seconds = df["PIT_TIME"].apply(parse_pit_time)
    return (df["CROSSING_FINISH_LINE_IN_PIT"] == 1) | (pit_time_seconds > 3)  # Threshold can be adjusted per class if needed

def infer_tyre_stints(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign TYRE_STINT_ID per CAR_ID based on pit stops and driver changes.
    """
    df = df.copy()
    df["PIT_LAP"] = detect_pit_laps(df)
    df["DRIVER_CHANGED"] = (
        df.groupby("CAR_ID")["DRIVER_NUMBER"].shift() != df["DRIVER_NUMBER"]
    ).fillna(False)

    df = df.sort_values(["CAR_ID", "LAP_NUMBER"])

    df["TYRE_STINT_ID"] = 0
    stint_id = 0

    prev_car = None
    prev_pit = False

    for idx, row in df.iterrows():
        if row["CAR_ID"] != prev_car:
            stint_id = 0
        elif row["PIT_LAP"] and (row["DRIVER_CHANGED"] or row["PIT_TIME"] > 5):
            stint_id += 1

        df.at[idx, "TYRE_STINT_ID"] = stint_id
        prev_car = row["CAR_ID"]
        prev_pit = row["PIT_LAP"]

    return df

def lap_time_to_seconds(lap_time_str: str) -> float:
    """
    Convert lap time string to seconds (float).
    Handles formats like '1:26.345' or '0:01:31.090'.
    Returns NaN if invalid.
    """
    if pd.isna(lap_time_str):
        return float('nan')
    s = str(lap_time_str).strip()
    if s == "" or s.lower() in {"nan", "na", "none"}:
        return float('nan')
    try:
        parts = s.split(":")
        if len(parts) == 2:
            mins, rest = parts
            return int(mins) * 60 + float(rest)
        elif len(parts) == 3:
            hrs, mins, rest = parts
            return int(hrs) * 3600 + int(mins) * 60 + float(rest)
        else:
            return float(s)
    except ValueError:
        return float('nan')

def tyre_stint_pace_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize pace for each tyre stint by class, team, car, and stint.
    """
    df = df.copy()
    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_time_to_seconds)
    # Filter valid lap times only
    df = df[df["LAP_TIME_SECONDS"].notna()]

    summary = (
        df.groupby(
            ["CLASS", "TEAM", "NUMBER", "CAR_ID", "TYRE_STINT_ID"],
            dropna=False,
        )
        .agg(
            laps=("LAP_NUMBER", "count"),
            avg_lap=("LAP_TIME_SECONDS", "mean"),
            min_lap=("LAP_TIME_SECONDS", "min"),
            max_lap=("LAP_TIME_SECONDS", "max"),
        )
        .reset_index()
    )
    return summary

def show_tyre_analysis(df: pd.DataFrame):
    st.subheader("Tyre stint analysis")

    df = infer_tyre_stints(df)
    summary = tyre_stint_pace_summary(df)

    classes = sorted(summary["CLASS"].dropna().unique())

    if classes:
        tabs = st.tabs(classes)
        for tab, race_class in zip(tabs, classes):
            with tab:
                class_df = summary[summary["CLASS"] == race_class]
                if not class_df.empty:
                    # Team selector filtered by class
                    teams = sorted(class_df["TEAM"].dropna().unique())
                    selected_team = st.selectbox(
                        "Select Team",
                        ["All"] + teams,
                        key=f"team_{race_class}",
                    )

                    # Filter by selected team if not "All"
                    if selected_team != "All":
                        filtered_df = class_df[class_df["TEAM"] == selected_team]
                    else:
                        filtered_df = class_df

                    # Car selector filtered by selected team
                    cars = sorted(filtered_df["NUMBER"].dropna().astype(str).unique())
                    selected_car = st.selectbox(
                        "Select Car Number",
                        ["All"] + cars,
                        key=f"car_{race_class}",
                    )

                    # Filter by selected car number if not "All"
                    if selected_car != "All":
                        filtered_df = filtered_df[
                            filtered_df["NUMBER"].astype(str) == selected_car
                        ]

                    st.write(f"Tyre stint pace summary for class {race_class}")
                    st.dataframe(
                        filtered_df.sort_values(["CAR_ID", "TYRE_STINT_ID"]),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No tyre stint data available for this class.")
    else:
        st.info("No tyre stint data available for analysis.")
