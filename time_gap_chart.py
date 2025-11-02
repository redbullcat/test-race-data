import pandas as pd
import streamlit as st

def show_time_gap_chart_debug(df, team_colors):
    st.subheader("⏱️ Time Gap Comparison - Debug Output Ordered by Laps and Time")

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

    # --- Get last lap row per car (total race time) ---
    last_lap_times = (
        class_df.groupby('NUMBER')
        .apply(lambda x: x.loc[x['LAP_NUMBER'].idxmax()])
        .reset_index(drop=True)
    )

    # Convert ELAPSED to seconds for sorting
    last_lap_times['ELAPSED_SECONDS'] = last_lap_times['ELAPSED'].apply(to_seconds)

    # Sort by laps desc, then elapsed seconds asc
    last_lap_times = last_lap_times.sort_values(
        by=['LAP_NUMBER', 'ELAPSED_SECONDS'],
        ascending=[False, True]
    )

    display_df = last_lap_times[['NUMBER', 'TEAM', 'LAP_NUMBER', 'ELAPSED']]

    st.markdown(f"### All Cars in Class '{selected_class}' Ordered by Laps and Elapsed Time")
    st.dataframe(display_df)
