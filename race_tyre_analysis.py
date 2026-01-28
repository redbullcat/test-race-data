import pandas as pd
import numpy as np
import streamlit as st

def parse_lap_time_to_seconds(val):
    """
    Convert lap time strings like 'm:ss.xxx' or 'mm:ss.xxx' to float seconds.
    Returns pd.NA if parsing fails.
    """
    if pd.isna(val):
        return pd.NA

    val = str(val).strip()

    try:
        if ":" in val:
            mins, rest = val.split(":")
            secs = float(rest)
            return int(mins) * 60 + secs
        return float(val)
    except Exception:
        return pd.NA

def detect_pit_laps(df: pd.DataFrame) -> pd.Series:
    """Identify pit laps using multiple signals."""
    return (
        (df["CROSSING_FINISH_LINE_IN_PIT"] == 1)
        | (df["PIT_TIME"].fillna(0).astype(float) > 3.0)  # threshold can be adjusted per class
    )

def infer_tyre_stints(df: pd.DataFrame) -> pd.DataFrame:
    """Infer tyre stints based on pit stops and driver changes."""
    df = df.sort_values(["CAR_ID", "LAP_NUMBER"]).copy()

    # Core flags
    df["IS_PIT_LAP"] = detect_pit_laps(df)

    df["DRIVER_CHANGED"] = (
        df.groupby("CAR_ID")["DRIVER_NUMBER"].shift() != df["DRIVER_NUMBER"]
    )

    # Thresholds for pit times by class
    class_pit_time_thresholds = {
        "LMP2": 20,
        "LMP3": 15,
        "GTE": 10,
        "LMGTE": 10,
        "LMH": 25,
        "Hypercar": 25,
        "GTD": 12,
        "GTD Pro": 12,
    }

    # Determine if pit stop included tyres
    def pit_includes_tyres(row):
        threshold = class_pit_time_thresholds.get(row["CLASS"], 15)
        pit_time = row["PIT_TIME"]
        if pd.isna(pit_time):
            return False
        try:
            return float(pit_time) > threshold
        except Exception:
            return False

    df["PIT_INCLUDES_TYRES"] = df.apply(pit_includes_tyres, axis=1)

    # Identify tyre stint changes on pit laps with tyres changed or driver changed
    df["TYRE_STINT_CHANGE"] = df["IS_PIT_LAP"] & (
        df["PIT_INCLUDES_TYRES"] | df["DRIVER_CHANGED"].fillna(False)
    )

    # Assign tyre stint IDs incrementing on each change per car
    df["TYRE_STINT_ID"] = (
        df.groupby("CAR_ID")["TYRE_STINT_CHANGE"]
        .cumsum()
        .fillna(0)
        .astype(int)
    )

    # Parse lap times to numeric seconds for aggregation
    df["LAP_TIME_S"] = df["LAP_TIME"].apply(parse_lap_time_to_seconds)

    return df

def tyre_stint_pace_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize pace by tyre stint per car and class.
    """
    summary = (
        df.groupby(
            ["CAR_ID", "TEAM", "NUMBER", "CLASS", "TYRE_STINT_ID"],
            dropna=False,
        )
        .agg(
            laps=("LAP_NUMBER", "count"),
            avg_lap_s=("LAP_TIME_S", "mean"),
            min_lap_s=("LAP_TIME_S", "min"),
        )
        .reset_index()
    )

    # Convert numeric seconds back to timedelta for nicer display
    summary["avg_lap"] = pd.to_timedelta(summary["avg_lap_s"], unit="s")
    summary["min_lap"] = pd.to_timedelta(summary["min_lap_s"], unit="s")

    return summary

def show_tyre_analysis(df: pd.DataFrame):
    st.subheader("Tyre stint analysis")

    df = infer_tyre_stints(df)

    summary = tyre_stint_pace_summary(df)

    classes = sorted(summary["CLASS"].dropna().unique())

    if not classes:
        st.warning("No classes found in data.")
        return

    tabbed = st.tabs(classes)

    for tab, cls in zip(tabbed, classes):
        with tab:
            class_summary = summary[summary["CLASS"] == cls]

            if class_summary.empty:
                st.write(f"No data for class {cls}")
                continue

            st.write(f"Tyre stint pace summary for class: {cls}")

            # Show summary table with readable columns
            display_df = class_summary[
                ["TEAM", "NUMBER", "TYRE_STINT_ID", "laps", "avg_lap", "min_lap"]
            ].copy()

            # Format timedelta nicely
            display_df["avg_lap"] = display_df["avg_lap"].dt.total_seconds().map(
                lambda x: f"{int(x // 60)}:{x % 60:06.3f}" if pd.notna(x) else ""
            )
            display_df["min_lap"] = display_df["min_lap"].dt.total_seconds().map(
                lambda x: f"{int(x // 60)}:{x % 60:06.3f}" if pd.notna(x) else ""
            )

            st.dataframe(display_df, use_container_width=True)

            # Additional visualizations can be added here, e.g. lap time distributions, stint degradation, etc.

