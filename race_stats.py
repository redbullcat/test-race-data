import pandas as pd
import streamlit as st


# =========================
# Helper: ELAPSED parsing
# =========================

def parse_elapsed_to_timedelta(series: pd.Series) -> pd.Series:
    """
    Parse ELAPSED values into pandas Timedelta.

    Handles formats like:
    - hh:mm:ss
    - hh:mm:ss.sss
    - mm:ss.s

    Treated as race duration (not wall clock),
    so no 24h rollover.
    """
    return pd.to_timedelta(series, errors="coerce")


# =========================
# Helper: lap ranges
# =========================

def laps_to_ranges(laps):
    """
    Convert a sorted iterable of lap numbers into compact ranges.
    Example: [1,2,3,5,6,10] -> "1–3, 5–6, 10"
    """
    if not laps:
        return ""

    laps = sorted(laps)
    ranges = []

    start = prev = laps[0]

    for lap in laps[1:]:
        if lap == prev + 1:
            prev = lap
        else:
            ranges.append(f"{start}" if start == prev else f"{start}–{prev}")
            start = prev = lap

    ranges.append(f"{start}" if start == prev else f"{start}–{prev}")
    return ", ".join(ranges)


# =========================
# Leader extraction with FCY logic
# =========================

def get_overall_leader_by_lap(df):
    """
    Determine the overall leader per lap, accounting for FCY conditions:
    - On FCY laps, carry forward previous leader if still classified and not crossing line in pit.
    - Otherwise, pick car with lowest ELAPSED on the lap.
    """

    df = df.copy()
    df["ELAPSED"] = parse_elapsed_to_timedelta(df["ELAPSED"])

    # Sort for deterministic processing
    df = df.sort_values(["LAP_NUMBER", "ELAPSED"])

    # Prepare output rows
    leaders = []

    # Group data by lap for iteration
    laps = df["LAP_NUMBER"].unique()
    prev_leader_car_id = None

    for lap in laps:
        lap_df = df[df["LAP_NUMBER"] == lap]

        # Filter out cars crossing finish line in pit (value "B" means crossing in pit)
        eligible_lap_df = lap_df[lap_df["CROSSING_FINISH_LINE_IN_PIT"] != "B"].copy()

        flag = lap_df["FLAG_AT_FL"].dropna().unique()
        flag = flag[0] if len(flag) == 1 else None  # Expect one unique flag per lap ideally

        # If no eligible cars (unlikely), fallback to full lap_df
        if eligible_lap_df.empty:
            eligible_lap_df = lap_df.copy()

        # Logic for FCY laps
        if flag == "FCY" and prev_leader_car_id is not None:
            # Check if previous leader still classified and eligible on this lap
            prev_leader_rows = eligible_lap_df[eligible_lap_df["CAR_ID"] == prev_leader_car_id]

            if not prev_leader_rows.empty:
                # Previous leader remains leader for this lap
                leader_row = prev_leader_rows.iloc[0]
            else:
                # Previous leader not eligible: find car with lowest ELAPSED
                leader_row = eligible_lap_df.nsmallest(1, "ELAPSED").iloc[0]

        else:
            # Green or other flag laps: leader is car with lowest ELAPSED
            leader_row = eligible_lap_df.nsmallest(1, "ELAPSED").iloc[0]

        leaders.append(leader_row)
        prev_leader_car_id = leader_row["CAR_ID"]

    leaders_df = pd.DataFrame(leaders)

    # Select only relevant columns for output
    return leaders_df[["LAP_NUMBER", "CAR_ID", "NUMBER", "DRIVER_NAME", "CLASS", "FLAG_AT_FL"]]


def get_class_leader_by_lap(df):
    """
    Similar to overall leader, but per class.
    Uses ELAPSED only, no carry forward logic for now.
    """
    df = df.copy()
    df["ELAPSED"] = parse_elapsed_to_timedelta(df["ELAPSED"])

    return (
        df.sort_values(["LAP_NUMBER", "CLASS", "ELAPSED"])
          .groupby(["LAP_NUMBER", "CLASS"], as_index=False)
          .first()
          [["LAP_NUMBER", "CLASS", "CAR_ID", "NUMBER", "DRIVER_NAME"]]
    )


# =========================
# Core metrics and other functions remain unchanged
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


def compute_car_lead_stats_by_class(class_leader_df):
    total_laps = (
        class_leader_df.groupby("CLASS")["LAP_NUMBER"]
        .nunique()
        .to_dict()
    )

    grouped = class_leader_df.groupby(["CLASS", "CAR_ID", "NUMBER"])

    car_stats = grouped.size().reset_index(name="laps_led")

    car_stats["laps_range"] = grouped["LAP_NUMBER"].apply(
        lambda x: laps_to_ranges(x.tolist())
    ).values

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

    grouped = class_leader_df.groupby(
        ["CLASS", "CAR_ID", "NUMBER", "DRIVER_NAME"]
    )

    driver_stats = grouped.size().reset_index(name="laps_led")

    driver_stats["laps_range"] = grouped["LAP_NUMBER"].apply(
        lambda x: laps_to_ranges(x.tolist())
    ).values

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

    # --- Critical fix: normalize ELAPSED ---
    df = df.copy()
    df["ELAPSED"] = parse_elapsed_to_timedelta(df["ELAPSED"])

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
    st.markdown(
        f"**Longest uninterrupted overall lead:** Car **{car}** – **{laps} laps**"
    )

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
                    "CAR_ID": "Car ID",
                    "laps_led": "Laps led",
                    "laps_range": "Laps led (ranges)",
                    "pct_led": "% of class race led"
                })[
                    ["Car", "Car ID", "Laps led", "Laps led (ranges)", "% of class race led"]
                ],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("### Drivers")
            ds = driver_stats[driver_stats["CLASS"] == cls]

            st.dataframe(
                ds.rename(columns={
                    "NUMBER": "Car",
                    "CAR_ID": "Car ID",
                    "DRIVER_NAME": "Driver",
                    "laps_led": "Laps led",
                    "laps_range": "Laps led (ranges)",
                    "pct_led": "% of class race led"
                })[
                    ["Car", "Car ID", "Driver", "Laps led", "Laps led (ranges)", "% of class race led"]
                ],
                use_container_width=True,
                hide_index=True
            )
