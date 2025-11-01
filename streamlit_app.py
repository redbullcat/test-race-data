import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Race Pace Analysis", page_icon="🏎️", layout="wide")

st.title("🏎️ Race Pace Analysis")
st.write("Upload your race CSV to visualize the average pace per car.")

uploaded_file = st.file_uploader("Upload race CSV file", type=["csv"])

if uploaded_file:
    # --- Read CSV safely ---
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine="python", encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(uploaded_file, sep="\t", encoding="utf-8-sig")

    df.columns = [c.strip() for c in df.columns]

    required_cols = {"NUMBER", "LAP_TIME"}
    if not required_cols.issubset(df.columns):
        st.error(f"❌ CSV must include {required_cols}. Found columns: {list(df.columns)}")
        st.stop()

    # --- Parse LAP_TIME into seconds ---
    def to_seconds(lap_time):
        if pd.isna(lap_time):
            return None
        s = str(lap_time).strip()
        match = re.match(r"(\d+):(\d+\.\d+)", s)
        if match:
            m, s = match.groups()
            return float(m) * 60 + float(s)
        return None

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(to_seconds)

    # --- Handle pit flag ---
    if "CROSSING_FINISH_LINE_IN_PIT" in df.columns:
        df["CROSSING_FINISH_LINE_IN_PIT"] = df["CROSSING_FINISH_LINE_IN_PIT"].astype(str).str.lower()
        df = df[df["CROSSING_FINISH_LINE_IN_PIT"].isin(["false", "0", "no", "nan"])]

    df = df[df["LAP_TIME_SECONDS"].notnull()]

    if df.empty:
        st.warning("No valid laps found in CSV after filtering.")
        st.stop()

    # --- CLASS filter ---
    if "CLASS" in df.columns:
        available_classes = sorted(df["CLASS"].dropna().unique())
        selected_classes = st.multiselect(
            "Select race classes to include:",
            options=available_classes,
            default=available_classes,
        )
        df = df[df["CLASS"].isin(selected_classes)]
        if df.empty:
            st.warning("No data available for the selected classes.")
            st.stop()

    # --- Compute average lap time per car ---
    group_cols = ["NUMBER"]
    if "TEAM" in df.columns:
        group_cols.append("TEAM")
    if "CLASS" in df.columns:
        group_cols.append("CLASS")

    avg_times = (
        df.groupby(group_cols, as_index=False)["LAP_TIME_SECONDS"]
        .mean()
        .sort_values("LAP_TIME_SECONDS")
    )

    avg_times["Average Lap (min)"] = avg_times["LAP_TIME_SECONDS"].apply(lambda x: f"{x/60:.2f}")

    # --- Combine label for display ---
    avg_times["Label"] = avg_times["NUMBER"].astype(str)
    if "TEAM" in avg_times.columns:
        avg_times["Label"] = avg_times["NUMBER"].astype(str) + " — " + avg_times["TEAM"]

    # --- Horizontal bar chart (one per car) ---
    fig = px.bar(
        avg_times,
        y="Label",
        x="LAP_TIME_SECONDS",
        color="CLASS" if "CLASS" in avg_times.columns else None,
        text="Average Lap (min)",
        orientation="h",
        title="Average Lap Time per Car",
        labels={"Label": "Car", "LAP_TIME_SECONDS": "Average Lap Time (s)"},
    )

    fig.update_layout(
        plot_bgcolor="#1e1e1e",
        paper_bgcolor="#1e1e1e",
        font_color="white",
        yaxis=dict(autorange="reversed"),
        xaxis=dict(showgrid=True, gridcolor="gray"),
        title_x=0.5,
        height=700,
        legend_title_text="Class",
    )

    fig.update_traces(textposition="outside")

    st.plotly_chart(fig, use_container_width=True)

    # --- Table ---
    with st.expander("View Average Lap Times Table"):
        st.dataframe(avg_times)

else:
    st.info("👆 Upload a CSV file to begin.")
