import streamlit as st
import pandas as pd

def show_practice_analysis(df: pd.DataFrame, team_colors: dict):
    """
    Practice / Test session analysis page.

    This page is intentionally separate from race analysis logic.
    It focuses on ultimate pace, consistency, and performance decomposition.
    """

    st.subheader("Practice / Test Session Analysis")

    # --- Basic validation ---
    required_columns = {"LAP_TIME", "NUMBER", "TEAM"}

    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        st.error(
            f"Missing required columns for practice analysis: "
            f"{', '.join(sorted(missing_columns))}"
        )
        return

    # --- Session overview ---
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total laps", len(df))

    with col2:
        st.metric("Cars", df["NUMBER"].nunique())

    with col3:
        if "DRIVER_NAME" in df.columns:
            st.metric("Drivers", df["DRIVER_NAME"].nunique())
        else:
            st.metric("Drivers", "N/A")

    st.markdown("---")

    # --- Placeholder for charts ---
    st.info(
        "Practice/Test charts will appear here.\n\n"
        "Planned analyses include:\n"
        "- Best lap comparison\n"
        "- Top-percentile pace\n"
        "- Lap time distributions\n"
        "- Sector performance breakdowns"
    )
