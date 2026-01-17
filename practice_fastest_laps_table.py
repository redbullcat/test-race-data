import pandas as pd
import streamlit as st


def show_practice_fastest_laps(df: pd.DataFrame):
    st.markdown("### Fastest Laps by Session")

    # --- Defensive copy ---
    df = df.copy()

    # --- Required columns ---
    required_columns = {
        "NUMBER",
        "LAP_TIME",
        "PRACTICE_SESSION",
        "CLASS",
        "DRIVER_NAME",
    }

    missing = required_columns - set(df.columns)
    if missing:
        st.error(
            "Fastest laps table missing required columns: "
            + ", ".join(sorted(missing))
        )
        return

    # --- Parse lap time safely (mm:ss.000) ---
    df["LAP_TIME_TD"] = pd.to_timedelta(
        df["LAP_TIME"],
        errors="coerce"
    )

    # --- Drop invalid laps ---
    df = df.dropna(subset=["LAP_TIME_TD"])

    # --- Exclude pit laps if column exists ---
    if "CROSSING_FINISH_LINE_IN_PIT" in df.columns:
        df = df[df["CROSSING_FINISH_LINE_IN_PIT"] != 1]

    if df.empty:
        st.warning("No valid laps available for fastest lap analysis.")
        return

    # --- Per-session analysis ---
    for session, df_session in df.groupby("PRACTICE_SESSION"):
        st.markdown(f"#### {session}")

        # --- Fastest lap per car ---
        idx = df_session.groupby("NUMBER")["LAP_TIME_TD"].idxmin()
        fastest = df_session.loc[idx].copy()

        # --- Overall ranking ---
        fastest = fastest.sort_values("LAP_TIME_TD")
        fastest["Overall Position"] = range(1, len(fastest) + 1)

        # --- Class ranking ---
        fastest["Class Position"] = (
            fastest
            .groupby("CLASS")["LAP_TIME_TD"]
            .rank(method="min")
            .astype(int)
        )

        # --- Gap to leader ---
        leader_time = fastest.iloc[0]["LAP_TIME_TD"]
        fastest["Gap"] = fastest["LAP_TIME_TD"] - leader_time

        def format_gap(td):
            if td == pd.Timedelta(0):
                return "—"
            return f"+{td.total_seconds():.3f}s"

        fastest["Gap"] = fastest["Gap"].apply(format_gap)

        # --- Italicise driver who set fastest lap ---
        def format_driver(row):
            if row["Overall Position"] == 1:
                return f"*{row['DRIVER_NAME']}*"
            return row["DRIVER_NAME"]

        fastest["Driver"] = fastest.apply(format_driver, axis=1)

        # --- Display table ---
        display_df = fastest[
            [
                "Overall Position",
                "Class Position",
                "NUMBER",
                "CLASS",
                "Driver",
                "Gap",
            ]
        ].rename(columns={
            "NUMBER": "Car",
            "CLASS": "Class",
        })

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
