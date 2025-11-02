import pandas as pd
import plotly.graph_objects as go
import streamlit as st

def show_time_gap_chart(df, team_colors):
    st.subheader("⏱️ Time Gap Comparison")

    # --- Determine class list and selection ---
    available_classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select Class", available_classes)

    class_df = df[df["CLASS"] == selected_class]

    # --- Determine available cars within that class ---
    available_cars = sorted(class_df["NUMBER"].unique())
    selected_cars = st.multiselect(
        "Select Cars to Compare", available_cars,
        help="Select at least two cars to compare race gaps."
    )

    if len(selected_cars) < 2:
        st.info("Select at least two cars to see the time gap chart.")
        return

    # --- Detect elapsed time column ---
    # We include ELAPSED in case it doesn't contain 'TIME'
    time_col_candidates = [c for c in df.columns if "TIME" in c.upper()] + \
                          [c for c in df.columns if c.upper() == "ELAPSED"]
    time_col_candidates = list(dict.fromkeys(time_col_candidates))  # remove duplicates

    if not time_col_candidates:
        st.error("No elapsed time column found (expected one named 'ELAPSED' or containing 'TIME').")
        return

    time_col = time_col_candidates[0]

    # --- Convert elapsed time to timedelta safely ---
    def parse_elapsed(value):
        try:
            parts = value.split(":")
            if len(parts) == 2:  # mm:ss.sss
                return pd.to_timedelta("0:" + value)
            elif len(parts) == 3:  # h:mm:ss.sss
                return pd.to_timedelta(value)
        except Exception:
            return pd.NaT
        return pd.NaT

    df["ELAPSED_TD"] = df[time_col].astype(str).apply(parse_elapsed)
    df["LAP_NUMBER"] = pd.to_numeric(df["LAP_NUMBER"], errors="coerce")

    # --- Build race gap data ---
    reference_car = selected_cars[0]
    fig = go.Figure()

    # Get reference car's race data
    ref_data = df[df["NUMBER"] == reference_car][["LAP_NUMBER", "ELAPSED_TD"]].dropna()
    ref_data = ref_data.sort_values("LAP_NUMBER").rename(columns={"ELAPSED_TD": "REF_TIME"})

    for car in selected_cars[1:]:
        car_data = df[df["NUMBER"] == car][["LAP_NUMBER", "ELAPSED_TD"]].dropna()
        car_data = car_data.sort_values("LAP_NUMBER").rename(columns={"ELAPSED_TD": "CAR_TIME"})

        # Merge laps between both cars to align comparison
        merged = pd.merge(ref_data, car_data, on="LAP_NUMBER", how="inner")
        if merged.empty:
            continue

        # Compute gap in seconds
        merged["GAP_SECONDS"] = (merged["CAR_TIME"] - merged["REF_TIME"]).dt.total_seconds()

        color = team_colors.get(
            df.loc[df["NUMBER"] == car, "TEAM"].iloc[0],
            None
        )

        fig.add_trace(go.Scatter(
            x=merged["LAP_NUMBER"],
            y=merged["GAP_SECONDS"],
            mode="lines",
            name=f"{car}",
            line=dict(width=2, color=color)
        ))

    # --- Dynamic Y-axis (based on data range) ---
    all_y = []
    for trace in fig.data:
        all_y.extend(trace.y)
    if all_y:
        y_min, y_max = min(all_y), max(all_y)
        margin = (y_max - y_min) * 0.1
        y_range = [y_max + margin, y_min - margin]  # reversed
    else:
        y_range = [1, 0]

    # --- Layout ---
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white"),
        xaxis=dict(title="Lap Number", showgrid=True, color="white"),
        yaxis=dict(
            title="Gap to Reference Car (seconds)",
            showgrid=True,
            color="white",
            autorange=False,
            range=y_range,
        ),
        legend=dict(title="Car Number"),
        hovermode="x unified",
        height=600,
    )

    st.plotly_chart(fig, use_container_width=True)
