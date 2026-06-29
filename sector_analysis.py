"""sector_analysis.py — Sector time analysis for practice, qualifying and race."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (apply_dark_layout, build_color_map, sort_cars,
                   seconds_to_laptime, lap_to_seconds, chart_export_buttons)
from theme import RED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_sector_seconds(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure S1/S2/S3 _SECONDS columns exist as floats.
    Falls back to parsing the formatted S1/S2/S3 string columns if needed."""
    df = df.copy()
    for n in (1, 2, 3):
        sec_col = f"S{n}_SECONDS"
        str_col = f"S{n}"
        if sec_col in df.columns:
            df[sec_col] = pd.to_numeric(df[sec_col], errors="coerce")
        elif str_col in df.columns:
            df[sec_col] = df[str_col].apply(lap_to_seconds)
    return df


def _nice_tick_step(span: float) -> float:
    if span <= 5:   return 1.0
    if span <= 15:  return 2.0
    if span <= 60:  return 5.0
    return 10.0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def show_sector_analysis(
    df: pd.DataFrame,
    team_colors: dict,
    key_prefix: str = "sec",
) -> None:
    """Render full sector analysis section."""
    df = _ensure_sector_seconds(df)

    has_sectors = all(c in df.columns for c in ("S1_SECONDS", "S2_SECONDS", "S3_SECONDS"))
    if not has_sectors:
        st.info("Sector time data is not available for this session.")
        return

    df_sec = df.dropna(subset=["S1_SECONDS", "S2_SECONDS", "S3_SECONDS"]).copy()
    df_sec["LAP_TIME_SECONDS"] = pd.to_numeric(
        df_sec.get("LAP_TIME_SECONDS", pd.Series(dtype=float)), errors="coerce"
    )

    if df_sec.empty:
        st.info("No rows with complete sector times found.")
        return

    all_cars = sort_cars(df_sec["NUMBER"].dropna().unique())
    selected_cars = st.multiselect(
        "Cars", all_cars, default=all_cars, key=f"{key_prefix}_sec_cars"
    )
    if not selected_cars:
        return
    df_sec = df_sec[df_sec["NUMBER"].isin(selected_cars)]

    st.markdown("### Best Sector Times")
    _show_sector_comparison(df_sec, team_colors, key_prefix)

    st.divider()
    st.markdown("### Theoretical Best Lap")
    _show_theoretical_best(df_sec, team_colors, key_prefix)

    st.divider()
    st.markdown("### Sector Delta vs Benchmark")
    _show_sector_delta_heatmap(df_sec, key_prefix)

    if "LAP_NUMBER" in df_sec.columns:
        st.divider()
        st.markdown("### Sector Evolution")
        _show_sector_evolution(df_sec, team_colors, key_prefix)


# ---------------------------------------------------------------------------
# Sub-charts
# ---------------------------------------------------------------------------

def _show_sector_comparison(df: pd.DataFrame, team_colors: dict, key_prefix: str) -> None:
    """Grouped bar: best S1, S2, S3 per car."""
    best = (
        df.groupby(["NUMBER", "TEAM"], as_index=False)
        .agg(S1=("S1_SECONDS", "min"), S2=("S2_SECONDS", "min"), S3=("S3_SECONDS", "min"))
    )
    cars_ordered = sort_cars(best.sort_values("S1")["NUMBER"].tolist())
    best["NUMBER"] = pd.Categorical(best["NUMBER"], categories=cars_ordered, ordered=True)
    best = best.sort_values("NUMBER")

    sector_colors = [RED, "#00C4FF", "#B4E600"]
    fig = go.Figure()
    for sector, color in zip(["S1", "S2", "S3"], sector_colors):
        fig.add_trace(go.Bar(
            name=sector,
            x=best["NUMBER"].astype(str),
            y=best[sector],
            marker_color=color,
            customdata=best[["TEAM", sector]].values,
            hovertemplate=(
                "<b>Car %{x}</b> (%{customdata[0]})<br>"
                "%{fullData.name}: %{y:.3f}s<extra></extra>"
            ),
        ))

    cars_str = [str(c) for c in cars_ordered]
    fig.update_layout(barmode="group")
    apply_dark_layout(
        fig,
        title="Best Sector Times by Car",
        xaxis=dict(type="category", categoryorder="array", categoryarray=cars_str),
        height=400,
    )
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(fig=fig, filename=f"{key_prefix}_sector_comparison", height=400)


def _show_theoretical_best(df: pd.DataFrame, team_colors: dict, key_prefix: str) -> None:
    """Bar: theoretical best (Σ best sectors) vs actual fastest lap, with gap table."""
    best = (
        df.groupby(["NUMBER", "TEAM"], as_index=False)
        .agg(
            S1=("S1_SECONDS", "min"), S2=("S2_SECONDS", "min"), S3=("S3_SECONDS", "min"),
            Actual=("LAP_TIME_SECONDS", "min"),
        )
    )
    best["Theoretical"] = best["S1"] + best["S2"] + best["S3"]
    best["Gap"] = (best["Actual"] - best["Theoretical"]).round(3)
    best = best.sort_values("Theoretical")

    color_map = build_color_map(best, team_colors)

    fig = go.Figure()
    for _, row in best.iterrows():
        color = color_map.get(row["TEAM"], "#888888")
        fig.add_trace(go.Bar(
            name=str(row["NUMBER"]),
            x=[str(row["NUMBER"])],
            y=[row["Theoretical"]],
            marker_color=color,
            showlegend=False,
            customdata=[[row["TEAM"], row["Theoretical"], row["Actual"], row["Gap"]]],
            hovertemplate=(
                "<b>Car %{x}</b> (%{customdata[0][0]})<br>"
                "Theoretical: %{customdata[0][1]:.3f}s<br>"
                "Actual fastest: %{customdata[0][2]:.3f}s<br>"
                "Gap: +%{customdata[0][3]:.3f}s<extra></extra>"
            ),
        ))

    # Actual fastest as horizontal tick marks
    fig.add_trace(go.Scatter(
        x=best["NUMBER"].astype(str),
        y=best["Actual"],
        mode="markers",
        marker=dict(symbol="line-ew", size=16, color="white",
                    line=dict(width=2, color="white")),
        name="Actual fastest",
        hoverinfo="skip",
    ))

    cars_in_order = [str(r["NUMBER"]) for _, r in best.iterrows()]
    y_min = best["Theoretical"].min() - 0.5
    y_max = best["Actual"].max() + 0.5
    apply_dark_layout(
        fig,
        title="Theoretical Best vs Actual Fastest Lap  (white bar = actual)",
        xaxis=dict(type="category", categoryorder="array", categoryarray=cars_in_order),
        yaxis=dict(range=[y_min, y_max]),
        height=420,
    )
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(fig=fig, filename=f"{key_prefix}_theoretical_best", height=420)

    # Table
    disp = best.copy()
    disp["Theoretical"] = disp["Theoretical"].apply(seconds_to_laptime)
    disp["Actual"] = disp["Actual"].apply(seconds_to_laptime)
    disp["Gap"] = disp["Gap"].apply(lambda x: f"+{x:.3f}s" if not pd.isna(x) else "")
    st.dataframe(
        disp.rename(columns={"NUMBER": "Car", "TEAM": "Team"})[
            ["Car", "Team", "Theoretical", "Actual", "Gap"]
        ],
        hide_index=True, width="stretch",
    )
    chart_export_buttons(
        df=disp.rename(columns={"NUMBER": "Car", "TEAM": "Team"})[
            ["Car", "Team", "Theoretical", "Actual", "Gap"]
        ],
        filename=f"{key_prefix}_theoretical_best_table",
    )


def _show_sector_delta_heatmap(df: pd.DataFrame, key_prefix: str) -> None:
    """Heatmap: each car's best sector delta vs the session benchmark."""
    best = (
        df.groupby("NUMBER", as_index=False)
        .agg(S1=("S1_SECONDS", "min"), S2=("S2_SECONDS", "min"), S3=("S3_SECONDS", "min"))
    )
    best = best.sort_values("S1")

    bm_s1 = best["S1"].min()
    bm_s2 = best["S2"].min()
    bm_s3 = best["S3"].min()

    best["ΔS1"] = (best["S1"] - bm_s1).round(3)
    best["ΔS2"] = (best["S2"] - bm_s2).round(3)
    best["ΔS3"] = (best["S3"] - bm_s3).round(3)

    cars = best["NUMBER"].astype(str).tolist()
    z = best[["ΔS1", "ΔS2", "ΔS3"]].values.T
    text = [[f"+{v:.3f}s" if v > 0 else "P" for v in row] for row in z]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=cars,
        y=["Sector 1", "Sector 2", "Sector 3"],
        text=text,
        texttemplate="%{text}",
        colorscale=[[0, "#0d3320"], [0.35, "#1a6640"], [0.5, "#111111"], [0.65, "#8b1a1a"], [1, "#cc0000"]],
        zmid=0,
        colorbar=dict(title="Gap (s)", thickness=12, tickfont=dict(size=10)),
        hovertemplate="Car %{x}<br>%{y}<br>%{text}<extra></extra>",
    ))
    apply_dark_layout(
        fig,
        title="Sector Delta vs Session Benchmark  (green = faster, P = benchmark holder)",
        height=260,
        margin=dict(l=80, r=60, t=56, b=48),
    )
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(fig=fig, filename=f"{key_prefix}_sector_delta_heatmap", height=260)


def _show_sector_evolution(df: pd.DataFrame, team_colors: dict, key_prefix: str) -> None:
    """Line chart: how a chosen sector improves lap-by-lap."""
    df = df.dropna(subset=["LAP_NUMBER"]).copy()
    df["LAP_NUMBER"] = pd.to_numeric(df["LAP_NUMBER"], errors="coerce")

    sector = st.selectbox(
        "Sector to plot",
        ["S1_SECONDS", "S2_SECONDS", "S3_SECONDS"],
        format_func=lambda x: x.replace("_SECONDS", ""),
        key=f"{key_prefix}_sec_evol_sector",
    )

    color_map = build_color_map(df, team_colors)
    fig = go.Figure()

    for (number, team), car_df in df.groupby(["NUMBER", "TEAM"]):
        car_df = car_df.sort_values("LAP_NUMBER").dropna(subset=[sector])
        if car_df.empty:
            continue
        fig.add_trace(go.Scatter(
            x=car_df["LAP_NUMBER"],
            y=car_df[sector],
            mode="lines+markers",
            name=str(number),
            line=dict(color=color_map.get(team, "#888888"), width=1.5),
            marker=dict(size=4),
            hovertemplate=(
                f"<b>Car {number}</b><br>"
                "Lap %{x}<br>"
                f"{sector.replace('_SECONDS', '')}: %{{y:.3f}}s<extra></extra>"
            ),
        ))

    sector_label = sector.replace("_SECONDS", "")
    apply_dark_layout(
        fig,
        title=f"{sector_label} — Lap-by-Lap",
        xaxis=dict(title="Lap"),
        yaxis=dict(title=f"{sector_label} (s)"),
        height=420,
    )
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(fig=fig, filename=f"{key_prefix}_sector_evolution", height=420)
