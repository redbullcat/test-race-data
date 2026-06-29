"""top_speed_chart.py — Top speed analysis: max by car, evolution over session."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import apply_dark_layout, build_color_map, sort_cars, chart_export_buttons


def show_top_speed_chart(
    df: pd.DataFrame,
    team_colors: dict,
    key_prefix: str = "ts",
    session_label: str = "Session",
) -> None:
    """Render top speed bar chart + lap-by-lap scatter."""
    st.subheader("Top Speed Analysis")

    if "TOP_SPEED" not in df.columns:
        st.info("Top speed data is not available for this session.")
        return

    dff = df.copy()
    dff["TOP_SPEED"] = pd.to_numeric(dff["TOP_SPEED"], errors="coerce")
    dff = dff.dropna(subset=["TOP_SPEED"])

    if dff.empty:
        st.info("No top speed values found.")
        return

    # ── Outlier filter (per class, 3×IQR Tukey fence) ────────────────────────
    removed: list[dict] = []
    clean_parts = []
    class_col = "CLASS" if "CLASS" in dff.columns else None
    groups = dff.groupby(class_col) if class_col else [("all", dff)]
    for cls, grp in groups:
        q1, q3 = grp["TOP_SPEED"].quantile(0.25), grp["TOP_SPEED"].quantile(0.75)
        cap = q3 + 3.0 * (q3 - q1)
        outliers = grp[grp["TOP_SPEED"] > cap]
        for _, row in outliers.iterrows():
            removed.append({
                "class": cls,
                "car": row["NUMBER"],
                "driver": row.get("DRIVER_NAME", "—"),
                "lap": int(row["LAP_NUMBER"]) if "LAP_NUMBER" in row and pd.notna(row["LAP_NUMBER"]) else "—",
                "speed": row["TOP_SPEED"],
                "cap": round(cap, 1),
            })
        clean_parts.append(grp[grp["TOP_SPEED"] <= cap])
    dff = pd.concat(clean_parts) if clean_parts else dff

    # ── Max speed by car ──────────────────────────────────────────────────────
    st.markdown("#### Maximum Speed by Car")

    max_speed = (
        dff.groupby(["NUMBER", "TEAM"])
        .agg(Max=("TOP_SPEED", "max"), Avg=("TOP_SPEED", "mean"))
        .reset_index()
        .sort_values("Max", ascending=True)
    )
    max_speed["Max"] = max_speed["Max"].round(1)
    max_speed["Avg"] = max_speed["Avg"].round(1)

    color_map = build_color_map(max_speed, team_colors)

    fig_bar = go.Figure()
    for _, row in max_speed.iterrows():
        color = color_map.get(row["TEAM"], "#888888")
        fig_bar.add_trace(go.Bar(
            y=[str(row["NUMBER"])],
            x=[row["Max"]],
            orientation="h",
            name=str(row["NUMBER"]),
            marker_color=color,
            showlegend=False,
            customdata=[[row["TEAM"], row["Avg"]]],
            hovertemplate=(
                "<b>Car %{y}</b> — %{customdata[0][0]}<br>"
                "Max: %{x:.1f} km/h<br>"
                "Avg: %{customdata[0][1]:.1f} km/h<extra></extra>"
            ),
        ))

    cars_y_order = [str(r["NUMBER"]) for _, r in max_speed.iterrows()]  # ascending by max speed
    x_floor = max_speed["Max"].min() * 0.994
    x_ceil  = max_speed["Max"].max() * 1.006
    apply_dark_layout(
        fig_bar,
        title=f"Max Top Speed by Car — {session_label}",
        xaxis=dict(title="Speed (km/h)", range=[x_floor, x_ceil]),
        yaxis=dict(type="category", categoryorder="array", categoryarray=cars_y_order),
        height=max(320, len(max_speed) * 22),
        showlegend=False,
    )
    st.plotly_chart(fig_bar, width="stretch")
    chart_export_buttons(fig=fig_bar, filename=f"{key_prefix}_topspeed_bar")

    # Table
    disp = max_speed.sort_values("Max", ascending=False).reset_index(drop=True)
    disp.insert(0, "Rank", range(1, len(disp) + 1))
    st.dataframe(
        disp.rename(columns={"NUMBER": "Car", "TEAM": "Team",
                              "Max": "Max (km/h)", "Avg": "Avg (km/h)"}),
        hide_index=True, width="stretch",
    )
    chart_export_buttons(df=disp, filename=f"{key_prefix}_topspeed_table")

    if removed:
        lines = []
        for r in removed:
            cls_str = f" ({r['class']})" if r["class"] != "all" else ""
            lines.append(
                f"Car #{r['car']}{cls_str}, lap {r['lap']}: "
                f"**{r['speed']:.1f} km/h** removed — "
                f"exceeds 3×IQR outlier threshold ({r['cap']:.1f} km/h) and is likely a timing system error."
            )
        st.caption("\\* Outlier readings removed from all charts: " + " | ".join(lines))

    # ── Speed over lap / session distance ─────────────────────────────────────
    if "LAP_NUMBER" not in dff.columns:
        return

    st.divider()
    st.markdown("#### Top Speed — Lap by Lap")

    all_cars = sort_cars(dff["NUMBER"].dropna().unique())
    default_sel = all_cars[:12] if len(all_cars) > 12 else all_cars
    selected = st.multiselect(
        "Cars to display",
        all_cars,
        default=default_sel,
        key=f"{key_prefix}_ts_cars",
    )
    if not selected:
        return

    dff_sel = dff[dff["NUMBER"].isin(selected)].dropna(subset=["LAP_NUMBER"]).copy()
    dff_sel["LAP_NUMBER"] = pd.to_numeric(dff_sel["LAP_NUMBER"], errors="coerce")

    fig_scatter = go.Figure()
    for number in selected:
        car_df = dff_sel[dff_sel["NUMBER"] == number].sort_values("LAP_NUMBER")
        if car_df.empty:
            continue
        team = car_df["TEAM"].iloc[0]
        color = color_map.get(team, "#888888")

        fig_scatter.add_trace(go.Scatter(
            x=car_df["LAP_NUMBER"],
            y=car_df["TOP_SPEED"],
            mode="markers",
            name=str(number),
            marker=dict(color=color, size=5, opacity=0.75),
            hovertemplate=(
                f"<b>Car {number}</b><br>"
                "Lap %{x}: %{y:.1f} km/h<extra></extra>"
            ),
        ))

    apply_dark_layout(
        fig_scatter,
        title=f"Top Speed by Lap — {session_label}",
        xaxis=dict(title="Lap"),
        yaxis=dict(title="Speed (km/h)"),
        height=440,
    )
    st.plotly_chart(fig_scatter, width="stretch")
    chart_export_buttons(fig=fig_scatter, filename=f"{key_prefix}_topspeed_scatter")
