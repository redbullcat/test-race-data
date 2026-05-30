"""track_analysis.py — Track SVG viewer."""

import base64
import os

import streamlit as st

from config import TRACKS_DIR


def show_track_analysis(df=None, team_colors=None):
    """Display a track map SVG. df and team_colors are accepted but not required."""
    st.subheader("Track Map")

    if not os.path.isdir(TRACKS_DIR):
        st.info("No track SVG files found.")
        return

    years = sorted([d for d in os.listdir(TRACKS_DIR) if os.path.isdir(os.path.join(TRACKS_DIR, d))])
    if not years:
        st.info("No track data available.")
        return

    year = st.selectbox("Year:", years, key="track_year")
    track_dir = os.path.join(TRACKS_DIR, year)

    svg_files = sorted([f for f in os.listdir(track_dir) if f.lower().endswith(".svg")])
    if not svg_files:
        st.info(f"No SVG track maps found for {year}.")
        return

    track_names = [os.path.splitext(f)[0] for f in svg_files]
    selected = st.selectbox("Track:", track_names, key="track_name")

    svg_path = os.path.join(track_dir, f"{selected}.svg")
    try:
        with open(svg_path, "r", encoding="utf-8") as f:
            svg_content = f.read()
    except Exception as e:
        st.error(f"Could not load track map: {e}")
        return

    b64 = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
    st.markdown(
        f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%; max-width:600px; height:auto;" />',
        unsafe_allow_html=True,
    )
