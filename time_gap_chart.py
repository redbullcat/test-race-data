import pandas as pd
import streamlit as st

def show_time_gap_chart_debug(df, team_colors):
    st.subheader("⏱️ Time Gap Comparison - Debug Output with Drivers, Gaps & Fastest Laps")

    # --- Class selection ---
    available_classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select Class for Debug", available_classes)
    class_df = df[df["CLASS"] == selected_class].copy()

    # --- Convert ELAPSED time string to total seconds ---
    def to_seconds(t):
        if pd.isna(t):
            return None
        t = str(t).strip()
        parts = t.split(':')
        try:
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
        except Exception:
            return None
        return None

    # Convert LAP_TIME for fastest lap detection
    def lap_to_seconds(lap):
        if pd.isna(lap):
            return None
        lap = str(lap).strip()
        parts = lap.split(':')
        try:
            if len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
        except Exception:
            return None
        return None

    def seconds_to_lap_format(seconds):
        """Convert seconds to m:ss.sss format"""
        if pd.isna(seconds):
            return None
        m = int(seconds // 60)
        s = seconds % 60
        return f"{m}:{s:06.3f}"

    # --- Preprocessing ---
    class_df["ELAPSED_SECONDS"] = class_df["ELAPSED"].apply(to_seconds)
    class_df["LAP_NUMBER"] = pd.to_numeric(class_df["LAP_NUMBER"], errors="coerce")
    class_df["LAP_TIME_SECONDS"] = class_df["LAP_TIME"].apply(lap_to_seconds)
    class_df = class_df.dropna(subset=["ELAPSED_SECONDS", "LAP_NUMBER"])

    # --- Create driver list per car ---
    driver_map = (
        class_df.groupby("NUMBER")["DRIVER_NAME"]
        .unique()
        .apply(lambda x: " / ".join(sorted(x)))
        .to_dict()
    )

    # --- Get last lap row per car (total race time) ---
    last_lap_times = (
        class_df.groupby("NUMBER")
        .apply(lambda x: x.loc[x["LAP_NUMBER"].idxmax()])
        .reset_index(drop=True)
    )

    # Add driver names
    last_lap_times["DRIVERS"] = last_lap_times["NUMBER"].map(driver_map)

    # Convert ELAPSED to seconds for sorting
    last_lap_times["ELAPSED_SECONDS"] = last_lap_times["ELAPSED"].apply(to_seconds)

    # Sort by laps desc, then elapsed time asc
    last_lap_times = last_lap_times.sort_values(
        by=["LAP_NUMBER", "ELAPSED_SECONDS"], ascending=[False, True]
    ).reset_index(drop=True)

    # Leader info
    leader_lap = last_lap_times.loc[0, "LAP_NUMBER"]
    leader_time = last_lap_times.loc[0, "ELAPSED_SECONDS"]

    # --- Interval and Gap to Leader calculations ---
    def calculate_interval(row):
        laps_down = leader_lap - row["LAP_NUMBER"]
        if laps_down >= 1:
            return f"{int(laps_down)} lap{'s' if laps_down > 1 else ''}"
        else:
            gap = row["ELAPSED_SECONDS"] - leader_time
            return f"{gap:.3f} s"

    def calculate_gap_to_leader(row):
        laps_down = leader_lap - row["LAP_NUMBER"]
        if laps_down >= 1:
            return None
        else:
            return row["ELAPSED_SECONDS"] - leader_time

    last_lap_times["interval"] = last_lap_times.apply(calculate_interval, axis=1)
    last_lap_times["Gap to leader (s)"] = last_lap_times.apply(calculate_gap_to_leader, axis=1)

    # --- Fastest Lap per car ---
    fastest_laps = (
        class_df.loc[class_df["LAP_TIME_SECONDS"].notna()]
        .sort_values("LAP_TIME_SECONDS")
        .groupby("NUMBER")
        .first()
        .reset_index()
    )

    fastest_laps["FASTEST_LAP_FORMATTED"] = fastest_laps.apply(
        lambda r: f"{seconds_to_lap_format(r['LAP_TIME_SECONDS'])} ({r['DRIVER_NAME']})", axis=1
    )

    # Merge fastest lap info
    last_lap_times = last_lap_times.merge(
        fastest_laps[["NUMBER", "FASTEST_LAP_FORMATTED", "LAP_TIME_SECONDS"]],
        on="NUMBER",
        how="left"
    )

    # Identify class fastest lap
    fastest_class_lap_time = fastest_laps["LAP_TIME_SECONDS"].min()

    # --- Reorder columns ---
    display_df = last_lap_times[
        ["NUMBER", "TEAM", "DRIVERS", "LAP_NUMBER", "ELAPSED", "interval", "Gap to leader (s)", "FASTEST_LAP_FORMATTED"]
    ].rename(columns={"FASTEST_LAP_FORMATTED": "Fastest Lap"})

    # Add Position column starting from 1
    display_df.insert(0, "Position", range(1, len(display_df) + 1))

    # --- Highlight absolute fastest lap in class ---
    st.markdown(f"### All Cars in Class '{selected_class}' Ordered by Laps, Gaps, and Fastest Laps")
    st.dataframe(display_df.style.applymap(
        lambda v: "font-weight: bold; color: #00FFAA;" if isinstance(v, str) and "(" in v and str(fastest_class_lap_time) in v else ""
    ))
