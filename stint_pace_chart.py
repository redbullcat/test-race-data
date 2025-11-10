# stint_pace_chart.py
import math
import pandas as pd
import plotly.express as px
import streamlit as st

def show_stint_pace_chart(df, team_colors):
    """
    Show bar chart of average of top X% laps per stint (stints defined by CROSSING_FINISH_LINE_IN_PIT == 'B').
    - df: full dataframe
    - selected_cars: list (if empty -> show internal filter UI)
    - selected_classes: list (if empty -> show internal filter UI)
    - top_percent: int (percentage for top laps to average)
    - team_colors: dict mapping team -> color
    """

    st.subheader("🏁 Stint Pace — Top laps per stint")

    # --- basic column checks ---
    required = {"CLASS", "NUMBER", "LAP_NUMBER", "LAP_TIME", "CROSSING_FINISH_LINE_IN_PIT", "TEAM"}
    missing = required - set(df.columns)
    if missing:
        st.warning(f"Missing required columns for stint pace chart: {', '.join(missing)}")
        return

    # If caller provided class selection, use it; otherwise provide internal selector
    if selected_classes:
        classes = [c for c in sorted(df["CLASS"].dropna().unique()) if c in selected_classes]
    else:
        classes = sorted(df["CLASS"].dropna().unique())
    if not classes:
        st.info("No classes available in data.")
        return

    # Tabs per class
    tabs = st.tabs(classes)

    # Helper: parse lap time string to seconds (same logic as other charts)
    def time_to_seconds(time_str):
        try:
            parts = str(time_str).split(':')
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
            else:
                return float(time_str)
        except Exception:
            return None

    for tab, cls in zip(tabs, classes):
        with tab:
            st.markdown(f"### {cls}")

            class_df = df[df["CLASS"] == cls].copy()
            if class_df.empty:
                st.write("No data for this class.")
                continue

            # If caller passed selected_cars, use those (intersection); otherwise internal selector
            available_cars = sorted(class_df["NUMBER"].dropna().unique())
            if selected_cars:
                # respect caller selection but only cars in this class
                local_default = [c for c in selected_cars if c in available_cars]
                cars_to_select = [c for c in available_cars if c in selected_cars]
                # if none of the caller-selected cars are in this class, chart will be empty (per your "empty until select" rule)
                local_selected = local_default
            else:
                local_selected = st.multiselect(
                    f"Select cars to include ({cls})",
                    options=available_cars,
                    default=[],
                    key=f"stint_cars_{cls}"
                )

            if not local_selected:
                st.info("Select one or more cars to display the stint pace chart.")
                continue

            # top%: prefer passed value if non-empty/meaningful; otherwise provide internal control
            if isinstance(top_percent, int) and 1 <= top_percent <= 100:
                top_pct = top_percent
            else:
                top_pct = st.slider(f"Top % fastest laps to average (per stint) - {cls}", 1, 100, 20, step=1, key=f"stint_toppct_{cls}")

            # Filter to selected cars
            plot_df = class_df[class_df["NUMBER"].isin(local_selected)].copy()
            if plot_df.empty:
                st.write("No matching data after filtering.")
                continue

            # Convert lap time to seconds
            plot_df["LAP_TIME_SEC"] = plot_df["LAP_TIME"].apply(time_to_seconds)
            # ensure numeric lap number
            plot_df["LAP_NUMBER"] = pd.to_numeric(plot_df["LAP_NUMBER"], errors="coerce")
            plot_df = plot_df.sort_values(["NUMBER", "LAP_NUMBER"]).reset_index(drop=True)
            plot_df = plot_df.dropna(subset=["LAP_NUMBER", "LAP_TIME_SEC"])
            if plot_df.empty:
                st.write("No valid lap times in the selection.")
                continue

            # Build stint segmentation per car
            rows = []  # will collect per-stint summary rows

            for car, car_group in plot_df.groupby("NUMBER", sort=False):
                car_group = car_group.sort_values("LAP_NUMBER").reset_index(drop=True)

                stint_no = 1
                skip_next_lap = False
                current_stint_idxs = []

                # We'll iterate rows with index to build stints
                for idx, row in car_group.iterrows():
                    pit_flag = str(row.get("CROSSING_FINISH_LINE_IN_PIT", "")).strip().upper() == "B"

                    if skip_next_lap:
                        # current lap is the out-lap after a pit — disregard it
                        skip_next_lap = False
                        # Starting a new stint after skipping this out-lap
                        # But we do not record the empty stint here; we increment and continue
                        stint_no += 1
                        current_stint_idxs = []
                        # continue to next row (out-lap is excluded)
                        continue

                    # Add this lap to current stint
                    current_stint_idxs.append(idx)

                    if pit_flag:
                        # Lap where B occurs counts as the last lap of the stint (we include it),
                        # then the next lap is the out-lap and should be skipped.
                        # Summarize the current stint now.
                        if current_stint_idxs:
                            stint_laps = car_group.loc[current_stint_idxs]
                            lap_secs = stint_laps["LAP_TIME_SEC"].dropna().tolist()
                            stint_length = len(lap_secs)
                            if stint_length > 0:
                                # compute top X% fastest laps in this stint
                                n_keep = max(1, int(math.ceil(stint_length * top_pct / 100.0)))
                                lap_secs_sorted = sorted(lap_secs)
                                top_laps = lap_secs_sorted[:n_keep]
                                avg_top = float(sum(top_laps)) / len(top_laps)
                            else:
                                avg_top = None
                            rows.append({
                                "CLASS": cls,
                                "NUMBER": car,
                                "TEAM": car_group["TEAM"].iloc[0] if "TEAM" in car_group.columns else "",
                                "STINT_NUMBER": stint_no,
                                "STINT_LAPS": stint_length,
                                "AVG_TOP_LAP_SEC": avg_top
                            })
                        # After a pit, skip the next lap (out-lap)
                        skip_next_lap = True
                        # prepare for next stint (stint_no will be incremented when skipping)
                        current_stint_idxs = []
                    else:
                        # continue building current stint
                        pass

                # End-of-car: if there are remaining laps in current_stint_idxs (i.e. stint that didn't end with a B),
                # summarize that final stint too.
                if current_stint_idxs:
                    stint_laps = car_group.loc[current_stint_idxs]
                    lap_secs = stint_laps["LAP_TIME_SEC"].dropna().tolist()
                    stint_length = len(lap_secs)
                    if stint_length > 0:
                        n_keep = max(1, int(math.ceil(stint_length * top_pct / 100.0)))
                        lap_secs_sorted = sorted(lap_secs)
                        top_laps = lap_secs_sorted[:n_keep]
                        avg_top = float(sum(top_laps)) / len(top_laps)
                    else:
                        avg_top = None
                    rows.append({
                        "CLASS": cls,
                        "NUMBER": car,
                        "TEAM": car_group["TEAM"].iloc[0] if "TEAM" in car_group.columns else "",
                        "STINT_NUMBER": stint_no,
                        "STINT_LAPS": stint_length,
                        "AVG_TOP_LAP_SEC": avg_top
                    })

            if not rows:
                st.write("No stints found for the selected cars.")
                continue

            summary = pd.DataFrame(rows)
            # Drop stints with no valid avg (shouldn't happen, but safe)
            summary = summary.dropna(subset=["AVG_TOP_LAP_SEC"])

            if summary.empty:
                st.write("No valid stint lap times after processing.")
                continue

            # Create a display label per stint (Car - Stint)
            summary["LABEL"] = summary["NUMBER"].astype(str) + " — S" + summary["STINT_NUMBER"].astype(str)

            # Order by car then stint
            summary = summary.sort_values(["NUMBER", "STINT_NUMBER"]).reset_index(drop=True)

            # Build the bar chart
            fig = px.bar(
                summary,
                x="LABEL",
                y="AVG_TOP_LAP_SEC",
                color="TEAM",
                hover_data={
                    "NUMBER": True,
                    "STINT_NUMBER": True,
                    "STINT_LAPS": True,
                    "AVG_TOP_LAP_SEC": ":.3f"
                },
                labels={"AVG_TOP_LAP_SEC": f"Average Top {top_pct}% Lap (s)", "LABEL": "Car — Stint"},
                color_discrete_map={team: col for team, col in team_colors.items()}
            )

            fig.update_layout(
                title=f"Stint Pace — {cls} (top {top_pct}%)",
                xaxis_title="Car — Stint",
                yaxis_title="Avg Top Lap (s)",
                plot_bgcolor="#2b2b2b",
                paper_bgcolor="#2b2b2b",
                font=dict(color="white"),
                xaxis=dict(tickangle=-45, color="white"),
                yaxis=dict(color="white"),
                legend=dict(title="Team"),
                margin=dict(l=60, r=20, t=60, b=140),
                hovermode="closest"
            )

            # If you want bars grouped by car visually, we leave the label as-is.
            # Show chart
            st.plotly_chart(fig, use_container_width=True)
