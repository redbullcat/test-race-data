import pandas as pd
import streamlit as st

def show_time_gap_chart_debug(df, team_colors):
    st.subheader("⏱️ Time Gap Comparison - Debug Output with Drivers and Gaps")

    # --- Class selection ---
    available_classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select Class for Debug", available_classes)
    class_df = df[df["CLASS"] == selected_class]

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

    class_df = class_df.copy()
    class_df['ELAPSED_SECONDS'] = class_df['ELAPSED'].apply(to_seconds)
    class_df['LAP_NUMBER'] = pd.to_numeric(class_df['LAP_NUMBER'], errors='coerce')
    class_df = class_df.dropna(subset=['ELAPSED_SECONDS', 'LAP_NUMBER'])

    # --- Create driver list per car ---
    driver_map = (
        class_df.groupby('NUMBER')['DRIVER_NAME']
        .unique()
        .apply(lambda x: " / ".join(sorted(x)))
        .to_dict()
    )

    # --- Get last lap row per car (total race time) ---
    last_lap_times = (
        class_df.groupby('NUMBER')
        .apply(lambda x: x.loc[x['LAP_NUMBER'].idxmax()])
        .reset_index(drop=True)
    )

    # Add driver names
    last_lap_times['DRIVERS'] = last_lap_times['NUMBER'].map(driver_map)

    # Convert ELAPSED to seconds for sorting (redundant but safe)
    last_lap_times['ELAPSED_SECONDS'] = last_lap_times['ELAPSED'].apply(to_seconds)

    # Sort by laps desc, then elapsed seconds asc
    last_lap_times = last_lap_times.sort_values(
        by=['LAP_NUMBER', 'ELAPSED_SECONDS'],
        ascending=[False, True]
    ).reset_index(drop=True)

    # Leader info (car with most laps and fastest elapsed time)
    leader_lap = last_lap_times.loc[0, 'LAP_NUMBER']
    leader_time = last_lap_times.loc[0, 'ELAPSED_SECONDS']

    # --- Interval and Gap to Leader calculations ---
    def calculate_interval(row):
        laps_down = leader_lap - row['LAP_NUMBER']
        if laps_down >= 1:
            return f"{int(laps_down)} lap{'s' if laps_down > 1 else ''}"
        else:
            gap = row['ELAPSED_SECONDS'] - leader_time
            return f"{gap:.3f} s"

    def calculate_gap_to_leader(row):
        laps_down = leader_lap - row['LAP_NUMBER']
        if laps_down >= 1:
            return None
        else:
            return row['ELAPSED_SECONDS'] - leader_time

    last_lap_times['interval'] = last_lap_times.apply(calculate_interval, axis=1)
    last_lap_times['Gap to leader (s)'] = last_lap_times.apply(calculate_gap_to_leader, axis=1)

    # --- Reorder columns ---
    display_df = last_lap_times[['NUMBER', 'TEAM', 'DRIVERS', 'LAP_NUMBER', 'ELAPSED', 'interval', 'Gap to leader (s)']]

    # --- Display results ---
    st.markdown(f"### All Cars in Class '{selected_class}' Ordered by Laps and Elapsed Time with Drivers and Gaps")
    st.dataframe(display_df)
