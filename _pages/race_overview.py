"""_pages/race_overview.py — Race overview tab: stat cards, class summary, mini charts."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import apply_dark_layout, seconds_to_laptime


_CLASS_COLORS = ["#E00000", "#00C4FF", "#B4E600", "#FF6B00", "#9B59B6", "#1ABC9C"]


def _class_color(i: int) -> str:
    return _CLASS_COLORS[i % len(_CLASS_COLORS)]


def _winner_info(df: pd.DataFrame) -> tuple[str, str]:
    """Return (car_number, team) for the class winner (most laps, earliest elapsed)."""
    if df.empty or "LAP_NUMBER" not in df.columns or "ELAPSED_SECONDS" not in df.columns:
        return "—", "—"
    valid = df.dropna(subset=["LAP_NUMBER", "ELAPSED_SECONDS"])
    if valid.empty:
        return "—", "—"
    idx = valid.groupby("NUMBER")["LAP_NUMBER"].idxmax()
    last = (
        valid.loc[idx]
        .sort_values(["LAP_NUMBER", "ELAPSED_SECONDS"], ascending=[False, True])
    )
    if last.empty:
        return "—", "—"
    top = last.iloc[0]
    return str(int(top["NUMBER"])), str(top.get("TEAM", "—"))


def _fastest_lap_info(df: pd.DataFrame) -> tuple[str, str, str]:
    """Return (laptime_str, car_number, driver) for the session fastest lap."""
    if "LAP_TIME_SECONDS" not in df.columns:
        return "—", "—", "—"
    valid = df.dropna(subset=["LAP_TIME_SECONDS"])
    if valid.empty:
        return "—", "—", "—"
    row = valid.loc[valid["LAP_TIME_SECONDS"].idxmin()]
    return (
        seconds_to_laptime(row["LAP_TIME_SECONDS"]),
        str(int(row["NUMBER"])),
        str(row.get("DRIVER_NAME", "—")),
    )


def _class_top3(df_full: pd.DataFrame, cls: str) -> list[dict]:
    """Return top-3 finishers for a class as list of dicts."""
    cls_df = df_full[df_full["CLASS"] == cls].dropna(subset=["LAP_NUMBER", "ELAPSED_SECONDS"])
    if cls_df.empty:
        return []
    idx = cls_df.groupby("NUMBER")["LAP_NUMBER"].idxmax()
    last = cls_df.loc[idx].sort_values(["LAP_NUMBER", "ELAPSED_SECONDS"], ascending=[False, True])
    result = []
    for _, row in last.head(3).iterrows():
        drivers = " / ".join(sorted(
            cls_df[cls_df["NUMBER"] == row["NUMBER"]]["DRIVER_NAME"].dropna().unique().tolist()
        ))
        best_s = cls_df[cls_df["NUMBER"] == row["NUMBER"]]["LAP_TIME_SECONDS"].min()
        result.append({
            "car": str(int(row["NUMBER"])),
            "team": str(row.get("TEAM", "")),
            "drivers": drivers,
            "best": seconds_to_laptime(best_s) if pd.notna(best_s) else "—",
        })
    return result


def show_race_overview(
    df: pd.DataFrame,
    df_full: pd.DataFrame,
    race_start_date,
    team_colors: dict,
) -> None:
    """Render the race Overview tab."""
    if df is None or df.empty:
        st.info("No race data loaded.")
        return

    # ── Stat cards ─────────────────────────────────────────────────────────────
    winner_car, winner_team = _winner_info(df)
    fl_time, fl_car, fl_driver = _fastest_lap_info(df_full)
    total_laps = int(df["LAP_NUMBER"].max()) if "LAP_NUMBER" in df.columns else 0
    total_cars = int(df_full["NUMBER"].nunique()) if "NUMBER" in df_full.columns else 0
    total_classes = int(df_full["CLASS"].nunique()) if "CLASS" in df_full.columns else 0

    top_speed_val, top_speed_car = "—", "—"
    if "TOP_SPEED" in df_full.columns:
        spd = pd.to_numeric(df_full["TOP_SPEED"], errors="coerce")
        if spd.notna().any():
            top_speed_val = f"{spd.max():.1f} km/h"
            top_speed_car = f"#{df_full.loc[spd.idxmax(), 'NUMBER']}"

    # Allow metric labels and delta text to wrap rather than truncate
    st.markdown("""
        <style>
        [data-testid="stMetricLabel"] p,
        [data-testid="stMetricDelta"] > div { white-space: normal !important; }
        </style>
    """, unsafe_allow_html=True)

    # Wider columns for cards with longer content
    c1, c2, c3, c4, c5, c6 = st.columns([1.2, 1.8, 0.9, 0.9, 0.7, 1.5])
    c1.metric("Winner", f"#{winner_car}", winner_team)
    c2.metric("Fastest Lap", fl_time, f"#{fl_car} · {fl_driver}")
    c3.metric("Total Laps", total_laps)
    c4.metric("Cars Entered", total_cars)
    c5.metric("Classes", total_classes)
    c6.metric("Top Speed", top_speed_val, top_speed_car)

    st.divider()

    # ── Class summary + Top 3 ──────────────────────────────────────────────────
    classes = sorted(df_full["CLASS"].dropna().unique())

    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.markdown("#### Class Summary")
        summary_rows = []
        for cls in classes:
            cls_df = df_full[df_full["CLASS"] == cls].dropna(subset=["LAP_NUMBER", "ELAPSED_SECONDS"])
            if cls_df.empty:
                continue
            cars_n = cls_df["NUMBER"].nunique()
            idx = cls_df.groupby("NUMBER")["LAP_NUMBER"].idxmax()
            last = cls_df.loc[idx].sort_values(["LAP_NUMBER", "ELAPSED_SECONDS"], ascending=[False, True])
            leader = f"#{int(last.iloc[0]['NUMBER'])}" if not last.empty else "—"
            if len(last) >= 2:
                lap_diff = last.iloc[0]["LAP_NUMBER"] - last.iloc[1]["LAP_NUMBER"]
                if lap_diff >= 1:
                    gap = f"+{int(lap_diff)} lap{'s' if lap_diff > 1 else ''}"
                else:
                    gap = f"+{last.iloc[1]['ELAPSED_SECONDS'] - last.iloc[0]['ELAPSED_SECONDS']:.1f}s"
            else:
                gap = "—"
            summary_rows.append({"Class": cls, "Cars": cars_n, "Leader": leader, "Gap to P2": gap})
        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), hide_index=True, width="stretch")

    with col_right:
        st.markdown("#### Top 3 by Class")
        top3_cols = st.columns(len(classes)) if len(classes) > 1 else [st.container()]
        for i, cls in enumerate(classes):
            with top3_cols[i]:
                st.markdown(f"**{cls}**")
                for pos, entry in enumerate(_class_top3(df_full, cls), 1):
                    team_short = entry["team"][:18]
                    st.write(f"**{pos}.** #{entry['car']} {team_short}")
                    st.caption(f"{entry['best']}")

    st.divider()

    # ── Mini charts row ─────────────────────────────────────────────────────────
    col_pace, col_speed = st.columns(2)

    with col_pace:
        st.markdown("#### Pace by Class")
        if "LAP_TIME_SECONDS" in df_full.columns and not df_full["LAP_TIME_SECONDS"].dropna().empty:
            fig = go.Figure()
            for i, cls in enumerate(classes):
                times = df_full[df_full["CLASS"] == cls]["LAP_TIME_SECONDS"].dropna()
                if times.empty:
                    continue
                color = _class_color(i)
                fig.add_trace(go.Box(
                    y=times,
                    name=cls,
                    marker_color=color,
                    line=dict(color=color, width=1.5),
                    boxpoints=False,
                    hovertemplate=f"<b>{cls}</b><br>%{{y:.3f}}s<extra></extra>",
                ))
            if fig.data:
                all_t = df_full["LAP_TIME_SECONDS"].dropna()
                y_lo, y_hi = all_t.quantile(0.01), all_t.quantile(0.99)
                pad = (y_hi - y_lo) * 0.08
                step = 5.0
                tick_vals = list(np.arange(np.floor(y_lo / step) * step, y_hi + step, step))
                apply_dark_layout(
                    fig,
                    title="",
                    yaxis=dict(
                        tickvals=tick_vals,
                        ticktext=[seconds_to_laptime(v) for v in tick_vals],
                        range=[y_lo - pad, y_hi + pad],
                    ),
                    height=300,
                    margin=dict(l=70, r=20, t=10, b=40),
                )
                st.plotly_chart(fig, width="stretch")

    with col_speed:
        st.markdown("#### Max Top Speed by Class")
        if "TOP_SPEED" in df_full.columns:
            rows = []
            for cls in classes:
                spd = pd.to_numeric(df_full[df_full["CLASS"] == cls]["TOP_SPEED"], errors="coerce").dropna()
                if not spd.empty:
                    q1, q3 = spd.quantile(0.25), spd.quantile(0.75)
                    spd = spd[spd <= q3 + 3.0 * (q3 - q1)]
                    rows.append({"Class": cls, "Max": round(spd.max(), 1), "Avg": round(spd.mean(), 1)})
            if rows:
                spd_df = pd.DataFrame(rows)
                fig2 = go.Figure()
                for i, (_, row) in enumerate(spd_df.iterrows()):
                    color = _class_color(i)
                    fig2.add_trace(go.Bar(
                        x=[row["Class"]],
                        y=[row["Max"]],
                        name=row["Class"],
                        marker_color=color,
                        showlegend=False,
                        customdata=[[row["Avg"]]],
                        hovertemplate=(
                            f"<b>{row['Class']}</b><br>"
                            "Max: %{y:.1f} km/h<br>"
                            "Avg: %{customdata[0][0]:.1f} km/h<extra></extra>"
                        ),
                    ))
                y_floor = spd_df["Max"].min() * 0.97
                apply_dark_layout(
                    fig2,
                    title="",
                    yaxis=dict(title="km/h", range=[y_floor, spd_df["Max"].max() * 1.02]),
                    height=300,
                    margin=dict(l=60, r=20, t=10, b=40),
                )
                st.plotly_chart(fig2, width="stretch")

    # ── Pit stop summary ────────────────────────────────────────────────────────
    pit_col = next((c for c in ("PIT_TIME", "PIT_DURATION") if c in df_full.columns), None)
    if pit_col:
        pits = df_full.copy()
        pits[pit_col] = pd.to_numeric(pits[pit_col], errors="coerce")
        pits = pits.dropna(subset=[pit_col])
        if not pits.empty:
            st.divider()
            st.markdown("#### Pit Stop Summary")
            pc1, pc2, pc3, pc4 = st.columns(4)
            pc1.metric("Total Stops", len(pits))
            pc2.metric("Avg Stop Time", f"{pits[pit_col].mean():.1f}s")
            fp = pits.loc[pits[pit_col].idxmin()]
            pc3.metric("Fastest Stop", f"{fp[pit_col]:.1f}s", f"#{int(fp['NUMBER'])}")
            most_n = pits.groupby("NUMBER").size()
            pc4.metric("Most Stops", f"#{int(most_n.idxmax())}", f"{most_n.max()} stops")
