"""
pace_consistency_chart.py — Pace vs consistency scatter chart.

Plots average clean-lap pace (x) vs standard deviation (y) for each car,
making it immediately visible who was fast-but-erratic vs slow-but-consistent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import apply_dark_layout, build_color_map, seconds_to_laptime, chart_export_buttons


@st.cache_data(show_spinner=False)
def _compute_pace_consistency(df: pd.DataFrame, top_percent: int = 100) -> pd.DataFrame:
    """
    For each car, compute:
      - mean of clean laps (within 105% of car's own median)
      - std dev of those laps
    Returns DataFrame with NUMBER, TEAM, CLASS, Avg Pace, Std Dev, Lap Count.
    """
    df = df.dropna(subset=["LAP_TIME_SECONDS"]).copy()
    # Remove obvious outlier laps (SC, pit, slow outlap) per car
    medians = df.groupby("NUMBER")["LAP_TIME_SECONDS"].transform("median")
    clean = df[df["LAP_TIME_SECONDS"] <= medians * 1.05]

    if top_percent < 100:
        parts = []
        for car, g in clean.groupby("NUMBER"):
            n = max(1, int(len(g) * top_percent / 100))
            parts.append(g.nsmallest(n, "LAP_TIME_SECONDS"))
        clean = pd.concat(parts) if parts else clean

    stats = (
        clean.groupby(["NUMBER", "TEAM", "CLASS"])["LAP_TIME_SECONDS"]
        .agg(["mean", "std", "count"])
        .reset_index()
        .rename(columns={"mean": "Avg Pace (s)", "std": "Std Dev (s)", "count": "Laps"})
    )
    stats = stats.dropna(subset=["Std Dev (s)"])
    stats["Avg Pace (s)"] = stats["Avg Pace (s)"].round(3)
    stats["Std Dev (s)"] = stats["Std Dev (s)"].round(3)
    return stats


def show_pace_consistency_chart(df: pd.DataFrame, team_colors: dict) -> None:
    st.subheader("Pace vs Consistency")
    st.caption(
        "Lower left = fastest and most consistent. "
        "X-axis: average clean lap time. Y-axis: standard deviation (lower = more consistent)."
    )

    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Class:", classes, key="pc_class")

    top_pct = st.slider(
        "Top lap %:", 50, 100, 100, step=10, key="pc_top_pct",
        help="Restrict analysis to each car's fastest N% of laps."
    )

    class_df = df[df["CLASS"] == selected_class].copy()
    stats = _compute_pace_consistency(class_df, top_pct)

    if stats.empty or len(stats) < 2:
        st.info("Not enough data to plot pace vs consistency.")
        return

    color_map = build_color_map(stats, team_colors)
    stats["Label"] = stats["NUMBER"] + " — " + stats["TEAM"]
    stats["Color"] = stats["TEAM"].map(color_map).fillna("#888888")

    # Quadrant lines (medians)
    med_pace = stats["Avg Pace (s)"].median()
    med_std  = stats["Std Dev (s)"].median()

    fig = go.Figure()

    # Quadrant shading
    x_min = stats["Avg Pace (s)"].min() - 0.5
    x_max = stats["Avg Pace (s)"].max() + 0.5
    y_min = 0
    y_max = stats["Std Dev (s)"].max() * 1.2

    quadrants = [
        (x_min, med_pace, y_min, med_std,  "rgba(0,180,0,0.06)",   "Fast & Consistent"),
        (med_pace, x_max, y_min, med_std,  "rgba(255,165,0,0.06)", "Slow & Consistent"),
        (x_min, med_pace, med_std, y_max,  "rgba(255,165,0,0.06)", "Fast & Erratic"),
        (med_pace, x_max, med_std, y_max,  "rgba(200,0,0,0.06)",   "Slow & Erratic"),
    ]
    for x0, x1, y0, y1, color, label in quadrants:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=color, line_width=0, layer="below")

    # Quadrant labels
    for (x0, x1, y0, y1, _, label) in quadrants:
        fig.add_annotation(
            x=(x0 + x1) / 2, y=(y0 + y1) / 2,
            text=label, showarrow=False,
            font=dict(color="rgba(200,200,200,0.4)", size=11),
        )

    # Cars
    for _, row in stats.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["Avg Pace (s)"]],
            y=[row["Std Dev (s)"]],
            mode="markers+text",
            name=row["Label"],
            text=[row["NUMBER"]],
            textposition="top center",
            textfont=dict(color="white", size=11),
            marker=dict(color=row["Color"], size=14, line=dict(color="white", width=1)),
            customdata=[[row["Label"], row["Laps"], seconds_to_laptime(row["Avg Pace (s)"])]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Avg pace: %{customdata[2]}<br>"
                "Std dev: %{y:.3f}s<br>"
                "Clean laps: %{customdata[1]}"
                "<extra></extra>"
            ),
            showlegend=False,
        ))

    # Median crosshairs
    fig.add_hline(y=med_std, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    fig.add_vline(x=med_pace, line_dash="dot", line_color="rgba(255,255,255,0.3)")

    fig.update_layout(
        title=f"Pace vs Consistency — {selected_class}",
        xaxis_title="Average Clean Lap Time (s) →  slower",
        yaxis_title="Lap Time Std Dev (s) →  less consistent",
        xaxis=dict(range=[x_min, x_max]),
        yaxis=dict(range=[y_min, y_max]),
    )
    apply_dark_layout(fig, title_font=dict(size=22))
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(fig=fig, filename="pace_consistency_chart", height=500)
