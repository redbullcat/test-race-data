import pandas as pd

def parse_time_to_seconds(s):
    """
    Parse a time string (H:MM:SS.sss, M:SS.sss, or SS.sss) into total seconds (float).
    Returns 0.0 if input is invalid or missing.
    """
    if pd.isna(s):
        return 0.0
    s = str(s).strip()
    if s == "" or s.lower() in {"nan", "na", "none"}:
        return 0.0
    try:
        parts = s.split(':')
        parts = [float(p) for p in parts]
        if len(parts) == 3:
            h, m, sec = parts
            return h * 3600 + m * 60 + sec
        elif len(parts) == 2:
            m, sec = parts
            return m * 60 + sec
        else:
            return parts[0]
    except Exception:
        return 0.0

def parse_lap_time_to_seconds(s):
    """
    Similar to parse_time_to_seconds but specifically for LAP_TIME values.
    """
    return parse_time_to_seconds(s)

def detect_pit_laps(df: pd.DataFrame) -> pd.Series:
    """
    Identify pit laps using CROSSING_FINISH_LINE_IN_PIT flag or PIT_TIME threshold > 3 seconds.
    """
    pit_time_seconds = df["PIT_TIME"].apply(parse_time_to_seconds)
    return (
        (df["CROSSING_FINISH_LINE_IN_PIT"] == 1)
        | (pit_time_seconds > 3.0)
    )

def infer_tyre_stints(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds columns to df identifying tyre stints based on pit stops, driver changes, and class-specific pit time thresholds.
    """
    df = df.sort_values(["CAR_ID", "LAP_NUMBER"]).copy()

    # Detect pit laps
    df["IS_PIT_LAP"] = detect_pit_laps(df)

    # Detect driver changes between laps
    df["DRIVER_CHANGED"] = (
        df.groupby("CAR_ID")["DRIVER_NUMBER"].shift() != df["DRIVER_NUMBER"]
    )

    # Class-specific pit time thresholds (seconds)
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

    # Precompute PIT_TIME in seconds
    pit_time_seconds = df["PIT_TIME"].apply(parse_time_to_seconds)

    # Determine if pit includes tyre change based on threshold per class
    def pit_includes_tyres(row):
        threshold = class_pit_time_thresholds.get(row["CLASS"], 15)  # default 15s
        pit_time_sec = pit_time_seconds.loc[row.name]
        return pit_time_sec > threshold

    df["PIT_INCLUDES_TYRES"] = df.apply(pit_includes_tyres, axis=1)

    # Tyre stint change if pit lap and either pit includes tyres or driver changed
    df["TYRE_STINT_CHANGE"] = df["IS_PIT_LAP"] & (
        df["PIT_INCLUDES_TYRES"] | df["DRIVER_CHANGED"].fillna(False)
    )

    # Assign unique tyre stint IDs per CAR_ID
    df["TYRE_STINT_ID"] = (
        df.groupby("CAR_ID")["TYRE_STINT_CHANGE"].cumsum().fillna(0).astype(int)
    )

    # Add numeric LAP_TIME column for analysis
    df["LAP_TIME_S"] = df["LAP_TIME"].apply(parse_lap_time_to_seconds)

    return df

def tyre_stint_pace_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarizes pace statistics by tyre stint and class.
    Expects df with 'TYRE_STINT_ID' and numeric 'LAP_TIME_S'.
    """
    work = df.copy()

    # Require valid lap times
    work = work[work["LAP_TIME_S"].notna()]

    summary = (
        work.groupby(
            [
                "CAR_ID",
                "TEAM",
                "CLASS",
                "NUMBER",
                "TYRE_STINT_ID",
            ],
            dropna=False,
        )
        .agg(
            laps=("LAP_NUMBER", "count"),
            avg_lap=("LAP_TIME_S", "mean"),
            min_lap=("LAP_TIME_S", "min"),
            max_lap=("LAP_TIME_S", "max"),
        )
        .reset_index()
    )

    return summary

def show_tyre_analysis(df: pd.DataFrame):
    import streamlit as st

    st.subheader("Tyre stint analysis")

    df = infer_tyre_stints(df)
    summary = tyre_stint_pace_summary(df)

    classes = sorted(summary["CLASS"].dropna().unique())

    tab_dict = {}

    if classes:
        tabs = st.tabs(classes)
        for tab, race_class in zip(tabs, classes):
            with tab:
                class_df = summary[summary["CLASS"] == race_class]
                if not class_df.empty:
                    st.write(f"Tyre stint pace summary for class {race_class}")
                    st.dataframe(
                        class_df.sort_values(["CAR_ID", "TYRE_STINT_ID"]),
                        use_container_width=True,
                        hide_index=True,
                    )
    else:
        st.info("No tyre stint data available for analysis.")
