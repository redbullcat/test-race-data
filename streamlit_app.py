import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Race Pace Analysis", page_icon="🏁", layout="wide")

st.title("🏁 Race Pace Analysis")
st.write("Upload your race CSV to visualize the average pace per car.")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload race CSV file", type=["csv"])

if uploaded_file:
    # Read CSV and handle UTF-8 BOM automatically
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine="python", encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(uploaded_file, sep="\t", encoding="utf-8-sig")

    # Clean column names
    df.columns = [c.strip() for c in df.columns]

    required_cols = {"NUMBER", "LAP_TIME"}
    if not required_cols.issubset(df.columns):
        st.error(
            f"❌ CSV must include {required_cols}. "
            f"Found columns: {list(df.columns)}"
        )
        st.stop()

    # --- Convert LAP_TIME to seconds ---
    def to_seconds(lap_time):
        try:
            m, s = str(lap_time).split(":")
            return float(m) * 60 + float(s)
        except Exception:
            return None

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(to_seconds)

    # --- Filter valid laps ---
    if "CROSSING_FINISH_LINE_IN_PIT" in df.columns:
        df = df[df["CROSSING_FINISH_LINE_IN_PIT"] == False]
    df = df[df["LAP_TIME_SECONDS"].notnull()]

    # --- Compute average lap per car ---
    group_cols = ["NUMBER"]
    if "TEAM" in df.columns:
        group_cols.append("TEAM")

    avg_times = (
        df.groupby(group_cols, as_index=False)["LAP_TIME_SECONDS"]
        .mean()
        .sort_values("LAP_TIME_SECONDS")
    )

    avg_times["Average Lap (min)"] = avg_times["LAP_TIME_SECONDS"].apply(lambda x: f"{x/60:.2f}")

    # --- Horizontal Plot ---
    fig = px.bar(
        avg_times,
        y="NUMBER",
        x="LAP_TIME_SECONDS",
        color=avg_times["TEAM"] if "TEAM" in df.columns else None,
        text="Average Lap (min)",
        orientation="h",
        title="Average Lap Time per Car",
        labels={"NUMBER": "Car Number", "LAP_TIME_SECONDS": "Average Lap Time (s)"},
    )

    fig.update_layout(
        plot_bgcolor="#1e1e1e",
        paper_bgcolor="#1e1e1e",
        font_color="white",
        yaxis=dict(autorange="reversed"),  # fastest car at top
        xaxis=dict(showgrid=True, gridcolor="gray"),
        title_x=0.5
    )

    fig.update_traces(textposition="outside")

    st.plotly_chart(fig, use_container_width=True)

    # --- Optional: Show data table ---
    with st.expander("View Average Lap Times Table"):
        st.dataframe(avg_times)

else:
    st.info("👆 Upload a CSV file to begin.")
