"""driver_pace_comparison_chart.py — Driver pace comparison by lap percentiles."""

import plotly.graph_objects as go
import streamlit as st

from utils import apply_dark_layout


@st.cache_data(show_spinner=False)
def _driver_percentile_avg(df, driver: str, percentile: int) -> float | None:
    laps = df[df["DRIVER_NAME"] == driver].nsmallest(
        max(1, int(len(df[df["DRIVER_NAME"] == driver]) * percentile / 100)),
        "LAP_TIME_SECONDS",
    )["LAP_TIME_SECONDS"]
    return float(laps.mean()) if not laps.empty else None


def show_driver_pace_comparison(df, team_colors):
    st.subheader("Driver Pace Comparison by Lap Percentile")

    classes = df["CLASS"].dropna().unique().tolist()
    selected_classes = st.multiselect(
        "Select class(es) to compare:", classes, key="dpc_class"
    )
    if not selected_classes:
        st.info("Select at least one class.")
        return

    selected_drivers = []
    for cls in selected_classes:
        class_drivers = (
            df[df["CLASS"] == cls]["DRIVER_NAME"].dropna().unique().tolist()
        )
        chosen = st.multiselect(f"Drivers from {cls}:", class_drivers, key=f"dpc_{cls}")
        selected_drivers.extend(chosen)

    if len(selected_drivers) < 2:
        st.info("Select at least two drivers to compare.")
        return

    percentile_options = [20, 40, 60, 80, 100]
    st.markdown("**Select percentile ranges:**")
    cols = st.columns(len(percentile_options))
    selected_percentiles = [
        p for i, p in enumerate(percentile_options)
        if cols[i].checkbox(f"Top {p}%", value=(p == 100), key=f"dpc_pct_{p}")
    ]
    if not selected_percentiles:
        st.warning("Select at least one percentile range.")
        return

    clean_df = df.dropna(subset=["LAP_TIME_SECONDS"])

    fig = go.Figure()
    all_y = []

    for p in selected_percentiles:
        avgs = []
        for driver in selected_drivers:
            driver_df = clean_df[clean_df["DRIVER_NAME"] == driver]
            n_keep = max(1, int(len(driver_df) * p / 100))
            val = driver_df.nsmallest(n_keep, "LAP_TIME_SECONDS")["LAP_TIME_SECONDS"].mean()
            avgs.append(float(val) if not driver_df.empty else None)
            if val is not None:
                all_y.append(float(val))

        fig.add_trace(go.Bar(
            name=f"Top {p}%",
            x=selected_drivers,
            y=avgs,
            text=[f"{v:.3f}" if v is not None else "–" for v in avgs],
            textposition="auto",
        ))

    if all_y:
        pad = (max(all_y) - min(all_y)) * 0.05
        fig.update_yaxes(autorange=False, range=[max(all_y) + pad, max(0, min(all_y) - pad)])

    fig.update_layout(
        barmode="group",
        title="Driver Average Pace by Lap Percentiles",
        xaxis_title="Driver",
        yaxis_title="Average Lap Time (seconds)",
        legend_title="Percentile Range",
    )
    apply_dark_layout(fig)
    st.plotly_chart(fig, use_container_width=True)
