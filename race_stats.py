"""race_stats.py — Race statistics: lead changes, laps led, flag conditions."""

from datetime import datetime

import pandas as pd
import streamlit as st

from utils import parse_hour_with_rollover, laps_to_ranges, chart_export_buttons


@st.cache_data(show_spinner=False)
def _compute_leaders(df: pd.DataFrame, race_start_date) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["HOUR_DT"] = parse_hour_with_rollover(df, race_start_date, group_col="CAR_ID")
    df = df.sort_values(["LAP_NUMBER", "HOUR_DT"])

    overall_leaders = []
    class_leaders = []
    laps = sorted(df["LAP_NUMBER"].dropna().unique())

    for lap in laps:
        lap_df = df[df["LAP_NUMBER"] == lap]

        # DO NOT filter out pit laps — a car that pits still crossed the line first
        # if it was leading. CROSSING_FINISH_LINE_IN_PIT = "B" means the car pitted
        # AFTER crossing, not that it didn't cross. Sorting by HOUR_DT (crossing time)
        # is the correct and only criterion for determining the lap leader.
        flag_vals = lap_df["FLAG_AT_FL"].dropna().unique() if "FLAG_AT_FL" in lap_df.columns else []
        flag = flag_vals[0] if len(flag_vals) == 1 else None

        overall_leader = lap_df.iloc[0]

        overall_leaders.append({
            "LAP_NUMBER": lap,
            "CAR_ID": overall_leader["CAR_ID"],
            "NUMBER": overall_leader["NUMBER"],
            "DRIVER_NAME": overall_leader.get("DRIVER_NAME", ""),
            "CLASS": overall_leader.get("CLASS", ""),
            "FLAG_AT_FL": flag,
        })

        for cls, cls_df in lap_df.groupby("CLASS"):
            first = cls_df.iloc[0]
            class_leaders.append({
                "LAP_NUMBER": lap,
                "CLASS": cls,
                "CAR_ID": first["CAR_ID"],
                "NUMBER": first["NUMBER"],
                "DRIVER_NAME": first.get("DRIVER_NAME", ""),
            })

    return pd.DataFrame(overall_leaders), pd.DataFrame(class_leaders)


def show_race_stats(df, race_start_date, series: str = "", df_full=None):
    st.subheader("Race Statistics")

    # df_full is the unfiltered dataframe (all classes). Falls back to df if not provided.
    if df_full is None:
        df_full = df

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

    # --- Overall laps led (GTWC only) ---
    if series == "GTWC":
        st.markdown("## Overall Laps Led")
        st.caption("All cars treated as one group, regardless of driver class — mirrors the official lap chart.")

        # Use the unfiltered dataframe so all classes contribute to the overall leader each lap
        all_overall_df, _ = _compute_leaders(df_full, race_start_date)
        total_overall = all_overall_df["LAP_NUMBER"].nunique()

        overall_car_stats = (
            all_overall_df.groupby(["CAR_ID", "NUMBER"])
            .agg(laps_led=("LAP_NUMBER", "count"), laps_range=("LAP_NUMBER", lambda x: laps_to_ranges(x.tolist())))
            .reset_index()
        )
        overall_car_stats["% of Race"] = (overall_car_stats["laps_led"] / total_overall * 100).round(1)
        overall_car_stats = overall_car_stats.sort_values("laps_led", ascending=False)

        # Attach class and team for context
        car_meta = (
            df_full[["NUMBER", "CLASS", "TEAM", "MANUFACTURER"]]
            .drop_duplicates("NUMBER")
        )
        overall_car_stats = overall_car_stats.merge(car_meta, on="NUMBER", how="left")

        _overall_car_display = overall_car_stats.rename(columns={
            "NUMBER": "Car", "laps_led": "Laps Led", "laps_range": "Lap Ranges",
            "CLASS": "Class", "TEAM": "Team", "MANUFACTURER": "Manufacturer",
        })[["Car", "Class", "Team", "Manufacturer", "Laps Led", "Lap Ranges", "% of Race"]]

        st.markdown("**By car**")
        st.dataframe(_overall_car_display, width="stretch", hide_index=True)
        chart_export_buttons(df=_overall_car_display, filename="overall_laps_led_by_car")

        overall_driver_stats = (
            all_overall_df.groupby(["CAR_ID", "NUMBER", "DRIVER_NAME"])
            .agg(laps_led=("LAP_NUMBER", "count"), laps_range=("LAP_NUMBER", lambda x: laps_to_ranges(x.tolist())))
            .reset_index()
        )
        overall_driver_stats["% of Race"] = (overall_driver_stats["laps_led"] / total_overall * 100).round(1)
        overall_driver_stats = overall_driver_stats.sort_values("laps_led", ascending=False)
        overall_driver_stats = overall_driver_stats.merge(car_meta[["NUMBER", "CLASS"]], on="NUMBER", how="left")

        _overall_driver_display = overall_driver_stats.rename(columns={
            "NUMBER": "Car", "DRIVER_NAME": "Driver", "laps_led": "Laps Led",
            "laps_range": "Lap Ranges", "CLASS": "Class",
        })[["Car", "Class", "Driver", "Laps Led", "Lap Ranges", "% of Race"]]

        st.markdown("**By driver**")
        st.dataframe(_overall_driver_display, width="stretch", hide_index=True)
        chart_export_buttons(df=_overall_driver_display, filename="overall_laps_led_by_driver")

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
            _car_stats_display = car_stats.rename(columns={"NUMBER": "Car", "laps_led": "Laps Led", "laps_range": "Lap Ranges", "% led": "% of Race"})[
                    ["Car", "Laps Led", "Lap Ranges", "% of Race"]
                ]
            st.dataframe(
                _car_stats_display,
                width='stretch',
                hide_index=True,
            )
            chart_export_buttons(df=_car_stats_display, filename="laps_led_by_car")

            driver_stats = (
                cdf.groupby(["CAR_ID", "NUMBER", "DRIVER_NAME"])
                .agg(laps_led=("LAP_NUMBER", "count"), laps_range=("LAP_NUMBER", lambda x: laps_to_ranges(x.tolist())))
                .reset_index()
            )
            driver_stats["% led"] = (driver_stats["laps_led"] / total * 100).round(1)
            driver_stats = driver_stats.sort_values("laps_led", ascending=False)

            st.markdown("**By driver**")
            _driver_stats_display = driver_stats.rename(columns={"NUMBER": "Car", "DRIVER_NAME": "Driver", "laps_led": "Laps Led", "laps_range": "Lap Ranges", "% led": "% of Race"})[
                    ["Car", "Driver", "Laps Led", "Lap Ranges", "% of Race"]
                ]
            st.dataframe(
                _driver_stats_display,
                width='stretch',
                hide_index=True,
            )
            chart_export_buttons(df=_driver_stats_display, filename="laps_led_by_driver")
