import plotly.graph_objects as go
import pandas as pd
import streamlit as st


def show_time_gap_chart(df, team_colors):
    st.subheader("⏱️ Time Gap Comparison")

    # --- Select class ---
    classes = sorted(df["CLASS"].dropna().unique())
    selected_class = st.selectbox("Select Class", classes, key="gap_class_select")

    class_df = df[df["CLASS"] == selected_class]

    # --- Select cars within class ---
    cars_in_class = sorted(class_df["NUMBER"].unique())
    selected_cars = st.multiselect(
        "Select Cars to Compare",
        cars_in_class,
        default=cars_in_class[:2],
        key="gap_car_select"
    )

    if len(selected_cars) < 2:
        st.info("Please select at least two cars to compare.")
        return

    # --- Convert ELAPSED to seconds ---
    def to_seconds(t):
        try:
            parts = t.split(":")
            if len(parts) == 2:  # mm:ss.sss
                m, s = parts
                return int(m) * 60 + float(s)
            elif len(parts) == 3:  # h:mm:ss.sss
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
        except:
            return None

    class_df["ELAPSED_SECONDS"] = class_df["ELAPSED"].apply(to_seconds)
    class_df = class_df.dropna(subset=["ELAPSED_SECONDS"])

    # --- Filter only selected cars ---
    class_df = class_df[class_df["NUMBER"].isin(selected_cars)]

    # --- Create lap-based structure ---
    gap_data = []
    for car, group in class_df.groupby("NUMBER"):
        group = group.sort_values("LAP")
        gap_data.append(group[["LAP", "ELAPSED_SECONDS"]].set_index("LAP").rename(columns={"ELAPSED_SECONDS": car}))
    merged = pd.concat(gap_data, axis=1)

    # --- Compute gaps relative to first selected car ---
    leader = selected_cars[0]
    for car in selected_cars:
        merged[car] = merged[car] - merged[leader]

    merged = merged.reset_index()

    # --- Plot ---
    fig = go.Figure()

    for car in selected_cars:
        color = None
        car_team = (
            df[df["NUMBER"] == car]["TEAM"].iloc[0]
            if not df[df["NUMBER"] == car]["TEAM"].empty
            else ""
        )
        for key, col in team_colors.items():
            if key.lower() in car_team.lower():
                color = col
                break
        color = color or "#888888"

        fig.add_trace(
            go.Scatter(
                x=merged["LAP"],
                y=merged[car],
                mode="lines",
                name=f"{car} — {car_team}",
                line=dict(color=color, width=2),
            )
        )

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white", size=14),
        xaxis_title="Lap Number",
        yaxis_title=f"Gap to Car {leader} (s)",
        title=f"Time Gap Comparison — {selected_class}",
        title_font=dict(size=22),
        legend=dict(
            bgcolor="rgba(0,0,0,0.4)",
            bordercolor="gray",
            borderwidth=1
        ),
    )

    fig.update_yaxes(autorange=True)
    st.plotly_chart(fig, use_container_width=True)
