import pandas as pd


def time_str_to_seconds(t):
    if pd.isna(t):
        return 0.0
    s = str(t).strip()
    if s == "" or s.lower() in {"nan", "na", "none"}:
        return 0.0
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
        return 0.0


def infer_tyre_stints(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["PIT_TIME_SECONDS"] = df["PIT_TIME"].apply(time_str_to_seconds)

    class_pit_time_thresholds = {
        "LMP2": 15,
        "LMP3": 15,
        "GTD": 12,
        "GTD Pro": 12,
    }

    def pit_includes_tyres(row):
        threshold = class_pit_time_thresholds.get(row["CLASS"], 15)
        return row["PIT_TIME_SECONDS"] > threshold

    df["PIT_LAP"] = (
        (df["CROSSING_FINISH_LINE_IN_PIT"] == 1)
        | df.apply(pit_includes_tyres, axis=1)
    )

    df["DRIVER_CHANGED"] = (
        df.groupby("CAR_ID")["DRIVER_NUMBER"].shift() != df["DRIVER_NUMBER"]
    ).fillna(False)

    df = df.sort_values(["CAR_ID", "LAP_NUMBER"])
    df["TYRE_STINT_ID"] = 0

    stint_id = 0
    prev_car = None

    for idx, row in df.iterrows():
        if row["CAR_ID"] != prev_car:
            stint_id = 0
        elif row["PIT_LAP"] and (row["DRIVER_CHANGED"] or row["PIT_TIME_SECONDS"] > 5):
            stint_id += 1
        df.at[idx, "TYRE_STINT_ID"] = stint_id
        prev_car = row["CAR_ID"]

    return df


def tyre_stint_pace_summary(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()

    work["LAP_TIME_SEC"] = work["LAP_TIME"].apply(time_str_to_seconds)
    work = work[work["LAP_TIME_SEC"].notna()]

    # Identify the pit lap that *started* each stint
    pit_events = (
        work[work["PIT_LAP"]]
        .sort_values(["CAR_ID", "LAP_NUMBER"])
        .groupby(["CAR_ID", "TYRE_STINT_ID"], as_index=False)
        .first()[["CAR_ID", "TYRE_STINT_ID", "LAP_NUMBER", "HOUR", "PIT_TIME_SECONDS"]]
        .rename(
            columns={
                "LAP_NUMBER": "STOP_LAP",
                "HOUR": "STOP_TIME",
            }
        )
    )

    pit_events["TOOK_TYRES"] = pit_events["PIT_TIME_SECONDS"] > 0
    pit_events["TYRES"] = pit_events["TOOK_TYRES"].apply(
        lambda x: "✅" if x else ""
    )

    summary = (
        work.groupby(
            [
                "CLASS",
                "TEAM",
                "CAR_ID",
                "TYRE_STINT_ID",
                "DRIVER_NUMBER",
            ],
            dropna=False,
        )
        .agg(
            laps=("LAP_NUMBER", "count"),
            avg_lap=("LAP_TIME_SEC", "mean"),
            min_lap=("LAP_TIME_SEC", "min"),
            max_lap=("LAP_TIME_SEC", "max"),
        )
        .reset_index()
    )

    summary = summary.merge(
        pit_events,
        on=["CAR_ID", "TYRE_STINT_ID"],
        how="left",
    )

    summary = summary.drop(columns=["PIT_TIME_SECONDS"], errors="ignore")

    return summary


def show_tyre_analysis(df: pd.DataFrame):
    import streamlit as st

    st.subheader("Tyre stint analysis")

    df = infer_tyre_stints(df)
    summary = tyre_stint_pace_summary(df)

    classes = sorted(summary["CLASS"].dropna().unique())
    if not classes:
        st.write("No tyre stint data available.")
        return

    tabs = st.tabs(classes)

    for tab, race_class in zip(tabs, classes):
        with tab:
            class_df = summary[summary["CLASS"] == race_class]

            teams = sorted(class_df["TEAM"].dropna().unique())
            selected_team = st.selectbox(
                f"Select team ({race_class})",
                ["All"] + teams,
                key=f"team_{race_class}",
            )

            if selected_team != "All":
                class_df = class_df[class_df["TEAM"] == selected_team]

            cars = sorted(class_df["CAR_ID"].dropna().unique())
            selected_car = st.selectbox(
                f"Select car ({race_class})",
                ["All"] + cars,
                key=f"car_{race_class}",
            )

            if selected_car != "All":
                class_df = class_df[class_df["CAR_ID"] == selected_car]

            if class_df.empty:
                st.write("No data for the selected filters.")
                continue

            display_cols = [
                "TEAM",
                "CAR_ID",
                "DRIVER_NUMBER",
                "TYRE_STINT_ID",
                "laps",
                "avg_lap",
                "min_lap",
                "max_lap",
                "STOP_LAP",
                "STOP_TIME",
                "TYRES",
            ]

            st.dataframe(
                class_df[display_cols],
                use_container_width=True,
            )
