import pandas as pd
import streamlit as st
from typing import Dict

# =========================
# Helpers
# =========================

def parse_lap_time(series: pd.Series) -> pd.Series:
    """Parse LAP_TIME to timedelta."""
    return pd.to_timedelta(series, errors="coerce")


def detect_pit_laps(df: pd.DataFrame) -> pd.Series:
    """Identify pit laps using multiple signals."""
    return (
        (df["CROSSING_FINISH_LINE_IN_PIT"] == 1)
        | (df["PIT_TIME"].fillna(0) > 0)
    )


# =========================
# Class-specific pit thresholds
# =========================

def compute_class_pit_thresholds(df: pd.DataFrame) -> Dict[str, float]:
    """
    Compute class-specific PIT_TIME thresholds using IQR method
    to separate fuel-only stops from tyre changes.
    """
    pit_df = df[df["IS_PIT_LAP"] & df["PIT_TIME"].notna()]
    thresholds = {}

    for cls, g in pit_df.groupby("CLASS"):
        q1 = g["PIT_TIME"].quantile(0.25)
        q3 = g["PIT_TIME"].quantile(0.75)
        iqr = q3 - q1
        thresholds[cls] = q3 + 1.5 * iqr

    return thresholds


# =========================
# Tyre stint inference
# =========================

def infer_tyre_stints(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["CAR_ID", "LAP_NUMBER"]).copy()

    # Core flags
    df["IS_PIT_LAP"] = detect_pit_laps(df)

    df["DRIVER_CHANGED"] = (
        df.groupby("CAR_ID")["DRIVER_NUMBER"].shift()
        != df["DRIVER_NUMBER"]
    )

    thresholds = compute_class_pit_thresholds(df)

    df["LONG_PIT"] = df.apply(
        lambda r: r["PIT_TIME"] >= thresholds.get(r["CLASS"], float("inf")),
        axis=1
    )

    # Tyre reset logic
    df["TYRE_RESET"] = df["DRIVER_CHANGED"] | df["LONG_PIT"]

    # Tyre stint ID (per car)
    df["TYRE_STINT_ID"] = (
        df.groupby("CAR_ID")["TYRE_RESET"].cumsum()
    )

    # Fuel-only stop inside same tyre stint
    df["FUEL_ONLY_STOP"] = df["IS_PIT_LAP"] & ~df["TYRE_RESET"]

    # Segment within tyre stint (1 = first run, 2 = double-stint, etc.)
    df["TYRE_STINT_SEGMENT"] = (
        df.groupby(["CAR_ID", "TYRE_STINT_ID"])["FUEL_ONLY_STOP"]
          .cumsum()
          .add(1)
    )

    # Valid pace laps: exclude pit-in and out-laps
    df["VALID_PACE_LAP"] = (
        ~df["IS_PIT_LAP"]
        & ~df.groupby("CAR_ID")["IS_PIT_LAP"].shift(-1).fillna(False)
    )

    df["LAP_TIME"] = parse_lap_time(df["LAP_TIME"])

    return df


# =========================
# Aggregation
# =========================

def tyre_stint_pace_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare average lap time between segments on same tyre set.
    """
    pace_df = df[df["VALID_PACE_LAP"] & df["LAP_TIME"].notna()]

    summary = (
        pace_df
        .groupby([
            "CLASS",
            "CAR_ID",
            "NUMBER",
            "TYRE_STINT_ID",
            "TYRE_STINT_SEGMENT",
        ])
        .agg(
            laps=("LAP_TIME", "count"),
            avg_lap_time=("LAP_TIME", "mean"),
        )
        .reset_index()
    )

    return summary


# =========================
# Streamlit UI
# =========================

def show_tyre_analysis(df: pd.DataFrame):
    st.subheader("Tyre stint analysis")

    df = infer_tyre_stints(df)
    summary = tyre_stint_pace_summary(df)

    classes = sorted(summary["CLASS"].dropna().unique())
    tabs = st.tabs(classes)

    for tab, cls in zip(tabs, classes):
        with tab:
            cls_df = summary[summary["CLASS"] == cls]

            st.markdown("### Tyre stint pace comparison")

            pivot = (
                cls_df
                .pivot_table(
                    index=["CAR_ID", "NUMBER", "TYRE_STINT_ID"],
                    columns="TYRE_STINT_SEGMENT",
                    values="avg_lap_time"
                )
                .reset_index()
            )

            if 1 in pivot.columns and 2 in pivot.columns:
                pivot["Δ Segment 2 - Segment 1"] = pivot[2] - pivot[1]

            st.dataframe(
                pivot,
                use_container_width=True,
                hide_index=True
            )

    return df
