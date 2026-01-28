import pandas as pd
import streamlit as st


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def parse_pit_time_seconds(val) -> float:
    """
    Convert PIT_TIME to seconds.

    Accepts:
      - mm:ss.xxx
      - ss.xxx
      - numeric
    Returns 0.0 if invalid or missing.
    """
    if pd.isna(val):
        return 0.0

    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if s == "" or s.lower() in {"nan", "na", "none"}:
        return 0.0

    try:
        # mm:ss.xxx
        if ":" in s:
            mins, rest = s.split(":", 1)
            return int(mins) * 60 + float(rest)
        # ss.xxx
        return float(s)
    except ValueError:
        return 0.0


def detect_pit_laps(df: pd.DataFrame) -> pd.Series:
    """
    Identify pit laps using multiple signals.
    """
    return (
        (df["CROSSING_FINISH_LINE_IN_PIT"] == 1)
        | (df["PIT_TIME_SECONDS"] > 0)
    )


# ------------------------------------------------------------
# Tyre stint inference
# ------------------------------------------------------------

def infer_tyre_stints(df: pd.DataFrame) -> pd.DataFrame:
    """
    Infer tyre stints using pit laps, driver changes and pit duration.
    """
    df = df.copy()

    # Ensure numeric pit time exists (parsed once)
    if "PIT_TIME_SECONDS" not in df.columns:
        df["PIT_TIME_SECONDS"] = df["PIT_TIME"].apply(parse_pit_time_seconds)

    # Stable car identifier
    if "CAR_ID" not in df.columns:
        df["CAR_ID"] = df["NUMBER"].astype(str) + "_" + df["TEAM"].astype(str)

    df = df.sort_values(["CAR_ID", "LAP_NUMBER"])

    # Core pit / service flags
    df["IS_PIT_LAP"] = detect_pit_laps(df)

    df["DRIVER_CHANGED"] = (
        df.groupby("CAR_ID")["DRIVER_NUMBER"]
        .shift()
        .ne(df["DRIVER_NUMBER"])
    )

    # Define a "full service" heuristic:
    # - driver change OR long pit stop
    df["FULL_SERVICE"] = (
        df["DRIVER_CHANGED"]
        | (df["PIT_TIME_SECONDS"] >= 30)  # conservative global default
    )

    # A new tyre stint starts after a full service
    df["NEW_TYRES"] = df["FULL_SERVICE"].shift().fillna(False)

    # Tyre stint ID per car
    df["TYRE_STINT_ID"] = (
        df.groupby("CAR_ID")["NEW_TYRES"]
        .cumsum()
        .astype(int)
    )

    return df


# ------------------------------------------------------------
# Analysis
# ------------------------------------------------------------

def tyre_stint_pace_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarise pace by tyre stint.
    """
    work = df.copy()

    # Require valid lap times
    work = work[work["LAP_TIME"].notna()]

    summary = (
        work.groupby(
            [
                "CLASS",
                "CAR_ID",
                "NUMBER",
                "TEAM",
                "DRIVER_NAME",
                "TYRE_STINT_ID",
            ],
            dropna=False,
        )
        .agg(
            laps=("LAP_NUMBER", "count"),
            avg_lap=("LAP_TIME", "mean"),
            min_lap=("LAP_TIME", "min"),
            max_lap=("LAP_TIME", "max"),
        )
        .reset_index()
    )

    return summary


# ------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------

def show_tyre_analysis(df: pd.DataFrame):
    st.subheader("Tyre stint analysis")

    df = infer_tyre_stints(df)
    summary = tyre_stint_pace_summary(df)

    classes = sorted(summary["CLASS"].dropna().unique())

    for cls in classes:
        st.markdown(f"### {cls}")

        cls_df = summary[summary["CLASS"] == cls].copy()
        cls_df = cls_df.sort_values(
            ["NUMBER", "TYRE_STINT_ID"]
        )

        st.dataframe(
            cls_df[
                [
                    "NUMBER",
                    "TEAM",
                    "DRIVER_NAME",
                    "TYRE_STINT_ID",
                    "laps",
                    "avg_lap",
                    "min_lap",
                    "max_lap",
                ]
            ],
            use_container_width=True,
        )
