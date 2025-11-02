import pandas as pd
import plotly.graph_objects as go
import streamlit as st

def show_time_gap_chart(df, team_colors):
    st.subheader("⏱️ Time Gap Comparison")

    # --- Class and car selection ---
    available_classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select Class", available_classes)
    class_df = df[df["CLASS"] == selected_class]

    available_cars = sorted(class_df["NUMBER"].unique())
    selected_cars = st.multiselect(
        "Select Cars to Compare", available_cars,
        help="Select at least two cars to compare race gaps."
    )

    if len(selected_cars) < 2:
        st.info("Select at least two cars to see the time gap chart.")
        return

    # --- Ensure ELAPSED column exists ---
    if "ELAPSED" not in df.columns:
        st.error("No 'ELAPSED' column found.")
        return

    # --- Convert ELAPSED to timedelta robustly ---
    def parse_elapsed(value):
        if pd.isna(value):
            return pd.NaT
        value = str(value).strip()
        try:
            parts = value.split(":")
            if len(parts) == 2:  # mm:ss.sss
                return pd.to_timedelta("0:" + value)
            elif len(parts) == 3:
                h, m, s = parts
                # if hours part >= 60, it’s actually minutes
                if int(h) >= 60:
                    return pd.to_timedelta("0:" + value)
                else:
                    return pd.to_timedelta(value)
        except Exception:
            return pd.NaT
        return pd.NaT

    df["ELAPSED_TD"] = df["ELAPSED"].astype(str).apply(parse_elapsed)
    df["LAP_NUMBER"] = pd.to_numeric(df["LAP_NUMBER"], errors="coerce")

    # --- Build reference and comparison traces ---
    reference_car = selected_cars[0]
    ref_data = df[df["NUMBER"] == reference_car][["LAP_NUMBER", "ELAPSED_TD"]].dropna()
    ref_data = ref_data.sort_values("LAP_NUMBER").rename(columns={"ELAPSED_TD": "REF_TIME"})

    fig = go.Figure()

    for car in selected_cars[1:]:
        car_data = df[df["NUMBER"] == car][["LAP_NUMBER", "ELAPSED_TD"]].dropna()
        car_data = car_data.sort_values("LAP_NUMBER").rename(columns={"ELAPSED_TD": "CAR_TIME"})

        merged = pd.merge(ref_data, car_data, on="LAP_NUMBER", how="inner")
        if merged.empty:
            continue

        merged["GAP_SECONDS"] = (merged["CAR_TIME"] - merged["REF_TIME"]).dt.total_seconds()

        team = df.loc[df["NUMBER"] == car, "TEAM"].iloc[0] if not df[df["NUMBER"] == car].empty else "Unknown"
        color = team_colors.get(team, "#888888")

        fig.add_trace(go.Scatter(
            x=merged["LAP_NUMBER"],
            y=merged["GAP_SECONDS"],
            mode="lines",
            name=f"{car}",
            line=dict(width=2, color=color)
        ))

    # --- Dynamic Y-axis range (reversed) ---
    all_y = [y for trace in fig.data for y in trace.y]
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
            title=f"Gap to Car #{reference_car} (seconds)",
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
