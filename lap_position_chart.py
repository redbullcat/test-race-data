"""lap_position_chart.py — Lap-by-lap position chart (full race + hourly)."""

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from utils import get_team_color, apply_dark_layout, sort_cars, chart_export_buttons


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

DASH_STYLES   = ["solid", "dash",    "dot"]
MARKER_SHAPES = ["circle", "square", "diamond"]


def _car_styles(selected_cars: list, car_colors: dict) -> dict[str, tuple]:
    """Return {car: (dash, marker_symbol)} based on shared colours."""
    color_to_cars: dict[str, list] = {}
    for car in sort_cars(selected_cars):
        col = car_colors.get(car, "#888888")
        color_to_cars.setdefault(col, []).append(car)
    car_style: dict[str, tuple] = {}
    for col, cars in color_to_cars.items():
        for i, car in enumerate(cars):
            idx = min(i, len(DASH_STYLES) - 1)
            car_style[car] = (DASH_STYLES[idx], MARKER_SHAPES[idx])
    return car_style


def _build_position_matrix(
    class_df: pd.DataFrame,
    laps_in_range: range,
) -> pd.DataFrame:
    """Build a position matrix: index=position, columns=Lap N, values=car number."""
    n_cars = class_df["NUMBER"].nunique()
    lap_positions: dict[str, list] = {
        f"Lap {i}": [None] * n_cars for i in laps_in_range
    }
    for lap in laps_in_range:
        lap_df = class_df[class_df["LAP_NUMBER"] == lap].copy()
        # Always sort by ELAPSED_SECONDS (numeric). Never sort by ELAPSED string —
        # string sort breaks at the 10-hour mark ("10:..." sorts before "9:...").
        if "ELAPSED_SECONDS" in lap_df.columns:
            lap_df = lap_df.sort_values("ELAPSED_SECONDS")
        elif "ELAPSED" in lap_df.columns:
            # Fall back: parse ELAPSED to seconds on the fly
            lap_df["_elapsed_s"] = lap_df["ELAPSED"].apply(lambda v: (
                int(v.split(":")[0]) * 3600 + int(v.split(":")[1]) * 60 + float(v.split(":")[2])
                if isinstance(v, str) and v.count(":") == 2
                else int(v.split(":")[0]) * 60 + float(v.split(":")[1])
                if isinstance(v, str) and v.count(":") == 1
                else None
            ))
            lap_df = lap_df.sort_values("_elapsed_s")
        lap_df = lap_df.reset_index(drop=True)
        for pos, car in enumerate(lap_df["NUMBER"].unique(), start=1):
            if pos - 1 < n_cars:
                lap_positions[f"Lap {lap}"][pos - 1] = car
    position_df = pd.DataFrame(lap_positions)
    position_df.index = range(1, len(position_df) + 1)
    return position_df


def _build_figure(
    class_df: pd.DataFrame,
    selected_cars: list,
    car_colors: dict,
    car_style: dict,
    laps_in_range: range,
    position_df: pd.DataFrame,
    title: str,
) -> go.Figure:
    """Build the Plotly position chart figure."""
    fig = go.Figure()
    for car in selected_cars:
        positions, laps = [], []
        for lap in laps_in_range:
            col = f"Lap {lap}"
            if col in position_df.columns and car in position_df[col].values:
                pos = position_df.index[position_df[col] == car][0]
            else:
                pos = None
            positions.append(pos)
            laps.append(lap)

        if not any(p is not None for p in positions):
            continue

        dash, marker_symbol = car_style.get(car, ("solid", "circle"))
        fig.add_trace(go.Scatter(
            x=laps,
            y=positions,
            mode="lines+markers",
            name=f"Car {car}",
            line_shape="hv",
            line=dict(
                color=car_colors.get(car, "#888888"),
                width=2,
                dash=dash,
            ),
            marker=dict(symbol=marker_symbol),
            connectgaps=False,
            hovertemplate="Lap %{x}<br>P%{y}<br>Car " + str(car),
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Lap",
        yaxis_title="Position",
        yaxis_autorange="reversed",
        yaxis=dict(dtick=1),
        legend=dict(title="Car", yanchor="top", y=0.99, xanchor="left", x=0.01),
        hovermode="x unified",
    )
    apply_dark_layout(fig)
    return fig


def _elapsed_to_seconds(val) -> float | None:
    """Convert ELAPSED_SECONDS column value to float seconds."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _hour_boundaries(class_df: pd.DataFrame) -> list[tuple[int, float, float]]:
    """
    Return list of (hour_number, elapsed_start, elapsed_end) for each
    clock-hour that contains at least one lap in class_df.
    Hour 1 = 0–3600 s, Hour 2 = 3600–7200 s, etc.
    """
    if "ELAPSED_SECONDS" not in class_df.columns:
        return []
    elapsed_vals = (
        class_df["ELAPSED_SECONDS"]
        .dropna()
        .apply(_elapsed_to_seconds)
        .dropna()
    )
    if elapsed_vals.empty:
        return []
    max_elapsed = elapsed_vals.max()
    n_hours = int(max_elapsed // 3600) + 1
    boundaries = []
    for h in range(1, n_hours + 1):
        e_start = (h - 1) * 3600.0
        e_end   = h * 3600.0
        mask = (elapsed_vals >= e_start) & (elapsed_vals < e_end)
        if mask.any():
            boundaries.append((h, e_start, e_end))
    return boundaries


def _laps_for_hour(
    class_df: pd.DataFrame,
    e_start: float,
    e_end: float,
) -> range | None:
    """
    Return the range of LAP_NUMBER values whose ELAPSED_SECONDS falls within
    [e_start, e_end). Returns None if no laps found.
    """
    if "ELAPSED_SECONDS" not in class_df.columns:
        return None
    elapsed_s = class_df["ELAPSED_SECONDS"].apply(_elapsed_to_seconds)
    mask = (elapsed_s >= e_start) & (elapsed_s < e_end)
    laps_in_hour = class_df.loc[mask, "LAP_NUMBER"].dropna().astype(int)
    if laps_in_hour.empty:
        return None
    return range(laps_in_hour.min(), laps_in_hour.max() + 1)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def show_lap_position_chart(df, team_colors):
    classes = sorted(df["CLASS"].dropna().unique())
    selected_classes = st.multiselect(
        "Select class(es) for position chart:", classes, default=classes,
        key="pos_class"
    )
    if not selected_classes:
        st.warning("No classes selected.")
        return

    st.subheader("Lap-by-Lap Position Chart")
    tabs = st.tabs(selected_classes)

    for tab, cls in zip(tabs, selected_classes):
        with tab:
            class_df = df[df["CLASS"] == cls].copy()
            available_cars = sort_cars(class_df["NUMBER"].unique())
            selected_cars = st.multiselect(
                f"Cars in {cls}:", available_cars, default=available_cars,
                key=f"pos_cars_{cls}"
            )
            if not selected_cars:
                st.info("No cars selected.")
                continue

            max_lap = class_df["LAP_NUMBER"].max()
            if pd.isna(max_lap) or max_lap < 1:
                st.info("No lap data available.")
                continue

            lap_range = st.slider(
                f"Lap range — {cls}:", 1, int(max_lap), (1, int(max_lap)),
                key=f"pos_laps_{cls}"
            )
            start_lap, end_lap = lap_range
            laps_in_range = range(start_lap, end_lap + 1)

            # ── Colour / style maps (shared by full-race and hourly) ──────
            car_colors: dict[str, str] = {}
            for _, row in class_df[["NUMBER", "TEAM"]].drop_duplicates().iterrows():
                car_colors[row["NUMBER"]] = get_team_color(row["TEAM"], team_colors)
            car_style = _car_styles(selected_cars, car_colors)

            # ── Full-race chart (untouched) ───────────────────────────────
            position_df = _build_position_matrix(class_df, laps_in_range)
            fig = _build_figure(
                class_df=class_df,
                selected_cars=selected_cars,
                car_colors=car_colors,
                car_style=car_style,
                laps_in_range=laps_in_range,
                position_df=position_df,
                title=f"Lap-by-Lap Position – {cls}",
            )
            st.plotly_chart(fig, width="stretch")
            chart_export_buttons(
                fig=fig,
                filename=f"lap_position_{cls.lower().replace(' ', '_')}",
                height=500,
            )

            # ── Hourly charts ─────────────────────────────────────────────
            with st.expander("Hourly Lap Charts", expanded=False):
                hour_boundaries = _hour_boundaries(class_df)
                if not hour_boundaries:
                    st.info("No elapsed time data available for hourly breakdown.")
                    continue

                n_hours = len(hour_boundaries)
                cls_slug = cls.lower().replace(" ", "_")

                col_view, col_svg, col_png, col_zip = st.columns([2, 1, 1, 1])
                btn_view = col_view.button(
                    f"Generate {n_hours} hourly chart{'s' if n_hours != 1 else ''}",
                    key=f"hourly_view_{cls}",
                )
                btn_svg = col_svg.button(
                    "⬇ Download all SVG",
                    key=f"hourly_svg_{cls}",
                )
                btn_png = col_png.button(
                    "⬇ Download all PNG",
                    key=f"hourly_png_{cls}",
                )

                # ── Bulk download (SVG or PNG) — JS sequential approach ──
                for fmt, btn in [("svg", btn_svg), ("png", btn_png)]:
                    if btn:
                        with st.spinner(
                            f"Preparing {n_hours} hourly {fmt.upper()} downloads…"
                        ):
                            fig_specs = []
                            for h, e_start, e_end in hour_boundaries:
                                h_laps = _laps_for_hour(class_df, e_start, e_end)
                                if h_laps is None:
                                    continue
                                h_pos_df = _build_position_matrix(class_df, h_laps)
                                h_fig = _build_figure(
                                    class_df=class_df,
                                    selected_cars=selected_cars,
                                    car_colors=car_colors,
                                    car_style=car_style,
                                    laps_in_range=h_laps,
                                    position_df=h_pos_df,
                                    title=f"Lap-by-Lap Position – {cls} – Hour {h}",
                                )
                                fname = f"{cls_slug}_hour_{h:02d}"
                                fig_specs.append((fname, h_fig.to_json()))

                        if fig_specs:
                            import json as _json
                            js_array = _json.dumps([
                                {"filename": fn, "figJson": fj}
                                for fn, fj in fig_specs
                            ])
                            scale = 1 if fmt == "svg" else 3
                            iframe_html = (
                                "<!DOCTYPE html><html><head>"
                                "<script src=\"https://cdn.plot.ly/plotly-2.35.2.min.js\"></script>"
                                "</head><body><div id=\"chart\" style=\"display:none;\"></div>"
                                "<script>"
                                f"var specs={js_array};"
                                f"var fmt=\"{fmt}\";var scale={scale};var idx=0;"
                                "function downloadNext(){if(idx>=specs.length)return;"
                                "var spec=specs[idx++];var fig=JSON.parse(spec.figJson);"
                                "Plotly.newPlot(\"chart\",fig.data,fig.layout,{staticPlot:true}).then(function(){"
                                "Plotly.newPlot(\"chart\",fig.data,fig.layout,{staticPlot:true});"
                                "Plotly.downloadImage(\"chart\","
                                "{format:fmt,width:1800,height:500,scale:scale,filename:spec.filename}"
                                ").then(function(){setTimeout(downloadNext,600);});});}"
                                "downloadNext();"
                                "</script></body></html>"
                            )
                            st.info(
                                f"Downloading {len(fig_specs)} {fmt.upper()} files — "
                                "your browser will save them one by one."
                            )
                            st.iframe(iframe_html, height=1)

                # ── View in Streamlit ────────────────────────────────────
                if btn_view or st.session_state.get(f"_hourly_generated_{cls}"):
                    st.session_state[f"_hourly_generated_{cls}"] = True

                    # Build all hourly figures (cached in session state)
                    cache_key = f"_hourly_figs_{cls}"
                    if btn_view or cache_key not in st.session_state:
                        with st.spinner(f"Building {n_hours} hourly charts…"):
                            hourly_figs = []
                            for h, e_start, e_end in hour_boundaries:
                                h_laps = _laps_for_hour(class_df, e_start, e_end)
                                if h_laps is None:
                                    continue
                                h_pos_df = _build_position_matrix(class_df, h_laps)
                                h_fig = _build_figure(
                                    class_df=class_df,
                                    selected_cars=selected_cars,
                                    car_colors=car_colors,
                                    car_style=car_style,
                                    laps_in_range=h_laps,
                                    position_df=h_pos_df,
                                    title=f"Lap-by-Lap Position – {cls} – Hour {h}",
                                )
                                hourly_figs.append((h, h_fig))
                            st.session_state[cache_key] = hourly_figs

                    hourly_figs = st.session_state.get(cache_key, [])
                    if not hourly_figs:
                        st.info("No hourly charts generated.")
                    else:
                        hour_labels = [f"Hour {h}" for h, _ in hourly_figs]
                        selected_hour = st.radio(
                            "Select hour:", hour_labels,
                            horizontal=True,
                            key=f"hourly_radio_{cls}",
                        )
                        for h, h_fig in hourly_figs:
                            if selected_hour == f"Hour {h}":
                                st.plotly_chart(h_fig, width="stretch")
                                chart_export_buttons(
                                    fig=h_fig,
                                    filename=f"{cls_slug}_hour_{h:02d}",
                                    height=500,
                                )
                                break
