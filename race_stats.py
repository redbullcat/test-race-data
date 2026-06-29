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
        overall_leader = lap_df.iloc[0]
        flag = overall_leader.get("FLAG_AT_FL") if "FLAG_AT_FL" in lap_df.columns else None

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
    col1.metric("Lead changes (overall race)", lead_changes)
    col2.metric("Cars that led overall", cars_led)
    col3.metric("Total race laps", total_laps)
    st.caption(
        "Lead changes (overall race) counts how many times the single race-wide leader changed "
        "across all classes combined. Per-class counts below are independent — they will not add up to this figure."
    )

    # Lead changes by class
    st.markdown("**Lead changes by class**")
    for cls, cdf in class_df.groupby("CLASS"):
        changes = max((cdf["CAR_ID"] != cdf["CAR_ID"].shift()).sum() - 1, 0)
        st.write(f"- **{cls}**: {changes}")

    # Flag laps
    if "FLAG_AT_FL" in overall_df.columns:
        st.markdown("**Laps by flag condition**")
        flag_counts = overall_df["FLAG_AT_FL"].fillna("GREEN").replace("GF", "GREEN").value_counts()
        total_laps_flag = flag_counts.sum()
        # Join lap times from source df — overall_df only carries leader identity, not lap times
        if "LAP_TIME_SECONDS" in df.columns and "CAR_ID" in df.columns:
            lt_lookup = df.drop_duplicates(["CAR_ID", "LAP_NUMBER"])[["CAR_ID", "LAP_NUMBER", "LAP_TIME_SECONDS", "FLAG_AT_FL"]]
            overall_with_lt = overall_df.merge(lt_lookup, on=["CAR_ID", "LAP_NUMBER"], how="left", suffixes=("", "_src"))
            overall_with_lt["_flag"] = overall_with_lt["FLAG_AT_FL"].fillna("GREEN").replace("GF", "GREEN")
            flag_mean_secs = overall_with_lt.groupby("_flag")["LAP_TIME_SECONDS"].mean()
        else:
            flag_mean_secs = {}
        accounted_secs = 0.0
        for flag, count in flag_counts.items():
            pct = count / total_laps_flag * 100
            avg_s = flag_mean_secs.get(flag)
            if avg_s:
                total_s = avg_s * count
                accounted_secs += total_s
                h = int(total_s // 3600)
                m = int((total_s % 3600) // 60)
                time_str = f"{h}h {m:02d}m" if h else f"{m}m"
                st.write(f"- **{flag}**: {count} laps ({pct:.0f}%, ~{time_str})")
            else:
                st.write(f"- **{flag}**: {count} laps ({pct:.0f}%)")

        # Derive actual race duration from the maximum elapsed time in the data
        def _elapsed_to_secs(s):
            try:
                parts = str(s).split(":")
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                if len(parts) == 2:
                    return int(parts[0]) * 60 + float(parts[1])
            except Exception:
                pass
            return None

        # overall_df doesn't carry ELAPSED — pull it from the source df
        if "ELAPSED" in df.columns and "CAR_ID" in df.columns:
            elapsed_lookup = df.drop_duplicates(["CAR_ID", "LAP_NUMBER"])[["CAR_ID", "LAP_NUMBER", "ELAPSED"]]
            overall_with_elapsed = overall_df.merge(elapsed_lookup, on=["CAR_ID", "LAP_NUMBER"], how="left")
            elapsed_secs_series = overall_with_elapsed["ELAPSED"].map(_elapsed_to_secs).dropna()
        else:
            elapsed_secs_series = pd.Series(dtype=float)
        race_dur_secs = elapsed_secs_series.max() if not elapsed_secs_series.empty else accounted_secs
        # Round up to the nearest hour for display (e.g. 23:58 → "24h")
        race_dur_h = round(race_dur_secs / 3600)
        gap_secs = max(race_dur_h * 3600 - accounted_secs, 0)
        acc_h = int(accounted_secs // 3600)
        acc_m = int((accounted_secs % 3600) // 60)
        gap_m = int(gap_secs // 60)
        gap_s = int(gap_secs % 60)
        st.caption(
            f"Total accounted: ~{acc_h}h {acc_m:02d}m of {race_dur_h}h 00m — "
            f"the remaining ~{gap_m}m {gap_s:02d}s is the leader's final incomplete lap "
            f"(still circulating when the chequered flag fell)."
        )

    # --- Fastest laps ---
    if "LAP_TIME_SECONDS" in df.columns and "LAP_NUMBER" in df.columns:
        st.markdown("## Fastest Laps")

        def _fmt_laptime(s):
            try:
                m = int(s // 60)
                sec = s % 60
                return f"{m}:{sec:06.3f}"
            except Exception:
                return ""

        fastest_per_driver = (
            df.dropna(subset=["LAP_TIME_SECONDS"])
            .sort_values("LAP_TIME_SECONDS")
            .groupby(["NUMBER", "DRIVER_NAME"], as_index=False)
            .first()[["NUMBER", "CLASS", "DRIVER_NAME", "LAP_TIME_SECONDS", "LAP_NUMBER"]]
        )
        fastest_per_driver["Fastest Lap"] = fastest_per_driver["LAP_TIME_SECONDS"].apply(_fmt_laptime)
        fastest_per_driver["Lap"] = fastest_per_driver["LAP_NUMBER"].astype(int)
        fastest_per_driver = fastest_per_driver.sort_values("LAP_TIME_SECONDS")

        classes = sorted(fastest_per_driver["CLASS"].dropna().unique())
        tabs = st.tabs(classes)
        for tab, cls in zip(tabs, classes):
            with tab:
                cdf = fastest_per_driver[fastest_per_driver["CLASS"] == cls].copy()
                cdf.insert(0, "Rank", range(1, len(cdf) + 1))
                _fl_display = cdf.rename(columns={
                    "NUMBER": "Car", "DRIVER_NAME": "Driver",
                })[["Rank", "Car", "Driver", "Fastest Lap", "Lap"]].set_index("Rank")
                st.dataframe(_fl_display, width="stretch")
                chart_export_buttons(df=_fl_display, filename=f"fastest_laps_{cls}")

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
