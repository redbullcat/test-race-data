import pandas as pd
import streamlit as st


def get_leader_by_lap(df):
    """
    One row per lap, leader defined as first car to complete the lap.
    """
    leader_df = (
        df.sort_values(["LAP_NUMBER", "ELAPSED"])
          .groupby("LAP_NUMBER", as_index=False)
          .first()
          [["LAP_NUMBER", "NUMBER", "DRIVER_NAME", "FLAG_AT_FL"]]
    )
    return leader_df


def compute_lead_changes(leader_df):
    leader_df = leader_df.sort_values("LAP_NUMBER")
    changes = (leader_df["NUMBER"] != leader_df["NUMBER"].shift()).sum() - 1
    return max(changes, 0)


def compute_flag_lap_counts(leader_df):
    return leader_df["FLAG_AT_FL"].fillna("GREEN").value_counts().to_dict()


def compute_longest_lead_stint(leader_df):
    leader_df = leader_df.copy()
    leader_df["lead_change"] = leader_df["NUMBER"] != leader_df["NUMBER"].shift()
    leader_df["stint_id"] = leader_df["lead_change"].cumsum()

    stint_lengths = (
        leader_df.groupby(["stint_id", "NUMBER"])
        .size()
        .reset_index(name="laps_led")
    )

    longest = stint_lengths.sort_values("laps_led", ascending=False).iloc[0]
    return longest["NUMBER"], int(longest["laps_led"])


def compute_car_lead_stats(leader_df):
    total_laps = leader_df["LAP_NUMBER"].nunique()

    car_stats = (
        leader_df.groupby("NUMBER")
        .size()
        .reset_index(name="laps_led")
    )

    car_stats["pct_led"] = (car_stats["laps_led"] / total_laps * 100).round(1)
    car_stats = car_stats.sort_values("laps_led", ascending=False)

    return car_stats, total_laps


def compute_driver_lead_stats(leader_df):
    total_laps = leader_df["LAP_NUMBER"].nunique()

    driver_stats = (
        leader_df.groupby(["NUMBER", "DRIVER_NAME"])
        .size()
        .reset_index(name="laps_led")
    )

    driver_stats["pct_led"] = (driver_stats["laps_led"] / total_laps * 100).round(1)
    driver_stats = driver_stats.sort_values(["laps_led", "NUMBER"], ascending=False)

    return driver_stats


def show_race_stats(df):
    st.subheader("Race statistics")

    leader_df = get_leader_by_lap(df)

    # --- Headline stats ---
    lead_changes = compute_lead_changes(leader_df)
    cars_that_led = leader_df["NUMBER"].nunique()
    flag_counts = compute_flag_lap_counts(leader_df)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Overall lead changes", lead_changes)

    with col2:
        st.metric("Cars that led the race", cars_that_led)

    with col3:
        st.metric("Total race laps", leader_df["LAP_NUMBER"].nunique())

    # --- Flag breakdown ---
    st.markdown("**Laps by flag condition**")
    for flag, count in sorted(flag_counts.items()):
        st.write(f"- **{flag}**: {count} laps")

    # --- Longest lead stint ---
    car, laps = compute_longest_lead_stint(leader_df)
    st.markdown(f"**Longest uninterrupted lead:** Car **{car}** – **{laps} laps**")

    # --- Car lead table ---
    st.markdown("### Laps led by car")

    car_stats, total_laps = compute_car_lead_stats(leader_df)

    st.dataframe(
        car_stats.rename(
            columns={
                "NUMBER": "Car",
                "laps_led": "Laps led",
                "pct_led": "% of race led"
            }
        ),
        use_container_width=True,
        hide_index=True
    )

    # --- Driver lead table ---
    st.markdown("### Laps led by driver")

    driver_stats = compute_driver_lead_stats(leader_df)

    st.dataframe(
        driver_stats.rename(
            columns={
                "NUMBER": "Car",
                "DRIVER_NAME": "Driver",
                "laps_led": "Laps led",
                "pct_led": "% of race led"
            }
        ),
        use_container_width=True,
        hide_index=True
    )
