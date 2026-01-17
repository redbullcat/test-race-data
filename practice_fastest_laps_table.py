import pandas as pd
import streamlit as st


def parse_lap_time(lap_str):
    """
    Parse lap time string in mm:ss.sss format into pd.Timedelta.
    Return pd.NaT if parsing fails.
    """
    if pd.isna(lap_str):
        return pd.NaT

    lap_str = str(lap_str).strip()
    if not lap_str:
        return pd.NaT

    # Expect format like "4:05.577" (m:ss.sss)
    parts = lap_str.split(":")
    if len(parts) != 2:
        return pd.NaT

    try:
        minutes = int(parts[0])
        seconds = float(parts[1])
        total_seconds = minutes * 60 + seconds
        return pd.Timedelta(seconds=total_seconds)
    except Exception:
        return pd.NaT


def show_practice_fastest_laps(df: pd.DataFrame):
    st.markdown("### Practice Sessions - Fastest Laps")

    # Defensive copy
    df = df.copy()

    # Required columns check
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

    # Strip whitespace on LAP_TIME strings
    df["LAP_TIME"] = df["LAP_TIME"].astype(str).str.strip()

    # Parse LAP_TIME using custom function
    df["LAP_TIME_TD"] = df["LAP_TIME"].apply(parse_lap_time)

    # Debug: Show how many failed parses
    failed_parses = df["LAP_TIME_TD"].isna().sum()
    if failed_parses > 0:
        st.warning(f"LAP_TIME parsing failed for {failed_parses} rows.")
        st.write(df.loc[df["LAP_TIME_TD"].isna(), ["LAP_TIME"]].head(10))

    # Drop rows with invalid lap times
    df = df.dropna(subset=["LAP_TIME_TD"])
    if df.empty:
        st.error("No valid lap times found after parsing LAP_TIME.")
        return

    # Exclude pit laps if column exists
    if "CROSSING_FINISH_LINE_IN_PIT" in df.columns:
        df = df[df["CROSSING_FINISH_LINE_IN_PIT"] != 1]

    if df.empty:
        st.warning("All valid laps were pit laps.")
        return

    # Process each practice session separately
    for session, df_session in df.groupby("PRACTICE_SESSION"):
        st.markdown(f"#### {session}")

        # Fastest lap per car
        idx = df_session.groupby("NUMBER")["LAP_TIME_TD"].idxmin()
        fastest = df_session.loc[idx].copy()

        # Overall ranking
        fastest = fastest.sort_values("LAP_TIME_TD")
        fastest["Overall Position"] = range(1, len(fastest) + 1)

        # Class ranking
        fastest["Class Position"] = (
            fastest
            .groupby("CLASS")["LAP_TIME_TD"]
            .rank(method="min")
            .astype(int)
        )

        # Gap to leader
        leader_time = fastest.iloc[0]["LAP_TIME_TD"]
        fastest["Gap"] = fastest["LAP_TIME_TD"] - leader_time

        def format_gap(td):
            if td == pd.Timedelta(0):
                return "—"
            return f"+{td.total_seconds():.3f}s"

        fastest["Gap"] = fastest["Gap"].apply(format_gap)

        # Driver formatting
        fastest["Driver"] = fastest["DRIVER_NAME"]

        # Display table
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
            width="stretch",
            hide_index=True
        )
