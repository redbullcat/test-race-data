"""
story_chart.py — Race Story visualisation.

Two chart types, both with annotations:
  1. Gap evolution (filled areas, like the IndyCar Reddit charts)
  2. Position chart (inverted Y, line-per-car)

Auto-detects key events from the data:
  - Caution / safety car periods (FLAG_AT_FL)
  - Pit stops per car (CROSSING_FINISH_LINE_IN_PIT)
  - Lead changes
  - Driver changes within a car

All auto-detected events are editable. Custom annotations can be added.
The headline narrative and car selection are fully configurable.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (
    apply_dark_layout,
    build_color_map,
    parse_hour_with_rollover,
    sort_cars,
    seconds_to_laptime,
)


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

# Colours for annotation categories
ANNOTATION_COLOURS = {
    "Caution / SC":    "#FFD700",
    "Pit stop":        "#00BFFF",
    "Lead change":     "#FF6B6B",
    "Driver change":   "#98FB98",
    "Custom":          "#FFFFFF",
}

FLAG_COLOURS = {
    "FCY":    "rgba(255,165,0,0.15)",
    "SC":     "rgba(255,165,0,0.25)",
    "YELLOW": "rgba(255,215,0,0.15)",
    "RED":    "rgba(220,50,50,0.20)",
}


# ---------------------------------------------------------------------------
# Auto event detection
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def detect_events(df: pd.DataFrame, selected_class: str) -> list[dict]:
    """
    Scan the race data for key events and return a list of annotation dicts:
        { lap, text, category, car, visible }

    Each event is a suggestion — the user can edit or delete them.
    """
    if df.empty:
        return []

    class_df = df[df["CLASS"] == selected_class].copy()
    class_df = class_df.dropna(subset=["LAP_NUMBER"]).copy()
    class_df["LAP_NUMBER"] = class_df["LAP_NUMBER"].astype(int)

    events: list[dict] = []

    # ── 1. Caution / SC periods ───────────────────────────────────────────
    if "FLAG_AT_FL" in class_df.columns:
        prev_flag = "GREEN"
        for lap in sorted(class_df["LAP_NUMBER"].unique()):
            lap_df = class_df[class_df["LAP_NUMBER"] == lap]
            flags = lap_df["FLAG_AT_FL"].dropna().unique()
            flag = flags[0] if len(flags) > 0 else "GREEN"
            flag = str(flag).strip().upper()

            if flag != prev_flag:
                if flag in ("FCY", "SC", "YELLOW", "RED"):
                    label = {"FCY": "FCY", "SC": "Safety Car", "YELLOW": "Yellow", "RED": "Red Flag"}.get(flag, flag)
                    events.append({
                        "lap":      int(lap),
                        "text":     f"{label} — Lap {lap}",
                        "category": "Caution / SC",
                        "car":      "All",
                        "visible":  True,
                    })
                elif flag == "GREEN" and prev_flag in ("FCY", "SC", "YELLOW", "RED"):
                    events.append({
                        "lap":      int(lap),
                        "text":     f"Restart — Lap {lap}",
                        "category": "Caution / SC",
                        "car":      "All",
                        "visible":  True,
                    })
            prev_flag = flag

    # ── 2. Pit stops ──────────────────────────────────────────────────────
    if "CROSSING_FINISH_LINE_IN_PIT" in class_df.columns:
        pit_df = class_df[
            class_df["CROSSING_FINISH_LINE_IN_PIT"].astype(str).str.strip().str.upper() == "B"
        ]
        for _, row in pit_df.iterrows():
            car  = row["NUMBER"]
            team = row.get("TEAM", "")
            lap  = int(row["LAP_NUMBER"])
            events.append({
                "lap":      lap,
                "text":     f"#{car} pits — Lap {lap}",
                "category": "Pit stop",
                "car":      car,
                "visible":  True,
            })

    # ── 3. Lead changes ───────────────────────────────────────────────────
    # Sort each lap by ELAPSED to find the leader
    if "ELAPSED_SECONDS" in class_df.columns:
        prev_leader = None
        for lap in sorted(class_df["LAP_NUMBER"].unique()):
            lap_df = class_df[class_df["LAP_NUMBER"] == lap].dropna(subset=["ELAPSED_SECONDS"])
            if lap_df.empty:
                continue
            # Exclude pit-lap crossings for leader detection
            if "CROSSING_FINISH_LINE_IN_PIT" in lap_df.columns:
                lap_df = lap_df[lap_df["CROSSING_FINISH_LINE_IN_PIT"].astype(str).str.strip().str.upper() != "B"]
            if lap_df.empty:
                continue
            leader = lap_df.sort_values("ELAPSED_SECONDS").iloc[0]["NUMBER"]
            if prev_leader is not None and leader != prev_leader:
                events.append({
                    "lap":      int(lap),
                    "text":     f"#{leader} takes the lead — Lap {lap}",
                    "category": "Lead change",
                    "car":      leader,
                    "visible":  True,
                })
            prev_leader = leader

    # ── 4. Driver changes ─────────────────────────────────────────────────
    if "DRIVER_NAME" in class_df.columns:
        for car, car_df in class_df.groupby("NUMBER"):
            car_df = car_df.sort_values("LAP_NUMBER")
            car_df["PREV_DRIVER"] = car_df["DRIVER_NAME"].shift()
            changes = car_df[
                car_df["DRIVER_NAME"].notna() &
                car_df["PREV_DRIVER"].notna() &
                (car_df["DRIVER_NAME"] != car_df["PREV_DRIVER"])
            ]
            for _, row in changes.iterrows():
                # Only flag if it coincides with a pit stop lap (within ±1 lap)
                lap = int(row["LAP_NUMBER"])
                events.append({
                    "lap":      lap,
                    "text":     f"#{car} driver change → {row['DRIVER_NAME'].split()[-1]} — Lap {lap}",
                    "category": "Driver change",
                    "car":      car,
                    "visible":  True,
                })

    # Sort by lap, deduplicate very close events
    events.sort(key=lambda e: e["lap"])
    return events


# ---------------------------------------------------------------------------
# Gap computation (shared by both chart types)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _compute_gaps(df: pd.DataFrame, ref_car: str) -> pd.DataFrame:
    """
    Compute gap to a reference car for all cars, per lap.
    Uses ELAPSED_SECONDS (cumulative race time) directly — no HOUR parsing needed.
    ELAPSED_SECONDS is already correct and handles midnight rollover via load_race.
    """
    if "ELAPSED_SECONDS" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df = df.dropna(subset=["ELAPSED_SECONDS", "LAP_NUMBER"])
    df["LAP_NUMBER"] = df["LAP_NUMBER"].astype(int)

    # Reference car: one row per lap (take the first crossing, not pit laps)
    ref_df = df[df["NUMBER"] == ref_car].copy()
    if "CROSSING_FINISH_LINE_IN_PIT" in ref_df.columns:
        ref_clean = ref_df[ref_df["CROSSING_FINISH_LINE_IN_PIT"].astype(str).str.strip().str.upper() != "B"]
        if not ref_clean.empty:
            ref_df = ref_clean

    ref = (
        ref_df.sort_values("ELAPSED_SECONDS")
        .groupby("LAP_NUMBER")["ELAPSED_SECONDS"]
        .first()
        .reset_index()
        .rename(columns={"ELAPSED_SECONDS": "REF_TIME"})
    )

    merged = df.merge(ref, on="LAP_NUMBER", how="left")
    merged["GAP"] = merged["ELAPSED_SECONDS"] - merged["REF_TIME"]
    return merged


def _compute_positions(df: pd.DataFrame) -> pd.DataFrame:
    """Compute lap-by-lap position from ELAPSED_SECONDS."""
    df = df.dropna(subset=["LAP_NUMBER", "ELAPSED_SECONDS"]).copy()
    df["LAP_NUMBER"] = df["LAP_NUMBER"].astype(int)

    if "CROSSING_FINISH_LINE_IN_PIT" in df.columns:
        not_pitting = df[df["CROSSING_FINISH_LINE_IN_PIT"].astype(str).str.strip().str.upper() != "B"]
    else:
        not_pitting = df

    positions = []
    for lap in sorted(df["LAP_NUMBER"].unique()):
        lap_df = not_pitting[not_pitting["LAP_NUMBER"] == lap].sort_values("ELAPSED_SECONDS").reset_index(drop=True)
        for pos, (_, row) in enumerate(lap_df.iterrows(), start=1):
            positions.append({"LAP_NUMBER": lap, "NUMBER": row["NUMBER"], "POSITION": pos})

    return pd.DataFrame(positions) if positions else pd.DataFrame()


# ---------------------------------------------------------------------------
# Annotation editor UI
# ---------------------------------------------------------------------------

def _annotation_editor(events: list[dict], key_prefix: str) -> list[dict]:
    """
    Render an editable table of annotations. Returns the updated list.
    Users can toggle visibility, edit text, change lap, or delete rows.
    """
    st.markdown("**Annotations**")

    if "story_events" not in st.session_state or st.session_state.get(f"{key_prefix}_reset"):
        st.session_state["story_events"] = [e.copy() for e in events]
        st.session_state[f"{key_prefix}_reset"] = False

    current = st.session_state["story_events"]

    # Add custom annotation
    with st.expander("➕ Add custom annotation", expanded=False):
        c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
        new_text = c1.text_input("Text", key=f"{key_prefix}_new_text")
        new_lap  = c2.number_input("Lap", min_value=1, value=1, key=f"{key_prefix}_new_lap")
        new_cat  = c3.selectbox("Category", list(ANNOTATION_COLOURS.keys()),
                                index=list(ANNOTATION_COLOURS.keys()).index("Custom"),
                                key=f"{key_prefix}_new_cat")
        new_car  = c4.text_input("Car #", value="All", key=f"{key_prefix}_new_car")
        if st.button("Add annotation", key=f"{key_prefix}_add"):
            current.append({
                "lap": int(new_lap), "text": new_text,
                "category": new_cat, "car": new_car, "visible": True,
            })
            current.sort(key=lambda e: e["lap"])
            st.rerun()

    # ── Bulk controls ──────────────────────────────────────────────────
    ctrl_cols = st.columns([2, 2, 2, 2])

    if ctrl_cols[0].button("↩ Reset to auto-detected", key=f"{key_prefix}_reset_btn"):
        st.session_state[f"{key_prefix}_reset"] = True
        st.rerun()
    if ctrl_cols[1].button("🗑 Delete all", key=f"{key_prefix}_delete_all"):
        st.session_state["story_events"] = []
        st.rerun()

    # Remove by car
    all_cars_in_events = sorted({e["car"] for e in current if e["car"] != "All"})
    if all_cars_in_events:
        car_to_remove = ctrl_cols[2].selectbox(
            "Remove car:", ["—"] + all_cars_in_events,
            key=f"{key_prefix}_remove_car"
        )
        if car_to_remove != "—":
            if ctrl_cols[2].button(f"Remove #{car_to_remove}", key=f"{key_prefix}_do_remove_car"):
                st.session_state["story_events"] = [
                    e for e in current if e["car"] != car_to_remove
                ]
                st.rerun()

    # Remove by category
    all_cats = sorted({e.get("category","Custom") for e in current})
    if all_cats:
        cat_to_remove = ctrl_cols[3].selectbox(
            "Remove category:", ["—"] + all_cats,
            key=f"{key_prefix}_remove_cat"
        )
        if cat_to_remove != "—":
            if ctrl_cols[3].button(f"Remove {cat_to_remove}", key=f"{key_prefix}_do_remove_cat"):
                st.session_state["story_events"] = [
                    e for e in current if e.get("category","Custom") != cat_to_remove
                ]
                st.rerun()

    st.divider()

    # Column header for Y position
    hdr = st.columns([0.5, 1, 3.5, 1, 1.5, 1])
    hdr[0].caption("Show"); hdr[1].caption("Lap"); hdr[2].caption("Text")
    hdr[3].caption("Y pos"); hdr[4].caption("Category"); hdr[5].caption("")

    # Editable rows
    to_delete = []
    for i, evt in enumerate(current):
        # Default y_pos: auto-spread from top (0.95) downwards in steps of 0.10
        if "y_pos" not in evt:
            evt["y_pos"] = round(0.95 - (i % 8) * 0.10, 2)
        with st.container():
            cols = st.columns([0.5, 1, 3.5, 1, 1.5, 1])
            evt["visible"] = cols[0].checkbox(
                "Show", value=evt["visible"], key=f"{key_prefix}_vis_{i}", label_visibility="hidden"
            )
            evt["lap"]  = int(cols[1].number_input(
                "Lap", value=int(evt["lap"]), min_value=1,
                key=f"{key_prefix}_lap_{i}", label_visibility="collapsed"
            ))
            evt["text"] = cols[2].text_input(
                "Text", value=evt["text"],
                key=f"{key_prefix}_txt_{i}", label_visibility="collapsed"
            )
            evt["y_pos"] = round(float(cols[3].number_input(
                "Y", value=float(evt["y_pos"]),
                min_value=0.0, max_value=1.0, step=0.05, format="%.2f",
                key=f"{key_prefix}_ypos_{i}", label_visibility="collapsed",
                help="Vertical position (0=bottom, 1=top)"
            )), 2)
            evt["category"] = cols[4].selectbox(
                "Cat", list(ANNOTATION_COLOURS.keys()),
                index=list(ANNOTATION_COLOURS.keys()).index(evt.get("category", "Custom")),
                key=f"{key_prefix}_cat_{i}", label_visibility="collapsed"
            )
            if cols[5].button("🗑", key=f"{key_prefix}_del_{i}"):
                to_delete.append(i)

    for i in sorted(to_delete, reverse=True):
        current.pop(i)
    if to_delete:
        st.rerun()

    st.session_state["story_events"] = current
    return current


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _add_flag_bands(fig, df: pd.DataFrame, lap_min: int, lap_max: int) -> None:
    """Add coloured background bands for caution / SC periods."""
    if "FLAG_AT_FL" not in df.columns:
        return
    laps = sorted(df["LAP_NUMBER"].dropna().astype(int).unique())
    prev_flag = "GREEN"
    band_start = None

    def _close_band(flag, end):
        if flag in FLAG_COLOURS and band_start is not None:
            fig.add_vrect(
                x0=band_start, x1=end,
                fillcolor=FLAG_COLOURS[flag],
                layer="below", line_width=0,
            )

    for lap in laps:
        if lap < lap_min or lap > lap_max:
            continue
        flags = df[df["LAP_NUMBER"] == lap]["FLAG_AT_FL"].dropna().unique()
        flag  = str(flags[0]).strip().upper() if len(flags) > 0 else "GREEN"
        if flag != prev_flag:
            _close_band(prev_flag, lap)
            band_start = lap
        prev_flag = flag

    _close_band(prev_flag, lap_max)


def _add_annotations(fig, events: list[dict], y_ref: str = "paper",
                      y_frac: float = 0.95) -> None:
    """
    Add vertical lines + text labels for each visible annotation.
    Y position comes from evt["y_pos"] (0–1 paper coords, set by user).
    Falls back to auto-spread from y_frac if not set.
    """
    visible = [e for e in events if e.get("visible")]
    # Track which laps already have a vline to avoid duplicates
    vlines_added: set = set()

    for i, evt in enumerate(visible):
        lap   = evt["lap"]
        color = ANNOTATION_COLOURS.get(evt.get("category", "Custom"), "#FFFFFF")
        y_pos = evt.get("y_pos", round(y_frac - (i % 8) * 0.10, 2))

        # Vertical line — one per lap regardless of how many annotations share it
        if lap not in vlines_added:
            fig.add_vline(
                x=lap,
                line_color=color,
                line_width=1.5,
                line_dash="dot",
                opacity=0.8,
            )
            vlines_added.add(lap)

        fig.add_annotation(
            x=lap,
            y=y_pos,
            yref=y_ref,
            text=evt["text"],
            showarrow=True,
            arrowhead=2,
            arrowcolor=color,
            arrowwidth=1.5,
            font=dict(color=color, size=11),
            bgcolor="rgba(0,0,0,0.65)",
            bordercolor=color,
            borderwidth=1,
            borderpad=3,
            ax=20,
            ay=-30,
            xanchor="left",
        )


# ---------------------------------------------------------------------------
# Gap evolution story chart
# ---------------------------------------------------------------------------

def _add_logo_to_fig(
    fig,
    logo_path: str | None,
    show_logo: bool,
    position: str,
    size: float,
    opacity: float,
) -> None:
    """Add a logo SVG as a Plotly layout image."""
    if not show_logo or not logo_path:
        return
    import base64, os as _os
    try:
        with open(logo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = _os.path.splitext(logo_path)[1].lstrip(".")
        mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
        src = f"data:{mime};base64,{b64}"
    except Exception:
        return

    # Map position label to paper coordinates
    pos_map = {
        "Bottom right": (1.0, 0.0, "right",  "bottom"),
        "Bottom left":  (0.0, 0.0, "left",   "bottom"),
        "Top right":    (1.0, 1.0, "right",  "top"),
        "Top left":     (0.0, 1.0, "left",   "top"),
    }
    x, y, xanchor, yanchor = pos_map.get(position, (1.0, 0.0, "right", "bottom"))

    fig.add_layout_image(dict(
        source=src,
        xref="paper", yref="paper",
        x=x, y=y,
        sizex=size, sizey=size,
        xanchor=xanchor, yanchor=yanchor,
        opacity=opacity,
        layer="above",
    ))


def _build_gap_story(
    df: pd.DataFrame,
    selected_cars: list[str],
    ref_car: str,
    team_colors: dict,
    events: list[dict],
    lap_range: tuple[int, int],
    headline: str,
    subtitle: str,
    logo_path: str | None = None,
    show_logo: bool = False,
    logo_position: str = "Bottom right",
    logo_size: float = 0.18,
    logo_opacity: float = 0.6,
) -> go.Figure:
    merged = _compute_gaps(df, ref_car)
    merged = merged[
        merged["NUMBER"].isin(selected_cars) &
        merged["LAP_NUMBER"].between(lap_range[0], lap_range[1])
    ]
    color_map = build_color_map(df, team_colors)

    fig = go.Figure()
    _add_flag_bands(fig, merged, lap_range[0], lap_range[1])

    # Reference car line (always at y=0, shown as thin reference)
    ref_data = merged[merged["NUMBER"] == ref_car].sort_values("LAP_NUMBER")
    if not ref_data.empty:
        team = ref_data["TEAM"].iloc[0]
        color = color_map.get(team, "#AAAAAA")
        fig.add_trace(go.Scatter(
            x=ref_data["LAP_NUMBER"],
            y=[0] * len(ref_data),
            mode="lines",
            name=f"#{ref_car} — {team} (reference)",
            line=dict(width=2, color=color, dash="dash"),
        ))

    # Other cars — filled area + line
    other_cars = [c for c in selected_cars if c != ref_car]
    for car in other_cars:
        car_data = merged[merged["NUMBER"] == car].sort_values("LAP_NUMBER")
        if car_data.empty:
            continue
        team  = car_data["TEAM"].iloc[0]
        color = color_map.get(team, "#AAAAAA")

        # Filled area — build rgba() fillcolor from hex or existing rgb/rgba
        def _to_rgba(c: str, alpha: float = 0.25) -> str:
            c = c.strip()
            if c.startswith("rgba"):
                return c  # already rgba, leave as-is
            if c.startswith("rgb("):
                return c.replace("rgb(", "rgba(").rstrip(")") + f",{alpha})"
            if c.startswith("#"):
                h = c.lstrip("#")
                if len(h) == 3:
                    h = "".join(x*2 for x in h)
                r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
                return f"rgba({r},{g},{b},{alpha})"
            return f"rgba(170,170,170,{alpha})"

        fig.add_trace(go.Scatter(
            x=pd.concat([car_data["LAP_NUMBER"], car_data["LAP_NUMBER"].iloc[::-1]]).tolist(),
            y=pd.concat([car_data["GAP"], pd.Series([0] * len(car_data))]).tolist(),
            fill="tozeroy",
            fillcolor=_to_rgba(color, 0.25),
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ))
        # Line
        fig.add_trace(go.Scatter(
            x=car_data["LAP_NUMBER"],
            y=car_data["GAP"],
            mode="lines",
            name=f"#{car} — {team}",
            line=dict(width=2.5, color=color),
            hovertemplate=f"#{car} — {team}<br>Lap %{{x}}<br>Gap: %{{y:.1f}}s<extra></extra>",
        ))

    _add_annotations(fig, events)

    title_text = f"<b>{headline}</b><br><sub>{subtitle}</sub>" if subtitle else f"<b>{headline}</b>"
    fig.update_layout(
        title=dict(text=title_text, font=dict(size=20)),
        xaxis_title="Lap Number",
        yaxis_title=f"Gap to #{ref_car} (s)",
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        height=550,
    )
    apply_dark_layout(fig)
    return fig


# ---------------------------------------------------------------------------
# Position story chart
# ---------------------------------------------------------------------------

def _build_position_story(
    df: pd.DataFrame,
    selected_cars: list[str],
    team_colors: dict,
    events: list[dict],
    lap_range: tuple[int, int],
    headline: str,
    subtitle: str,
    logo_path: str | None = None,
    show_logo: bool = False,
    logo_position: str = "Bottom right",
    logo_size: float = 0.18,
    logo_opacity: float = 0.6,
) -> go.Figure:
    pos_df = _compute_positions(df)
    if pos_df.empty:
        return go.Figure()

    pos_df = pos_df[
        pos_df["NUMBER"].isin(selected_cars) &
        pos_df["LAP_NUMBER"].between(lap_range[0], lap_range[1])
    ]
    color_map = build_color_map(df, team_colors)

    fig = go.Figure()
    _add_flag_bands(fig, df, lap_range[0], lap_range[1])

    for car in selected_cars:
        car_data = pos_df[pos_df["NUMBER"] == car].sort_values("LAP_NUMBER")
        if car_data.empty:
            continue
        car_rows = df[df["NUMBER"] == car]
        team  = car_rows["TEAM"].iloc[0] if not car_rows.empty else ""
        color = color_map.get(team, "#AAAAAA")

        fig.add_trace(go.Scatter(
            x=car_data["LAP_NUMBER"],
            y=car_data["POSITION"],
            mode="lines+markers",
            name=f"#{car} — {team}",
            line=dict(width=2.5, color=color),
            marker=dict(size=3),
            hovertemplate=f"#{car} — {team}<br>Lap %{{x}}<br>P%{{y}}<extra></extra>",
        ))

    _add_annotations(fig, events, y_ref="paper", y_frac=0.05)

    title_text = f"<b>{headline}</b><br><sub>{subtitle}</sub>" if subtitle else f"<b>{headline}</b>"
    fig.update_layout(
        title=dict(text=title_text, font=dict(size=20)),
        xaxis_title="Lap",
        yaxis_title="Position",
        yaxis=dict(autorange="reversed", dtick=1),
        hovermode="x unified",
        height=550,
    )
    apply_dark_layout(fig)
    _add_logo_to_fig(fig, logo_path, show_logo, logo_position, logo_size, logo_opacity)
    return fig


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def show_story(df: pd.DataFrame, team_colors: dict, race_start_date) -> None:
    st.subheader("Race Story")
    st.caption(
        "Auto-detected key events are shown as annotations. "
        "Edit them, add your own, or switch between chart types."
    )

    required = {"CLASS", "NUMBER", "LAP_NUMBER", "TEAM"}
    if not required.issubset(df.columns):
        st.warning(f"Missing columns: {required - set(df.columns)}")
        return

    # ── Class & car selection ────────────────────────────────────────────
    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Class:", classes, key="story_class")
    class_df = df[df["CLASS"] == selected_class].copy()
    class_df = class_df.dropna(subset=["LAP_NUMBER"]).copy()
    class_df["LAP_NUMBER"] = class_df["LAP_NUMBER"].astype(int)

    all_cars = sort_cars(class_df["NUMBER"].unique())
    default_cars = all_cars[:5] if len(all_cars) >= 5 else all_cars
    selected_cars = st.multiselect(
        "Cars to include:", all_cars, default=default_cars, key="story_cars"
    )
    if not selected_cars:
        st.info("Select at least one car.")
        return

    # ── Lap range ────────────────────────────────────────────────────────
    min_lap = int(class_df["LAP_NUMBER"].min())
    max_lap = int(class_df["LAP_NUMBER"].max())
    lap_range = st.slider(
        "Lap range:", min_lap, max_lap, (min_lap, max_lap), key="story_laps"
    )

    # ── Chart type ───────────────────────────────────────────────────────
    chart_type = st.radio(
        "Chart type:",
        ["Gap evolution (filled area)", "Position chart"],
        horizontal=True,
        key="story_chart_type",
    )

    # ── Reference car (gap chart only) ───────────────────────────────────
    ref_car = None
    if chart_type == "Gap evolution (filled area)":
        if race_start_date is None:
            st.warning("Gap evolution requires a race start date in the filename.")
            return
        if "ELAPSED_SECONDS" not in class_df.columns:
            st.warning("Gap evolution requires ELAPSED_SECONDS column.")
            return
        ref_car = st.selectbox(
            "Reference car (gap measured from this car):",
            selected_cars,
            key="story_ref_car",
        )

    # ── Narrative ────────────────────────────────────────────────────────
    st.markdown("**Narrative** *(shown as chart title)*")
    col1, col2 = st.columns([3, 2])
    headline = col1.text_input(
        "Headline:",
        value="Race Story",
        key="story_headline",
    )
    subtitle = col2.text_input(
        "Subtitle / context:",
        value="",
        placeholder="e.g. 'Final 30 laps — Hypercar battle'",
        key="story_subtitle",
    )

    # ── Logo ─────────────────────────────────────────────────────────────
    import os as _os
    logo_col1, logo_col2, logo_col3, logo_col4 = st.columns([1, 1, 1, 1])
    show_logo = logo_col1.checkbox("Show logo", value=False, key="story_show_logo")
    logo_position = logo_col2.selectbox(
        "Logo position", ["Bottom right", "Bottom left", "Top right", "Top left"],
        key="story_logo_pos"
    )
    logo_opacity = logo_col3.slider("Logo opacity", 0.1, 1.0, 0.6, 0.05, key="story_logo_opacity")
    logo_size = logo_col4.slider("Logo size", 0.05, 0.35, 0.18, 0.01, key="story_logo_size")

    # Resolve logo path — look for white version (better on dark background)
    _repo_root = _os.path.dirname(_os.path.abspath(__file__))
    _logo_candidates = [
        _os.path.join(_repo_root, "colour-white.svg"),
        _os.path.join(_repo_root, "colour-black.svg"),
        _os.path.join(_repo_root, "logo.svg"),
        _os.path.join(_repo_root, "logo-white.svg"),
    ]
    logo_path = next((p for p in _logo_candidates if _os.path.exists(p)), None)

    # ── Auto-detect events ───────────────────────────────────────────────
    auto_events = detect_events(class_df, selected_class)

    # Filter to selected cars and lap range — only show events for selected cars
    auto_events = [
        e for e in auto_events
        if lap_range[0] <= e["lap"] <= lap_range[1]
        and (e["car"] == "All" or e["car"] in selected_cars)
    ]

    # If the car selection has changed, reset annotation state so stale
    # events from removed cars don't persist
    cars_key = f"story_cars_prev_{key_prefix if False else 'story'}"
    if st.session_state.get(cars_key) != tuple(sorted(selected_cars)):
        st.session_state["story_events"] = [e.copy() for e in auto_events]
        st.session_state[cars_key] = tuple(sorted(selected_cars))

    # ── Annotation filter controls ───────────────────────────────────────
    ann_col1, ann_col2, ann_col3 = st.columns([2, 2, 2])
    max_annotations = ann_col1.slider(
        "Max annotations to show:", 0, 50, 20, key="story_max_ann",
        help="Limits auto-detected annotations per chart. Custom annotations are always shown."
    )
    all_cats = list(ANNOTATION_COLOURS.keys())
    hidden_cats = ann_col2.multiselect(
        "Hide categories:", all_cats, default=[], key="story_hidden_cats",
        help="Hide entire annotation categories without deleting them."
    )

    # Apply category filter and max_annotations limit to auto events
    # Custom annotations (added by user) always bypass the max limit
    auto_filtered = [e for e in auto_events if e.get("category","Custom") not in hidden_cats]
    # Prioritise: lead changes > caution > pit stops > driver changes
    priority = {"Lead change": 0, "Caution / SC": 1, "Pit stop": 2, "Driver change": 3, "Custom": 4}
    auto_filtered.sort(key=lambda e: (priority.get(e.get("category","Custom"), 4), e["lap"]))
    auto_filtered = auto_filtered[:max_annotations]
    auto_filtered.sort(key=lambda e: e["lap"])

    # ── Annotation editor ────────────────────────────────────────────────
    with st.expander("📝 Edit annotations", expanded=False):
        st.caption(
            "Toggle visibility (☑), edit text, change lap number, or delete rows. "
            "Colour is determined by the category."
        )
        # Column headers
        h = st.columns([0.5, 1, 4, 1.5, 1])
        h[0].caption("Show")
        h[1].caption("Lap")
        h[2].caption("Text")
        h[3].caption("Category")
        h[4].caption("")
        events = _annotation_editor(auto_filtered, key_prefix="story")

    # Use whatever is current in session state (edited or auto)
    events = st.session_state.get("story_events", auto_filtered)

    # ── Build and display chart ──────────────────────────────────────────
    filtered_class_df = class_df[class_df["NUMBER"].isin(selected_cars)].copy()

    if chart_type == "Gap evolution (filled area)":
        fig = _build_gap_story(
            df=class_df,  # pass full class df so ref car always has data
            selected_cars=selected_cars,
            ref_car=ref_car,
            team_colors=team_colors,
            events=events,
            lap_range=lap_range,
            headline=headline,
            subtitle=subtitle,
            logo_path=logo_path,
            show_logo=show_logo,
            logo_position=logo_position,
            logo_size=logo_size,
            logo_opacity=logo_opacity,
        )
    else:
        fig = _build_position_story(
            df=filtered_class_df,
            selected_cars=selected_cars,
            team_colors=team_colors,
            events=events,
            lap_range=lap_range,
            headline=headline,
            subtitle=subtitle,
            logo_path=logo_path,
            show_logo=show_logo,
            logo_position=logo_position,
            logo_size=logo_size,
            logo_opacity=logo_opacity,
        )

    if fig.data:
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No data to display for the selected cars and lap range.")

    # ── Annotation legend ────────────────────────────────────────────────
    st.markdown("**Annotation categories:**")
    cols = st.columns(len(ANNOTATION_COLOURS))
    for col, (cat, color) in zip(cols, ANNOTATION_COLOURS.items()):
        col.markdown(
            f"<span style='color:{color}'>■</span> {cat}",
            unsafe_allow_html=True,
        )
