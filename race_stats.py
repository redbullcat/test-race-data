"""race_stats.py — Race statistics: lead changes, laps led, flag conditions."""

from datetime import datetime

import pandas as pd
import streamlit as st

from utils import parse_hour_with_rollover, laps_to_ranges


@st.cache_data(show_spinner=False)
def _compute_leaders(df: pd.DataFrame, race_start_date) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["HOUR_DT"] = parse_hour_with_rollover(df, race_start_date, group_col="CAR_ID")
    df = df.sort_values(["LAP_NUMBER", "HOUR_DT"])

    overall_leaders = []
    class_leaders = []
    laps = sorted(df["LAP_NUMBER"].dropna().unique())
    prev_overall_car = None

    pit_col = "CROSSING_FINISH_LINE_IN_PIT" if "CROSSING_FINISH_LINE_IN_PIT" in df.columns else None

    for lap in laps:
        lap_df = df[df["LAP_NUMBER"] == lap]

        if pit_col:
            eligible = lap_df[lap_df[pit_col] != "B"]
            if eligible.empty:
                eligible = lap_df
        else:
            eligible = lap_df

        flag_vals = lap_df["FLAG_AT_FL"].dropna().unique() if "FLAG_AT_FL" in lap_df.columns else []
        flag = flag_vals[0] if len(flag_vals) == 1 else None

        if flag == "FCY" and prev_overall_car is not None:
            prev_rows = eligible[eligible["CAR_ID"] == prev_overall_car]
            overall_leader = prev_rows.iloc[0] if not prev_rows.empty else eligible.iloc[0]
        else:
            overall_leader = eligible.iloc[0]

        prev_overall_car = overall_leader["CAR_ID"]
        overall_leaders.append({
            "LAP_NUMBER": lap,
            "CAR_ID": overall_leader["CAR_ID"],
            "NUMBER": overall_leader["NUMBER"],
            "DRIVER_NAME": overall_leader.get("DRIVER_NAME", ""),
            "CLASS": overall_leader.get("CLASS", ""),
            "FLAG_AT_FL": flag,
        })

        for cls, cls_df in eligible.groupby("CLASS"):
            first = cls_df.iloc[0]
            class_leaders.append({
                "LAP_NUMBER": lap,
                "CLASS": cls,
                "CAR_ID": first["CAR_ID"],
                "NUMBER": first["NUMBER"],
                "DRIVER_NAME": first.get("DRIVER_NAME", ""),
            })

    return pd.DataFrame(overall_leaders), pd.DataFrame(class_leaders)


def show_race_stats(df, race_start_date):
    st.subheader("Race Statistics")

    overall_df, class_df = _compute_leaders(df, race_start_date)
    if overall_df.empty:
        st.warning("Could not compute race statistics.")
        return

    # --- Top metrics ---
    lead_changes = max((overall_df["CAR_ID"] != overall_df["CAR_ID"].shift()).sum() - 1, 0)
    cars_led = overall_df["CAR_ID"].nunique()
    total_laps = overall_df["LAP_NUMBER"].nunique()

    col1, col2, col3 = st.columns(3)
    col1.metric("Overall lead changes", lead_changes)
    col2.metric("Cars that led overall", cars_led)
    col3.metric("Total race laps", total_laps)

    # Lead changes by class
    st.markdown("**Lead changes by class**")
    for cls, cdf in class_df.groupby("CLASS"):
        changes = max((cdf["CAR_ID"] != cdf["CAR_ID"].shift()).sum() - 1, 0)
        st.write(f"- **{cls}**: {changes}")

    # Flag laps
    if "FLAG_AT_FL" in overall_df.columns:
        st.markdown("**Laps by flag condition**")
        for flag, count in overall_df["FLAG_AT_FL"].fillna("GREEN").value_counts().items():
            st.write(f"- **{flag}**: {count} laps")

    # Longest lead stint
    overall_df["change"] = overall_df["CAR_ID"] != overall_df["CAR_ID"].shift()
    overall_df["stint_id"] = overall_df["change"].cumsum()
    stints = (
        overall_df.groupby(["stint_id", "CAR_ID", "NUMBER"])
        .size()
        .reset_index(name="laps_led")
        .sort_values("laps_led", ascending=False)
    )
    if not stints.empty:
        top = stints.iloc[0]
        st.markdown(f"**Longest uninterrupted overall lead:** Car **{top['NUMBER']}** — **{int(top['laps_led'])} laps**")

    # --- Laps led tables ---
    st.markdown("## Laps Led by Class")
    classes = sorted(class_df["CLASS"].dropna().unique())
    tabs = st.tabs(classes)

    for tab, cls in zip(tabs, classes):
        with tab:
            cdf = class_df[class_df["CLASS"] == cls]
            total = cdf["LAP_NUMBER"].nunique()

            car_stats = (
                cdf.groupby(["CAR_ID", "NUMBER"])
                .agg(laps_led=("LAP_NUMBER", "count"), laps_range=("LAP_NUMBER", lambda x: laps_to_ranges(x.tolist())))
                .reset_index()
            )
            car_stats["% led"] = (car_stats["laps_led"] / total * 100).round(1)
            car_stats = car_stats.sort_values("laps_led", ascending=False)

            st.markdown("**By car**")
            st.dataframe(
                car_stats.rename(columns={"NUMBER": "Car", "laps_led": "Laps Led", "laps_range": "Lap Ranges", "% led": "% of Race"})[
                    ["Car", "Laps Led", "Lap Ranges", "% of Race"]
                ],
                use_container_width=True,
                hide_index=True,
            )

            driver_stats = (
                cdf.groupby(["CAR_ID", "NUMBER", "DRIVER_NAME"])
                .agg(laps_led=("LAP_NUMBER", "count"), laps_range=("LAP_NUMBER", lambda x: laps_to_ranges(x.tolist())))
                .reset_index()
            )
            driver_stats["% led"] = (driver_stats["laps_led"] / total * 100).round(1)
            driver_stats = driver_stats.sort_values("laps_led", ascending=False)

            st.markdown("**By driver**")
            st.dataframe(
                driver_stats.rename(columns={"NUMBER": "Car", "DRIVER_NAME": "Driver", "laps_led": "Laps Led", "laps_range": "Lap Ranges", "% led": "% of Race"})[
                    ["Car", "Driver", "Laps Led", "Lap Ranges", "% of Race"]
                ],
                use_container_width=True,
                hide_index=True,
            )
