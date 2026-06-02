"""results_table.py — Race results table with gaps, intervals, fastest laps, and pit stops."""

import pandas as pd
import streamlit as st

from utils import seconds_to_laptime, lap_to_seconds, chart_export_buttons


@st.cache_data(show_spinner=False)
def _build_results(df: pd.DataFrame, selected_class: str) -> pd.DataFrame:
    class_df = df[df["CLASS"] == selected_class].copy()
    class_df = class_df.dropna(subset=["ELAPSED_SECONDS", "LAP_NUMBER"])

    # Drivers per car
    driver_map = (
        class_df.groupby("NUMBER")["DRIVER_NAME"]
        .unique()
        .apply(lambda x: " / ".join(sorted(str(d) for d in x)))
        .to_dict()
    )

    # Final classification: most laps, then earliest elapsed time
    idx = class_df.groupby("NUMBER")["LAP_NUMBER"].idxmax()
    last_laps = (
        class_df.loc[idx]
        .reset_index(drop=True)
        .sort_values(["LAP_NUMBER", "ELAPSED_SECONDS"], ascending=[False, True])
        .reset_index(drop=True)
    )
    last_laps["DRIVERS"] = last_laps["NUMBER"].map(driver_map)

    leader_lap = last_laps.loc[0, "LAP_NUMBER"]
    leader_time = last_laps.loc[0, "ELAPSED_SECONDS"]

    # Gap to leader
    def _gap_to_leader(row):
        laps_down = leader_lap - row["LAP_NUMBER"]
        if laps_down >= 1:
            return f"{int(laps_down)} lap{'s' if laps_down > 1 else ''}"
        return f"{row['ELAPSED_SECONDS'] - leader_time:.3f}"

    last_laps["Gap"] = last_laps.apply(_gap_to_leader, axis=1)

    # Interval to car ahead
    intervals = ["–"]
    for i in range(1, len(last_laps)):
        prev = last_laps.iloc[i - 1]
        curr = last_laps.iloc[i]
        laps_down = prev["LAP_NUMBER"] - curr["LAP_NUMBER"]
        if laps_down >= 1:
            intervals.append(f"{int(laps_down)} lap{'s' if laps_down > 1 else ''}")
        else:
            intervals.append(f"{curr['ELAPSED_SECONDS'] - prev['ELAPSED_SECONDS']:.3f} s")
    last_laps["Interval"] = intervals

    # Fastest lap per car
    fastest = (
        class_df.dropna(subset=["LAP_TIME_SECONDS"])
        .sort_values("LAP_TIME_SECONDS")
        .groupby("NUMBER")
        .first()
        .reset_index()
    )
    fastest["FASTEST_LAP"] = fastest.apply(
        lambda r: f"{seconds_to_laptime(r['LAP_TIME_SECONDS'])} ({r['DRIVER_NAME']})", axis=1
    )

    last_laps = last_laps.merge(
        fastest[["NUMBER", "FASTEST_LAP", "LAP_TIME_SECONDS"]],
        on="NUMBER", how="left", suffixes=("", "_fastest"),
    )

    # Pit stop count
    pit_counts = (
        class_df[class_df.get("CROSSING_FINISH_LINE_IN_PIT", pd.Series(dtype=str)) == "B"]
        .groupby("NUMBER")
        .size()
        .rename("Pits")
    ) if "CROSSING_FINISH_LINE_IN_PIT" in class_df.columns else pd.Series(dtype=int)

    last_laps = last_laps.merge(pit_counts, on="NUMBER", how="left")
    last_laps["Pits"] = last_laps["Pits"].fillna(0).astype(int)

    return last_laps, fastest["LAP_TIME_SECONDS"].min()


def show_results_table(df, team_colors):
    st.subheader("Race Results")

    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select class:", classes, key="results_class")
    if not selected_class:
        return

    last_laps, fastest_class_time = _build_results(df, selected_class)

    display_df = last_laps[
        ["NUMBER", "TEAM", "DRIVERS", "LAP_NUMBER", "ELAPSED", "Interval", "Gap", "FASTEST_LAP", "Pits"]
    ].rename(columns={
        "NUMBER": "Car",
        "TEAM": "Team",
        "DRIVERS": "Drivers",
        "LAP_NUMBER": "Laps",
        "ELAPSED": "Total Time",
        "FASTEST_LAP": "Fastest Lap",
    })
    display_df.insert(0, "Pos", range(1, len(display_df) + 1))
    display_df = display_df.set_index("Pos")

    st.dataframe(display_df, width='stretch')
    chart_export_buttons(df=display_df, filename="race_results")
