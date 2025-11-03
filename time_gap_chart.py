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

    # Add driver
