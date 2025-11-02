import pandas as pd
import plotly.express as px
import streamlit as st

def show_time_gap_chart(df, team_colors):
    st.subheader("Driver Pace Comparison")

    # --- Streamlit filters ---
    all_cars = sorted(df["CAR_NUMBER"].unique())
    car_options = st.multiselect(
        "Select two cars to compare:",
        options=all_cars,
        default=all_cars[:2],
        max_selections=2
    )

    if len(car_options) != 2:
        st.warning("Please select exactly two cars.")
        return

    car1, car2 = car_options

    # --- Ensure proper data types ---
    if "LAP_NUMBER" not in df.columns:
        st.error("Missing required column: LAP_NUMBER")
        return

    # Convert race time columns if needed
    # Try both formats: total race time or cumulative lap time
    time_col_candidates = [c for c in df.columns if "TIME" in c.upper()]
    if not time_col_candidates:
        st.error("No TIME-related column found in DataFrame.")
        return

    # Pick the first matching time column
    time_col = time_col_candidates[0]

    # Convert to timedelta if in string format (e.g., "6:00:28.365")
    if df[time_col].dtype == object:
        df[time_col] = pd.to_timedelta(df[time_col])

    # --- Filter both cars ---
    df_car1 = df[df["CAR_NUMBER"] == car1].sort_values("LAP_NUMBER")
    df_car2 = df[df["CAR_NUMBER"] == car2].sort_values("LAP_NUMBER")

    # --- Merge by LAP_NUMBER ---
    merged = pd.merge(
        df_car1[["LAP_NUMBER", time_col]],
        df_car2[["LAP_NUMBER", time_col]],
        on="LAP_NUMBER",
        suffixes=(f"_{car1}", f"_{car2}")
    )

    # --- Calculate gap in seconds ---
    merged["GAP_SECONDS"] = (
        merged[f"{time_col}_{car2}"] - merged[f"{time_col}_{car1}"]
    ).dt.total_seconds()

    # --- Sanity check ---
    final_gap = merged["GAP_SECONDS"].iloc[-1]
    st.write(f"**Final gap:** {final_gap:.3f} seconds")

    # --- Create chart ---
    fig = px.line(
        merged,
        x="LAP_NUMBER",
        y="GAP_SECONDS",
        title=f"Gap between car {car1} and car {car2}",
        labels={"LAP_NUMBER": "Lap", "GAP_SECONDS": "Time gap (s)"},
    )

    # --- Styling ---
    color1 = team_colors.get(car1, "#AAAAAA")
    color2 = team_colors.get(car2, "#CCCCCC")
    fig.update_traces(line=dict(color=color2, width=3))

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white"),
        yaxis=dict(
            title="Gap (s)",
            rangemode="normal",
            autorange=True
        ),
        xaxis=dict(title="Lap"),
        title=dict(x=0.5),
        hovermode="x unified",
    )

    # --- Display chart ---
    st.plotly_chart(fig, use_container_width=True)
