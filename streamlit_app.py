import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Race Pace Analysis",
    page_icon="🏁",
    layout="wide"
)

st.title("🏁 Race Pace Analysis")
st.write("Upload your race CSV to visualize the average pace per car.")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload race CSV file", type=["csv"])

if uploaded_file:
    # Read CSV
    df = pd.read_csv(uploaded_file, sep=None, engine="python")  # auto-detects delimiter

    # Ensure LAP_TIME column is valid
    if "LAP_TIME" not in df.columns or "NUMBER" not in df.columns:
        st.error("CSV must include 'NUMBER' and 'LAP_TIME' columns.")
    else:
        # Convert LAP_TIME from string (mm:ss.xxx) to seconds
        def to_seconds(lap_time):
            try:
                m, s = lap_time.split(":")
                return float(m) * 60 + float(s)
            except:
                return None

        df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(to_seconds)

        # Filter out invalid / pit laps
        df = df[
            (df["LAP_TIME_SECONDS"].notnull()) &
            (df["CROSSING_FINISH_LINE_IN_PIT"] == False)
        ]

        # Compute average lap time per car
        avg_times = (
            df.groupby(["NUMBER", "TEAM"], as_index=False)["LAP_TIME_SECONDS"]
            .mean()
            .sort_values("LAP_TIME_SECONDS")
        )

        # Format for display
        avg_times["Average Lap"] = avg_times["LAP_TIME_SECONDS"].apply(lambda x: f"{x/60:.2f} min")

        # --- Plot ---
        fig = px.bar(
            avg_times,
            x="NUMBER",
            y="LAP_TIME_SECONDS",
            color="TEAM",
            text="Average Lap",
            title="Average Lap Time per Car",
            labels={"NUMBER": "Car Number", "LAP_TIME_SECONDS": "Average Lap Time (s)"},
        )

        fig.update_layout(
            plot_bgcolor="#1e1e1e",
            paper_bgcolor="#1e1e1e",
            font_color="white",
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="gray"),
            title_x=0.5
        )

        fig.update_traces(textposition="outside")

        st.plotly_chart(fig, use_container_width=True)

        # Optional: show table
        with st.expander("View Average Lap Times Table"):
            st.dataframe(avg_times)
else:
    st.info("👆 Upload a CSV file to begin.")
