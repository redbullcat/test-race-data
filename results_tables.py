import pandas as pd
import streamlit as st

def show_results_tables(df, team_colors):
    st.subheader("🏁 Race Results by Class (Debug Mode)")

    # --- Convert ELAPSED column to seconds ---
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

    # Ensure proper types
    df = df.copy()
    df['LAP_NUMBER'] = pd.to_numeric(df['LAP_NUMBER'], errors='coerce')
    df['ELAPSED_SECONDS'] = df['ELAPSED'].apply(to_seconds)

    # --- Calculate total elapsed per car (last lap) ---
    last_lap = (
        df.sort_values('LAP_NUMBER')
        .groupby('NUMBER')
        .tail(1)
        .reset_index(drop=True)
    )

    # --- Add fastest lap per car ---
    def get_fastest_lap(group):
        valid = group.dropna(subset=['LAP_TIME'])
        if valid.empty:
            return None, None
        valid = valid.copy()
        valid['LAP_TIME_SEC'] = valid['LAP_TIME'].astype(str).apply(to_seconds)
        best_row = valid.loc[valid['LAP_TIME_SEC'].idxmin()]
        # DRIVER_NAME expected in your data
        driver_col = 'DRIVER_NAME' if 'DRIVER_NAME' in best_row.index else ('DRIVER' if 'DRIVER' in best_row.index else None)
        return best_row['LAP_TIME'], best_row[driver_col] if driver_col else None

    car_fastest = df.groupby('NUMBER').apply(get_fastest_lap).reset_index()
    car_fastest.columns = ['NUMBER', 'FastestData']
    car_fastest[['FASTEST_LAP', 'FASTEST_DRIVER']] = pd.DataFrame(car_fastest['FastestData'].tolist(), index=car_fastest.index)
    car_fastest.drop(columns=['FastestData'], inplace=True)

    last_lap = last_lap.merge(car_fastest, on='NUMBER', how='left')

    # --- Build per-class results ---
    for race_class in sorted(df['CLASS'].dropna().unique()):
        st.markdown(f"### 🏎️ {race_class} Class Results")

        class_cars = last_lap[last_lap['CLASS'] == race_class].copy()
        if class_cars.empty:
            st.info(f"No data found for class {race_class}")
            continue

        # Sort by laps completed and total time
        class_cars = class_cars.sort_values(['LAP_NUMBER', 'ELAPSED_SECONDS'], ascending=[False, True]).reset_index(drop=True)

        # ✅ Add Position column (starting from 1)
        class_cars.insert(0, "Position", range(1, len(class_cars) + 1))

        # Compute interval & gap to leader
        leader_time = class_cars.iloc[0]['ELAPSED_SECONDS']
        leader_laps = class_cars.iloc[0]['LAP_NUMBER']

        intervals, gaps = [None], [0.0]
        for i in range(1, len(class_cars)):
            car = class_cars.iloc[i]
            prev = class_cars.iloc[i - 1]
            if car['LAP_NUMBER'] < leader_laps:
                laps_down = int(leader_laps - car['LAP_NUMBER'])
                interval = f"{laps_down} lap"
                gap = f"{laps_down} lap"
            else:
                interval_val = car['ELAPSED_SECONDS'] - prev['ELAPSED_SECONDS']
                gap_val = car['ELAPSED_SECONDS'] - leader_time
                interval = f"{interval_val:.3f}s"
                gap = f"{gap_val:.3f}s"
            intervals.append(interval)
            gaps.append(gap)

        class_cars['Interval'] = intervals
        class_cars['Gap to Leader'] = gaps

        # Combine drivers list into a single column (if multiple drivers)
        driver_col_name = None
        if 'DRIVER_NAME' in df.columns:
            driver_col_name = 'DRIVER_NAME'
        elif 'DRIVER' in df.columns:
            driver_col_name = 'DRIVER'

        if driver_col_name:
            drivers_by_car = (
                df.groupby('NUMBER')[driver_col_name]
                .unique()
                .apply(lambda d: " / ".join(map(str, d)))
                .reset_index()
                .rename(columns={driver_col_name: 'DRIVERS'})
            )
            class_cars = class_cars.merge(drivers_by_car, on='NUMBER', how='left')
        else:
            class_cars['DRIVERS'] = None

        # Identify fastest lap in class
        all_fastest = df[df['CLASS'] == race_class].copy()
        all_fastest['LAP_TIME_SEC'] = all_fastest['LAP_TIME'].apply(to_seconds)
        if not all_fastest['LAP_TIME_SEC'].dropna().empty:
            best_lap_sec = all_fastest['LAP_TIME_SEC'].min()
        else:
            best_lap_sec = None

        def format_fastest(row):
            lap = row.get('FASTEST_LAP', None)
            driver = row.get('FASTEST_DRIVER', None)
            if pd.isna(lap) or lap is None:
                return ""
            lap_sec = to_seconds(lap)
            formatted = f"{lap} ({driver})" if driver else f"{lap}"
            if best_lap_sec and lap_sec == best_lap_sec:
                return f"**{formatted}**"
            return formatted

        class_cars['Fastest Lap'] = class_cars.apply(format_fastest, axis=1)

        # Format elapsed time
        def format_time(seconds):
            if pd.isna(seconds):
                return ""
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h >= 1:
                return f"{int(h)}:{int(m):02d}:{s:06.3f}"
            else:
                return f"{int(m)}:{s:06.3f}"

        class_cars['Total Time'] = class_cars['ELAPSED_SECONDS'].apply(format_time)

        # Build display columns list, but only keep those that exist
        desired_cols = [
            'Position', 'NUMBER', 'TEAM', 'DRIVERS', 'LAP_NUMBER',
            'Interval', 'Gap to Leader', 'Fastest Lap', 'Total Time'
        ]
        available_cols = [c for c in desired_cols if c in class_cars.columns]

        # Rename DRIVERS -> DRIVER for display if you prefer a different label
        # we'll present it as DRIVER to match prior expectations
        if 'DRIVERS' in available_cols:
            class_cars = class_cars.rename(columns={'DRIVERS': 'DRIVER'})

            # adjust available_cols list
            available_cols = [ 'Position' if c=='Position' else ('DRIVER' if c=='DRIVERS' else c) for c in desired_cols ]
            # filter to those actually present
            available_cols = [c for c in available_cols if c in class_cars.columns]

        st.dataframe(class_cars[available_cols], use_container_width=True, hide+index=True)
