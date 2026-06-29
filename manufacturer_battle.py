"""manufacturer_battle.py — Manufacturer performance charts.

Shows laps completed, pace distribution (box plot), and top speed per manufacturer.
Works for practice, qualifying, and race data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (
    apply_dark_layout, seconds_to_laptime, filter_top_percent, chart_export_buttons,
)
from theme import RED


def _hex_to_rgba(hex_color: str, alpha: float = 0.33) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

# Colour palette distinct from team colours (qualitative set)
_MFR_COLORS = [
    "#E00000", "#00C4FF", "#B4E600", "#FF6B00", "#9B59B6",
    "#1ABC9C", "#F39C12", "#FFFFFF", "#888888", "#FF69B4",
    "#00FA9A", "#FF4500", "#7B68EE", "#20B2AA", "#DAA520",
]


def _mfr_color_map(manufacturers: list[str]) -> dict[str, str]:
    return {m: _MFR_COLORS[i % len(_MFR_COLORS)] for i, m in enumerate(sorted(manufacturers))}


def show_manufacturer_battle(
    df: pd.DataFrame,
    team_colors: dict,
    key_prefix: str = "mfr",
) -> None:
    """Full manufacturer analysis: laps completed, pace, top speed."""
    if "MANUFACTURER" not in df.columns:
        st.info("Manufacturer data is not available for this session.")
        return

    df = df.copy()
    df["MANUFACTURER"] = df["MANUFACTURER"].astype(str).str.strip()
    # Drop rows where manufacturer is empty/nan
    df = df[df["MANUFACTURER"].notna() & (df["MANUFACTURER"] != "") & (df["MANUFACTURER"] != "nan")]

    if df.empty:
        st.info("No manufacturer data after filtering.")
        return

    mfr_list = sorted(df["MANUFACTURER"].unique())
    cmap = _mfr_color_map(mfr_list)

    laps_tab, pace_tab, speed_tab = st.tabs(["Laps Completed", "Pace Comparison", "Top Speed"])

    with laps_tab:
        _show_laps_by_manufacturer(df, cmap, key_prefix)

    with pace_tab:
        _show_manufacturer_pace(df, cmap, key_prefix)

    with speed_tab:
        _show_manufacturer_speed(df, cmap, key_prefix)


# ---------------------------------------------------------------------------
# Sub-charts
# ---------------------------------------------------------------------------

def _show_laps_by_manufacturer(df: pd.DataFrame, cmap: dict, key_prefix: str) -> None:
    laps = (
        df.groupby("MANUFACTURER")
        .agg(Total_Laps=("LAP_NUMBER", "count"), Cars=("NUMBER", "nunique"))
        .reset_index()
        .sort_values("Total_Laps", ascending=True)
    )
    laps["Avg_Per_Car"] = (laps["Total_Laps"] / laps["Cars"]).round(1)

    fig = go.Figure()
    for _, row in laps.iterrows():
        fig.add_trace(go.Bar(
            y=[row["MANUFACTURER"]],
            x=[row["Total_Laps"]],
            orientation="h",
            name=row["MANUFACTURER"],
            marker_color=cmap.get(row["MANUFACTURER"], "#888888"),
            customdata=[[row["Cars"], row["Avg_Per_Car"]]],
            hovertemplate=(
                f"<b>{row['MANUFACTURER']}</b><br>"
                "Total laps: %{x}<br>"
                "Cars entered: %{customdata[0][0]}<br>"
                "Avg laps/car: %{customdata[0][1]}<extra></extra>"
            ),
        ))

    apply_dark_layout(
        fig,
        title="Total Laps Completed by Manufacturer",
        xaxis=dict(title="Laps"),
        showlegend=False,
        height=max(260, len(laps) * 52),
    )
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(fig=fig, filename=f"{key_prefix}_mfr_laps")

    st.dataframe(
        laps.rename(columns={
            "MANUFACTURER": "Manufacturer",
            "Total_Laps": "Total Laps",
            "Cars": "Cars",
            "Avg_Per_Car": "Avg Laps / Car",
        }).sort_values("Total Laps", ascending=False).reset_index(drop=True),
        hide_index=True,
        width="stretch",
    )
    chart_export_buttons(df=laps, filename=f"{key_prefix}_mfr_laps_table")


def _show_manufacturer_pace(df: pd.DataFrame, cmap: dict, key_prefix: str) -> None:
    if "LAP_TIME_SECONDS" not in df.columns:
        st.info("Lap time data not available.")
        return

    top_pct = st.slider(
        "Top lap %", 20, 100, 85, step=5, key=f"{key_prefix}_mfr_pct",
        help="Filters out SC/FCY laps and traffic — shows representative race pace.",
    )

    dff = filter_top_percent(df.dropna(subset=["LAP_TIME_SECONDS"]).copy(), top_pct)

    if dff.empty:
        st.warning("No data after filtering.")
        return

    median_order = (
        dff.groupby("MANUFACTURER")["LAP_TIME_SECONDS"].median()
        .sort_values().index.tolist()
    )

    # Y-axis with lap-time labels
    y_min = dff["LAP_TIME_SECONDS"].min()
    y_max = dff["LAP_TIME_SECONDS"].max()
    span = y_max - y_min
    step = 1.0 if span <= 5 else 2.0 if span <= 15 else 5.0 if span <= 60 else 10.0
    tick_vals = list(np.arange(np.floor(y_min / step) * step, y_max + step, step))
    tick_text = [seconds_to_laptime(v) for v in tick_vals]

    fig = go.Figure()
    for mfr in median_order:
        mfr_df = dff[dff["MANUFACTURER"] == mfr]
        color = cmap.get(mfr, "#888888")
        fig.add_trace(go.Box(
            y=mfr_df["LAP_TIME_SECONDS"],
            name=mfr,
            marker_color=color,
            line=dict(color=color, width=1.5),
            fillcolor=_hex_to_rgba(color, 0.33),
            boxpoints="outliers",
            hovertemplate=f"<b>{mfr}</b><br>%{{y:.3f}}s<extra></extra>",
        ))

    apply_dark_layout(
        fig,
        title="Pace Distribution by Manufacturer",
        yaxis=dict(tickvals=tick_vals, ticktext=tick_text,
                   range=[y_min - step * 0.5, y_max + step * 0.5]),
        height=460,
    )
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(fig=fig, filename=f"{key_prefix}_mfr_pace")


def _show_manufacturer_speed(df: pd.DataFrame, cmap: dict, key_prefix: str) -> None:
    if "TOP_SPEED" not in df.columns:
        st.info("Top speed data is not available for this session.")
        return

    dff = df.copy()
    dff["TOP_SPEED"] = pd.to_numeric(dff["TOP_SPEED"], errors="coerce")
    dff = dff.dropna(subset=["TOP_SPEED"])

    if dff.empty:
        st.info("No top speed values found.")
        return

    # 3×IQR outlier filter applied per class so mixed-class data doesn't
    # widen the fence and miss within-class spikes.
    removed_mfr = []
    clean_parts = []
    class_col = "CLASS" if "CLASS" in dff.columns else None
    groups = dff.groupby(class_col) if class_col else [("all", dff)]
    _caps: dict[str, float] = {}
    for cls, grp in groups:
        q1, q3 = grp["TOP_SPEED"].quantile(0.25), grp["TOP_SPEED"].quantile(0.75)
        cap = q3 + 3.0 * (q3 - q1)
        _caps[str(cls)] = round(cap, 1)
        removed_mfr.append(grp[grp["TOP_SPEED"] > cap])
        clean_parts.append(grp[grp["TOP_SPEED"] <= cap])
    removed_mfr = pd.concat(removed_mfr) if removed_mfr else pd.DataFrame()
    dff = pd.concat(clean_parts) if clean_parts else dff

    stats = (
        dff.groupby("MANUFACTURER")
        .agg(Max=("TOP_SPEED", "max"), Avg=("TOP_SPEED", "mean"), Count=("TOP_SPEED", "count"))
        .reset_index()
        .sort_values("Max", ascending=False)
    )
    stats["Max"] = stats["Max"].round(1)
    stats["Avg"] = stats["Avg"].round(1)

    fig = go.Figure()
    for _, row in stats.iterrows():
        color = cmap.get(row["MANUFACTURER"], "#888888")
        fig.add_trace(go.Bar(
            x=[row["MANUFACTURER"]],
            y=[row["Max"]],
            name=row["MANUFACTURER"],
            marker_color=color,
            customdata=[[row["Avg"], int(row["Count"])]],
            hovertemplate=(
                f"<b>{row['MANUFACTURER']}</b><br>"
                "Max speed: %{y:.1f} km/h<br>"
                "Avg speed: %{customdata[0][0]:.1f} km/h<br>"
                "Laps sampled: %{customdata[0][1]}<extra></extra>"
            ),
        ))

    y_floor = stats["Max"].min() * 0.985
    apply_dark_layout(
        fig,
        title="Maximum Top Speed by Manufacturer",
        yaxis=dict(title="Speed (km/h)", range=[y_floor, stats["Max"].max() * 1.015]),
        showlegend=False,
        height=380,
    )
    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(fig=fig, filename=f"{key_prefix}_mfr_speed")

    st.dataframe(
        stats.rename(columns={
            "MANUFACTURER": "Manufacturer",
            "Max": "Max Speed (km/h)",
            "Avg": "Avg Speed (km/h)",
            "Count": "Laps sampled",
        }).reset_index(drop=True),
        hide_index=True,
        width="stretch",
    )
    chart_export_buttons(df=stats, filename=f"{key_prefix}_mfr_speed_table")

    if not removed_mfr.empty:
        notes = []
        for _, r in removed_mfr.iterrows():
            lap = int(r["LAP_NUMBER"]) if "LAP_NUMBER" in r and pd.notna(r.get("LAP_NUMBER")) else "—"
            cls_key = str(r["CLASS"]) if class_col and "CLASS" in r else "all"
            threshold = _caps.get(cls_key, "—")
            notes.append(
                f"Car #{r['NUMBER']} ({r.get('MANUFACTURER', '—')}), lap {lap}: "
                f"**{r['TOP_SPEED']:.1f} km/h** removed — "
                f"exceeds 3×IQR outlier threshold ({threshold} km/h) and is likely a timing system error."
            )
        st.caption("\\* Outlier readings removed: " + " | ".join(notes))
