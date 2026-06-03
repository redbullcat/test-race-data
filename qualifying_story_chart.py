"""qualifying_story_chart.py — Sector-by-sector gap chart for qualifying sessions."""

from __future__ import annotations

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from utils import (
    apply_dark_layout,
    build_color_map,
    chart_export_buttons,
    lap_to_seconds,
    sort_cars,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sector_to_seconds(value) -> float | None:
    """
    Parse a sector time to seconds. Al-Kamel sector times (S1/S2/S3) are
    typically plain 'SS.sss' floats, but may also be 'M:SS.sss' strings.
    Returns None for anything unparseable.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", ""):
        return None
    try:
        # Plain float / integer seconds: "23.456" or "23"
        return float(s)
    except ValueError:
        pass
    # Fall back to lap_to_seconds for M:SS.sss format
    return lap_to_seconds(s)


def _parse_sectors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse S1, S2, S3 columns to seconds and add S1_S, S2_S, S3_S.
    Also computes LAP_TIME_SECONDS if not already present.
    """
    df = df.copy()
    for col, out in [("S1", "S1_S"), ("S2", "S2_S"), ("S3", "S3_S")]:
        if col in df.columns:
            df[out] = df[col].apply(_sector_to_seconds)
        else:
            df[out] = None
    if "LAP_TIME_SECONDS" not in df.columns:
        df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
    return df


def _fastest_lap_per_car(df: pd.DataFrame) -> dict[str, int]:
    """Return {car: lap_number} of each car's fastest lap."""
    result = {}
    for car, grp in df.groupby("NUMBER"):
        valid = grp.dropna(subset=["LAP_TIME_SECONDS"])
        if valid.empty:
            continue
        idx = valid["LAP_TIME_SECONDS"].idxmin()
        result[str(car)] = int(valid.loc[idx, "LAP_NUMBER"])
    return result


def _build_gap_trace(
    df: pd.DataFrame,
    car: str,
    lap_number: int,
    ref_splits: list[float],   # [s1_ref, s1+s2_ref, s1+s2+s3_ref]
    color: str,
    label: str,
    show_fill: bool = True,
) -> list[go.Scatter]:
    """
    Build Plotly traces for one car/lap against reference splits.
    Returns a list (fill trace + line trace).
    """
    row = df[(df["NUMBER"] == car) & (df["LAP_NUMBER"] == lap_number)]
    if row.empty:
        return []

    row = row.iloc[0]
    s1 = row.get("S1_S")
    s2 = row.get("S2_S")
    s3 = row.get("S3_S")

    if pd.isna(s1) or pd.isna(s2) or pd.isna(s3):
        return []

    cum = [s1, s1 + s2, s1 + s2 + s3]
    gaps = [c - r for c, r in zip(cum, ref_splits)]

    # Prepend zero origin so the line starts at (0, 0)
    x_vals = [0.0] + ref_splits
    y_vals = [0.0] + gaps

    traces = []
    if show_fill:
        traces.append(go.Scatter(
            x=x_vals,
            y=y_vals,
            fill="tozeroy",
            fillcolor=color.replace(")", ", 0.20)").replace("rgb(", "rgba(")
                       if color.startswith("rgb(")
                       else color + "33",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ))

    traces.append(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode="lines+markers",
        name=label,
        line=dict(color=color, width=2.5),
        marker=dict(size=7),
        hovertemplate=(
            "Sector end: %{x:.3f}s<br>"
            "Gap: %{y:+.3f}s<br>"
            f"{label}<extra></extra>"
        ),
    ))
    return traces


def _rgba(hex_color: str, alpha: float = 0.20) -> str:
    """Convert #rrggbb hex to rgba string."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    return hex_color


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def show_qualifying_story(
    df: pd.DataFrame,
    team_colors: dict,
    session_files: list[str],
    key_prefix: str = "qual_story",
) -> None:
    """
    Render the qualifying story (sector gap) chart.
    df should be the combined qualifying dataframe already loaded.
    """
    if df.empty:
        st.info("No qualifying data loaded.")
        return

    df = _parse_sectors(df)

    # Remove laps missing all sector data
    has_sectors = df[["S1_S", "S2_S", "S3_S"]].notna().all(axis=1)
    df_s = df[has_sectors].copy()

    if df_s.empty:
        st.warning("No sector time data found in qualifying files (S1/S2/S3 columns missing or empty).")
        return

    # ── Session filter ────────────────────────────────────────────────────
    sessions = sorted(df_s["PRACTICE_SESSION"].dropna().unique())
    if len(sessions) > 1:
        st.markdown("**Sessions**")
        sel_sessions = []
        cols = st.columns(len(sessions))
        for i, sess in enumerate(sessions):
            if cols[i].checkbox(sess, value=True, key=f"{key_prefix}_sess_{i}"):
                sel_sessions.append(sess)
        if not sel_sessions:
            st.warning("No sessions selected.")
            return
        df_s = df_s[df_s["PRACTICE_SESSION"].isin(sel_sessions)]
    else:
        sel_sessions = sessions

    # ── Class filter ──────────────────────────────────────────────────────
    classes = sorted(df_s["CLASS"].dropna().unique())
    selected_class = st.selectbox(
        "Class", classes, key=f"{key_prefix}_class"
    )
    df_cls = df_s[df_s["CLASS"] == selected_class].copy()

    if df_cls.empty:
        st.info("No data for selected class.")
        return

    # ── Colour map ────────────────────────────────────────────────────────
    car_colors = build_color_map(df_cls, team_colors)

    # ── Reference selection ───────────────────────────────────────────────
    # Find overall fastest lap in class
    valid = df_cls.dropna(subset=["LAP_TIME_SECONDS", "S1_S", "S2_S", "S3_S"])
    if valid.empty:
        st.warning("No valid laps with sector data.")
        return

    fastest_idx   = valid["LAP_TIME_SECONDS"].idxmin()
    fastest_car   = str(valid.loc[fastest_idx, "NUMBER"])
    fastest_lap   = int(valid.loc[fastest_idx, "LAP_NUMBER"])
    fastest_row   = valid.loc[fastest_idx]
    default_ref_splits = [
        fastest_row["S1_S"],
        fastest_row["S1_S"] + fastest_row["S2_S"],
        fastest_row["S1_S"] + fastest_row["S2_S"] + fastest_row["S3_S"],
    ]

    use_ref_car = st.checkbox(
        "Use a specific car as reference (instead of fastest lap)",
        value=False,
        key=f"{key_prefix}_use_ref",
    )

    all_cars = sort_cars(df_cls["NUMBER"].unique())

    if use_ref_car:
        ref_car = st.selectbox(
            "Reference car",
            all_cars,
            index=all_cars.index(fastest_car) if fastest_car in all_cars else 0,
            key=f"{key_prefix}_ref_car",
        )
        fastest_laps = _fastest_lap_per_car(df_cls)
        default_ref_lap = fastest_laps.get(ref_car, 1)
        ref_lap = st.number_input(
            f"Reference lap (car #{ref_car})",
            min_value=1,
            max_value=int(df_cls["LAP_NUMBER"].max()),
            value=default_ref_lap,
            key=f"{key_prefix}_ref_lap",
        )
        ref_row = df_cls[
            (df_cls["NUMBER"] == ref_car) &
            (df_cls["LAP_NUMBER"] == ref_lap)
        ].dropna(subset=["S1_S", "S2_S", "S3_S"])
        if ref_row.empty:
            st.warning(f"No sector data for car #{ref_car} lap {ref_lap}.")
            return
        ref_row = ref_row.iloc[0]
        ref_splits = [
            ref_row["S1_S"],
            ref_row["S1_S"] + ref_row["S2_S"],
            ref_row["S1_S"] + ref_row["S2_S"] + ref_row["S3_S"],
        ]
        ref_label = f"Reference: #{ref_car} Lap {ref_lap}"
    else:
        ref_splits = default_ref_splits
        ref_label  = f"Reference: #{fastest_car} Lap {fastest_lap} (fastest)"

    st.caption(ref_label)

    # ── Car / lap selection ───────────────────────────────────────────────
    fastest_laps_all = _fastest_lap_per_car(df_cls)

    highlighted_cars = st.multiselect(
        "Cars to show",
        all_cars,
        default=all_cars[:min(6, len(all_cars))],
        key=f"{key_prefix}_cars",
    )
    if not highlighted_cars:
        st.info("No cars selected.")
        return

    show_others = st.checkbox(
        "Show non-selected cars (grey)",
        value=False,
        key=f"{key_prefix}_show_others",
    )

    # Per-car lap pickers
    st.markdown("**Lap selection** — defaults to each car's fastest lap")
    car_lap_map: dict[str, list[int]] = {}  # car → [lap1] or [lap1, lap2]

    lap_cols = st.columns(min(len(highlighted_cars), 4))
    for i, car in enumerate(highlighted_cars):
        col = lap_cols[i % len(lap_cols)]
        max_lap = int(df_cls[df_cls["NUMBER"] == car]["LAP_NUMBER"].max())
        default_lap = fastest_laps_all.get(car, 1)
        lap1 = col.number_input(
            f"#{car} lap",
            min_value=1, max_value=max_lap,
            value=default_lap,
            key=f"{key_prefix}_lap1_{car}",
        )
        add_second = col.checkbox(
            f"Add 2nd lap for #{car}",
            value=False,
            key=f"{key_prefix}_lap2_cb_{car}",
        )
        laps = [lap1]
        if add_second:
            lap2 = col.number_input(
                f"#{car} 2nd lap",
                min_value=1, max_value=max_lap,
                value=default_lap,
                key=f"{key_prefix}_lap2_{car}",
            )
            laps.append(lap2)
        car_lap_map[car] = laps

    # ── Build figure ──────────────────────────────────────────────────────
    fig = go.Figure()

    # x-axis tick positions = sector split points of reference lap
    sector_labels = {
        ref_splits[0]: "S1",
        ref_splits[1]: "S2",
        ref_splits[2]: "Lap end",
    }

    # Zero reference line
    fig.add_hline(y=0, line_color="white", line_width=1.5, opacity=0.8)

    # Non-highlighted cars (grey, no fill, thin, excluded from legend)
    if show_others:
        other_cars = [c for c in all_cars if c not in highlighted_cars]
        for car in other_cars:
            default_lap = fastest_laps_all.get(car, 1)
            row = df_cls[
                (df_cls["NUMBER"] == car) &
                (df_cls["LAP_NUMBER"] == default_lap)
            ].dropna(subset=["S1_S", "S2_S", "S3_S"])
            if row.empty:
                continue
            row = row.iloc[0]
            cum = [
                row["S1_S"],
                row["S1_S"] + row["S2_S"],
                row["S1_S"] + row["S2_S"] + row["S3_S"],
            ]
            gaps = [c - r for c, r in zip(cum, ref_splits)]
            fig.add_trace(go.Scatter(
                x=[0.0] + ref_splits,
                y=[0.0] + gaps,
                mode="lines",
                name=f"#{car}",
                line=dict(color="#888888", width=1),
                opacity=0.4,
                showlegend=False,
                hovertemplate="Gap: %{y:+.3f}s<extra>#" + car + "</extra>",
            ))

    # Highlighted cars
    for car in highlighted_cars:
        color = car_colors.get(car, "#FFFFFF")
        fill_color = _rgba(color, 0.20) if color.startswith("#") else color

        for lap_idx, lap_number in enumerate(car_lap_map.get(car, [])):
            label = f"#{car} Lap {lap_number}"
            if len(car_lap_map[car]) > 1:
                label += f" ({'A' if lap_idx == 0 else 'B'})"

            row = df_cls[
                (df_cls["NUMBER"] == car) &
                (df_cls["LAP_NUMBER"] == lap_number)
            ].dropna(subset=["S1_S", "S2_S", "S3_S"])
            if row.empty:
                continue
            row = row.iloc[0]
            s1, s2, s3 = row["S1_S"], row["S2_S"], row["S3_S"]
            cum    = [s1, s1 + s2, s1 + s2 + s3]
            gaps   = [c - r for c, r in zip(cum, ref_splits)]
            x_vals = [0.0] + ref_splits
            y_vals = [0.0] + gaps

            # Fill area
            dash = "solid" if lap_idx == 0 else "dash"
            fig.add_trace(go.Scatter(
                x=x_vals,
                y=y_vals,
                fill="tozeroy",
                fillcolor=fill_color,
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ))
            # Line
            fig.add_trace(go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines+markers",
                name=label,
                line=dict(color=color, width=2.5, dash=dash),
                marker=dict(size=8),
                hovertemplate=(
                    "Sector end: %{x:.3f}s<br>"
                    "Gap: %{y:+.3f}s<br>"
                    f"{label}<extra></extra>"
                ),
            ))

    # Sector boundary vertical lines
    for x_pos, s_label in sector_labels.items():
        fig.add_vline(
            x=x_pos,
            line_color="#666666",
            line_width=1,
            line_dash="dot",
            annotation_text=s_label,
            annotation_position="top",
            annotation_font_color="#aaaaaa",
        )

    # Layout
    fig.update_layout(
        title=f"Qualifying Sector Gap — {selected_class}",
        xaxis=dict(
            title="Cumulative lap time (s)",
            tickvals=ref_splits,
            ticktext=["S1", "S2", "Lap end"],
        ),
        yaxis=dict(
            title="Gap to reference (s)",
            zeroline=False,
        ),
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        height=520,
    )
    apply_dark_layout(fig)

    st.plotly_chart(fig, width="stretch")
    chart_export_buttons(
        fig=fig,
        filename=f"qualifying_story_{selected_class.lower().replace(' ', '_')}",
        height=520,
    )
