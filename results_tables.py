import pandas as pd
import streamlit as st

def show_results_tables(df, team_colors):
    st.subheader("🏁 Race Results by Class")

    # --- Helper: Convert ELAPSED to total seconds ---
    def to_seconds(t):
        if pd.isna(t):
            return None
        t = str(t).strip()
        parts = t.split(':')
        try:
            if len(parts) == 3:  # h:mm:ss.sss
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:  # mm:ss.sss
                m, s = parts
                return int(m) * 60 + float(s)
        except Exception:
            return None
        return None

    # --- Helper: Get fastest lap for each car ---
    def get_fastest_lap(car_df):
        car_df = car_df.copy()
        car_df["LAP_TIME_S"] = car_df["LAP_TIME"].apply(to_seconds)
        car_df = car_df.dropna(subset=["LAP_TIME_S"])
        if len(car_df) == 0:
            return pd.Series({"Fastest Lap": None})
        best_row = car_df.loc[car_df["LAP_TIME_S"].idxmin()]
        formatted = f"{best_row['LAP_TIME']} ({best_row['DRIVER_NAME']})"
        return pd.Series({"Fastest Lap": formatted, "Fastest Lap Time": best_row["LAP_TIME_S"]})

    # --- Precompute fastest laps for all cars ---
    car_fastest = df.groupby("NUMBER").apply(get_fastest_lap).reset_index()

    # --- Process results by class ---
    for race_class in sorted(df["CLASS"].dropna().unique()):
        st.markdown(f"### **Class: {race_class}**")

        class_subset = df[df["CLASS"] == race_class].copy()
        class_subset["ELAPSED_SECONDS"] = class_subset["ELAPSED"].apply(to_seconds)
        class_subset["LAP_NUMBER"] = pd.to_numeric(class_subset["LAP_NUMBER"], errors="coerce")

        # Last lap row per car = finish time
        last_lap_times = (
            class_subset.groupby("NUMBER", as_index=False)
            .apply(lambda x: x.sort_values("LAP_NUMBER").iloc[-1])
            .reset_index(drop=True)
        )

        # Merge fastest lap info
        last_lap_times = last_lap_times.merge(car_fastest, on="NUMBER", how="left")

        # Add combined driver names per car
        driver_names = (
            class_subset.groupby("NUMBER")["DRIVER_NAME"]
            .unique()
            .apply(lambda x: " / ".join(x))
            .reset_index()
        )
        last_lap_times = last_lap_times.merge(driver_names, on="NUMBER", how="left")

        # Sort: first by LAP_NUMBER desc (more laps = ahead), then by ELAPSED_SECONDS asc
        last_lap_times = last_lap_times.sort_values(
            by=["LAP_NUMBER", "ELAPSED_SECONDS"], ascending=[False, True]
        ).reset_index(drop=True)

        # Add Position (1-based)
        last_lap_times.insert(0, "Position", range(1, len(last_lap_times) + 1))

        # Determine interval and gap to leader
        leader_time = last_lap_times.iloc[0]["ELAPSED_SECONDS"]
        leader_laps = last_lap_times.iloc[0]["LAP_NUMBER"]

        intervals = []
        gaps_to_leader = []

        for i, row in last_lap_times.iterrows():
            if i == 0:
                intervals.append("—")
                gaps_to_leader.append("—")
                continue

            lap_diff_prev = last_lap_times.iloc[i - 1]["LAP_NUMBER"] - row["LAP_NUMBER"]
            lap_diff_leader = leader_laps - row["LAP_NUMBER"]

            if lap_diff_prev > 0:
                intervals.append(f"{int(lap_diff_prev)} lap")
            else:
                diff_prev = row["ELAPSED_SECONDS"] - last_lap_times.iloc[i - 1]["ELAPSED_SECONDS"]
                intervals.append(f"{diff_prev:.3f}s")

            if lap_diff_leader > 0:
                gaps_to_leader.append(f"{int(lap_diff_leader)} lap")
            else:
                diff_leader = row["ELAPSED_SECONDS"] - leader_time
                gaps_to_leader.append(f"{diff_leader:.3f}s")

        last_lap_times["Interval"] = intervals
        last_lap_times["Gap to Leader"] = gaps_to_leader

        # === DEBUG: Print columns to check before subsetting ===
        st.write("Columns in last_lap_times BEFORE selecting display columns:", last_lap_times.columns.tolist())

        display_cols = [
            "Position",
            "NUMBER",
            "TEAM",
            "DRIVER_NAME",
            "Interval",
            "Gap to Leader",
            "Fastest Lap",
        ]

        # Check for missing columns
        missing_cols = [col for col in display_cols if col not in last_lap_times.columns]
        if missing_cols:
            st.error(f"Missing columns in last_lap_times: {missing_cols}")

        # Convert mixed-type columns to strings to avoid Arrow conversion issues
        last_lap_times["Gap to Leader"] = last_lap_times["Gap to Leader"].astype(str)
        last_lap_times["Interval"] = last_lap_times["Interval"].astype(str)

        class_cars = last_lap_times[display_cols].rename(columns={"DRIVER_NAME": "Drivers"})

        # Highlight class-best fastest lap
        min_fastest = last_lap_times["Fastest Lap Time"].min()
        class_cars["Fastest Lap"] = class_cars.apply(
            lambda x: f"**{x['Fastest Lap']}**"
            if pd.notna(x["Fastest Lap"])
            and last_lap_times.loc[last_lap_times["NUMBER"] == x["NUMBER"], "Fastest Lap Time"].iloc[0] == min_fastest
            else x["Fastest Lap"],
            axis=1,
        )

        # Display table
        st.dataframe(class_cars, width="stretch", hide_index=True)
