import pandas as pd
import streamlit as st


def get_leader_by_lap(df):
    """
    One row per lap, leader defined as first car to complete the lap.
    CLASS is inherited from the leading car on that lap.
    """
    leader_df = (
        df.sort_values(["LAP_NUMBER", "ELAPSED"])
          .groupby("LAP_NUMBER", as_index=False)
          .first()
          [["LAP_NUMBER", "NUMBER", "DRIVER_NAME", "CLASS", "FLAG_AT_FL"]]
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
        leader_df.groupby(["CLASS", "NUMBER"])
        .size()
        .reset_index(name="laps_led")
    )

    car_stats["pct_led"] = (car_stats["laps_led"] / total_laps * 100).round(1)

    return car_stats.sort_values(["CLASS", "laps_led"], ascending=[True, False])


def compute_driver_lead_stats(leader_df):
    total_laps = leader_df["LAP_NUMBER"].nunique()

    driver_stats = (
        leader_df.groupby(["CLASS", "NUMBER", "DRIVER_NAME"])
        .size()
        .reset_index(name="laps_led")
    )

    driver_stats["pct_led"] = (driver_stats["laps_led"] / total_laps * 100).round(1)

    return driver_stats.sort_values(
        ["CLASS", "laps_led", "NUMBER"],
        ascending=[True, False, True]
    )


def show_race_stats(df):
    st.subheader("Race statistics")

    leader_df = get_leader_by_lap(df)

    # --- Headline stats (overall race) ---
    lead_changes = compute_lead_changes(leader_df)
    cars_that_led = leader_df["NUMBER"].nunique()
    flag_counts = compute_flag_lap_counts(leader_df)
    total_laps = leader_df["LAP_NUMBER"].nunique()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Overall lead changes", lead_changes)

    with col2:
        st.metric("Cars that led the race", cars_that_led)

    with col3:
        st.metric("Total race laps", total_laps)

    # --- Flag breakdown ---
    st.markdown("**Laps by flag condition**")
    for flag, count in sorted(flag_counts.items()):
        st.write(f"- **{flag}**: {count} laps")

    # --- Longest lead stint ---
    car, laps = compute_longest_lead_stint(leader_df)
    st.markdown(f"**Longest uninterrupted lead:** Car **{car}** – **{laps} laps**")

    # --- Per-class lead stats ---
    st.markdown("## Laps led by class")

    classes = sorted(leader_df["CLASS"].dropna().unique())

    if not classes:
        st.info("No class information available for this race.")
        return

    class_tabs = st.tabs(classes)

    car_stats = compute_car_lead_stats(leader_df)
    driver_stats = compute_driver_lead_stats(leader_df)

    for tab, race_class in zip(class_tabs, classes):
        with tab:
            st.markdown(f"### {race_class}")

            # --- Cars ---
            st.markdown("**Cars**")
            class_car_stats = car_stats[car_stats["CLASS"] == race_class]

            if class_car_stats.empty:
                st.info("No lead data for this class.")
            else:
                st.dataframe(
                    class_car_stats.rename(
                        columns={
                            "NUMBER": "Car",
                            "laps_led": "Laps led",
                            "pct_led": "% of race led"
                        }
                    )[["Car", "Laps led", "% of race led"]],
                    use_container_width=True,
                    hide_index=True
                )

            # --- Drivers ---
            st.markdown("**Drivers**")
            class_driver_stats = driver_stats[driver_stats["CLASS"] == race_class]

            if class_driver_stats.empty:
                st.info("No driver lead data for this class.")
            else:
                st.dataframe(
                    class_driver_stats.rename(
                        columns={
                            "NUMBER": "Car",
                            "DRIVER_NAME": "Driver",
                            "laps_led": "Laps led",
                            "pct_led": "% of race led"
                        }
                    )[["Car", "Driver", "Laps led", "% of race led"]],
                    use_container_width=True,
                    hide_index=True
                )
