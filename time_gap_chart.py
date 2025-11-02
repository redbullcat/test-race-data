import pandas as pd
import streamlit as st

def show_time_gap_chart(df, team_colors):
    st.subheader("⏱️ Time Gap Comparison - Debug Output Only")

    # --- Class selection ---
    available_classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select Class for Debug", available_classes)
    class_df = df[df["CLASS"] == selected_class]

    # --- Convert ELAPSED column (format: mm:ss.sss or h:mm:ss.sss) to total seconds ---
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

    # --- DEBUG: Show top 5 cars by total elapsed time per class ---
    st.markdown("### Debug: Top 5 cars by total elapsed time per class")
    for race_class in df['CLASS'].dropna().unique():
        st.markdown(f"**Class: {race_class}**")
        class_subset = df[df['CLASS'] == race_class].copy()

        # Get last lap row per car (assumed total race time)
        last_lap_times = class_subset.groupby('NUMBER').apply(
            lambda x: x.sort_values('LAP_NUMBER').iloc[-1]
        ).reset_index(drop=True)

        last_lap_times['ELAPSED_SECONDS'] = last_lap_times['ELAPSED'].apply(to_seconds)

        display_df = last_lap_times[['NUMBER', 'TEAM', 'ELAPSED', 'ELAPSED_SECONDS']]
        display_df = display_df.sort_values('ELAPSED_SECONDS').head(5)

        st.dataframe(display_df)
