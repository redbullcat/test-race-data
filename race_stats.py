import pandas as pd
import streamlit as st


# =========================
# Leader extraction
# =========================

def get_overall_leader_by_lap(df):
    """
    One row per lap: overall race leader.
    Uses CAR_ID for uniqueness, NUMBER only for display.
    """
    return (
        df.sort_values(["LAP_NUMBER", "ELAPSED"])
          .groupby("LAP_NUMBER", as_index=False)
          .first()
          [["LAP_NUMBER", "CAR_ID", "NUMBER", "DRIVER_NAME", "CLASS", "FLAG_AT_FL"]]
    )


def get_class_leader_by_lap(df):
    """
    One row per lap PER CLASS: class leader.
    """
    return (
        df.sort_values(["LAP_NUMBER", "CLASS", "ELAPSED"])
          .groupby(["LAP_NUMBER", "CLASS"], as_index=False)
          .first()
          [["LAP_NUMBER", "CLASS", "CAR_ID", "NUMBER", "DRIVER_NAME"]]
    )


# =========================
# Core metrics
# =========================

def compute_lead_changes(overall_leader_df):
    overall_leader_df = overall_leader_df.sort_values("LAP_NUMBER")
    return max(
        (overall_leader_df["CAR_ID"] != overall_leader_df["CAR_ID"].shift()).sum() - 1,
        0
    )


def compute_flag_lap_counts(overall_leader_df):
    return overall_leader_df["FLAG_AT_FL"].fillna("GREEN").value_counts().to_dict()


def compute_longest_lead_stint(overall_leader_df):
    df = overall_leader_df.copy()
    df["change"] = df["CAR_ID"] != df["CAR_ID"].shift()
    df["stint_id"] = df["change"].cumsum()

    stints = (
        df.groupby(["stint_id", "CAR_ID", "NUMBER"])
        .size()
        .reset_index(name="laps_led")
        .sort_values("laps_led", ascending=False)
    )

    top = stints.iloc[0]
    return top["NUMBER"], int(top["laps_led"])


# =========================
# Class-based stats
# =========================

def compute_car_lead_stats_by_class(class_leader_df):
    total_laps = (
        class_leader_df.groupby("CLASS")["LAP_NUMBER"]
        .nunique()
        .to_dict()
    )

    car_stats = (
        class_leader_df
        .groupby(["CLASS", "CAR_ID", "NUMBER"])
        .size()
        .reset_index(name="laps_led")
    )

    car_stats["pct_led"] = car_stats.apply(
        lambda r: round(r["laps_led"] / total_laps.get(r["CLASS"], 1) * 100, 1),
        axis=1
    )

    return car_stats.sort_values(["CLASS", "laps_led"], ascending=[True, False])


def compute_driver_lead_stats_by_class(class_leader_df):
    total_laps = (
        class_leader_df.groupby("CLASS")["LAP_NUMBER"]
        .nunique()
        .to_dict()
    )

    driver_stats = (
        class_leader_df
        .groupby(["CLASS", "CAR_ID", "NUMBER", "DRIVER_NAME"])
        .size()
        .reset_index(name="laps_led")
    )

    driver_stats["pct_led"] = driver_stats.apply(
        lambda r: round(r["laps_led"] / total_laps.get(r["CLASS"], 1) * 100, 1),
        axis=1
    )

    return driver_stats.sort_values(
        ["CLASS", "laps_led", "NUMBER"],
        ascending=[True, False, True]
    )


# =========================
# Streamlit renderer
# =========================

def show_race_stats(df):
    st.subheader("Race statistics")

    overall_leader_df = get_overall_leader_by_lap(df)
    class_leader_df = get_class_leader_by_lap(df)

    # --- Headline metrics ---
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Overall lead changes", compute_lead_changes(overall_leader_df))

    with col2:
        st.metric("Cars that led overall", overall_leader_df["CAR_ID"].nunique())

    with col3:
        st.metric("Total race laps", overall_leader_df["LAP_NUMBER"].nunique())

    # --- Flags ---
    st.markdown("**Laps by flag condition**")
    for flag, count in compute_flag_lap_counts(overall_leader_df).items():
        st.write(f"- **{flag}**: {count} laps")

    # --- Longest stint ---
    car, laps = compute_longest_lead_stint(overall_leader_df)
    st.markdown(f"**Longest uninterrupted overall lead:** Car **{car}** – **{laps} laps**")

    # --- Class leaders ---
    st.markdown("## Laps led by class")

    classes = sorted(class_leader_df["CLASS"].dropna().unique())
    tabs = st.tabs(classes)

    car_stats = compute_car_lead_stats_by_class(class_leader_df)
    driver_stats = compute_driver_lead_stats_by_class(class_leader_df)

    for tab, cls in zip(tabs, classes):
        with tab:
            st.markdown("### Cars")
            cs = car_stats[car_stats["CLASS"] == cls]

            st.dataframe(
                cs.rename(columns={
                    "NUMBER": "Car",
                    "laps_led": "Laps led",
                    "pct_led": "% of class race led"
                })[["Car", "Laps led", "% of class race led"]],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("### Drivers")
            ds = driver_stats[driver_stats["CLASS"] == cls]

            st.dataframe(
                ds.rename(columns={
                    "NUMBER": "Car",
                    "DRIVER_NAME": "Driver",
                    "laps_led": "Laps led",
                    "pct_led": "% of class race led"
                })[["Car", "Driver", "Laps led", "% of class race led"]],
                use_container_width=True,
                hide_index=True
            )
