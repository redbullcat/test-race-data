import pandas as pd
import plotly.graph_objects as go
import streamlit as st

def show_time_gap_chart(df, team_colors):
    st.subheader("⏱️ Time Gap Comparison")

    # --- Class and car selection ---
    available_classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select Class", available_classes)
    class_df = df[df["CLASS"] == selected_class]

    available_cars = sorted(class_df["NUMBER"].unique())
    selected_cars = st.multiselect(
        "Select Cars to Compare", available_cars,
        help="Select at least two cars to compare race gaps."
    )

    if len(selected_cars) < 2:
        st.info("Select at least two cars to see the time gap chart.")
        return

    # --- Convert ELAPSED column (format: mm:ss.sss or h:mm:ss.sss) to total seconds ---
    def to_seconds(t):
        if pd.isna(t):
            return None
        t = str(t).strip()
        parts = t.split(':')
        try:
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
        except Exception:
            return None
        return None

    class_df = class_df.copy()
    class_df['ELAPSED_SECONDS'] = class_df['ELAPSED'].apply(to_seconds)
    class_df['LAP_NUMBER'] = pd.to_numeric(class_df['LAP_NUMBER'], errors='coerce')
    class_df = class_df.dropna(subset=['ELAPSED_SECONDS', 'LAP_NUMBER'])

    # --- Prepare reference car (first selected car) ---
    reference_car = selected_cars[0]
    ref_data = class_df[class_df["NUMBER"] == reference_car][["LAP_NUMBER", "ELAPSED_SECONDS"]].sort_values("LAP_NUMBER")
    ref_data = ref_data.rename(columns={"ELAPSED_SECONDS": "REF_TIME"})

    fig = go.Figure()

    # --- Plot gaps of other cars vs reference ---
    for car in selected_cars[1:]:
        car_data = class_df[class_df["NUMBER"] == car][["LAP_NUMBER", "ELAPSED_SECONDS"]].sort_values("LAP_NUMBER")
        car_data = car_data.rename(columns={"ELAPSED_SECONDS": "CAR_TIME"})

        merged = pd.merge(ref_data, car_data, on="LAP_NUMBER", how="inner")
        if merged.empty:
            continue

        merged["GAP_SECONDS"] = merged["CAR_TIME"] - merged["REF_TIME"]

        team = class_df.loc[class_df["NUMBER"] == car, "TEAM"].iloc[0] if not class_df[class_df["NUMBER"] == car].empty else "Unknown"
        color = team_colors.get(team, "#888888")

        fig.add_trace(go.Scatter(
            x=merged["LAP_NUMBER"],
            y=merged["GAP_SECONDS"],
            mode="lines",
            name=f"{car}",
            line=dict(width=2, color=color)
        ))

    # --- Dynamic Y-axis range (reversed) ---
    all_y = [y for trace in fig.data for y in trace.y]
    if all_y:
        y_min, y_max = min(all_y), max(all_y)
        margin = (y_max - y_min) * 0.1
        y_range = [y_max + margin, y_min - margin]  # reversed axis
    else:
        y_range = [1, 0]

    # --- Layout ---
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white"),
        xaxis=dict(title="Lap Number", showgrid=True, color="white"),
        yaxis=dict(
            title=f"Gap to Car #{reference_car} (seconds)",
            showgrid=True,
            color="white",
            autorange=False,
            range=y_range,
        ),
        legend=dict(title="Car Number"),
        hovermode="x unified",
        height=600,
    )

    st.plotly_chart(fig, use_container_width=True)
