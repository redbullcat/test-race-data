import streamlit as st
import streamlit.components.v1 as components
import os

def show_track_analysis(_, team_colors=None):
    st.header("Track Analysis")

    TRACKS_DIR = "tracks"
    DATA_DIR = "data"

    # --- 1. Year selection ---
    years = sorted([
        d for d in os.listdir(TRACKS_DIR)
        if os.path.isdir(os.path.join(TRACKS_DIR, d))
    ])

    if not years:
        st.error("No track folders found in /tracks")
        return

    selected_year = st.selectbox("Select Year", years)

    # --- 2. Load race files for reference ---
    data_year_path = os.path.join(DATA_DIR, selected_year)
    race_files = [
        f for f in os.listdir(data_year_path)
        if f.endswith(".csv")
    ]

    if not race_files:
        st.error(f"No race data found for year {selected_year}")
        return

    # --- 3. Load SVGs for selected year ---
    tracks_path = os.path.join(TRACKS_DIR, selected_year)
    svg_files = [
        f for f in os.listdir(tracks_path)
        if f.endswith(".svg")
    ]

    if not svg_files:
        st.error(f"No SVG tracks found for year {selected_year}")
        return

    # e.g. "1-qatar.svg" → 1, qatar
    def parse_svg(filename):
        try:
            num, name = filename.replace(".svg", "").split("-", 1)
            return int(num), name, filename
        except:
            return None, None, None

    parsed = []
    for svg in svg_files:
        num, name, fname = parse_svg(svg)
        if num is not None:
            parsed.append((num, name, fname))

    parsed.sort(key=lambda x: x[0])  # sort by race order

    track_labels = [f"{num}. {name.title()}" for num, name, _ in parsed]

    selected_label = st.selectbox("Select Track", track_labels)
    idx = track_labels.index(selected_label)
    _, _, chosen_svg = parsed[idx]

    svg_path = os.path.join(tracks_path, chosen_svg)

    # --- 4. Display SVG ---
    st.markdown("### Track Layout")

    try:
        with open(svg_path, "r", encoding="utf-8") as f:
            svg = f.read()

        # Render properly using HTML component (required for full SVG support)
        components.html(svg, height=600, scrolling=False)

    except Exception as e:
        st.error(f"Error loading SVG: {e}")
