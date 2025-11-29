import streamlit as st
import os
import base64

def render_svg(svg_content):
    b64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    html = f'<img src="data:image/svg+xml;base64,{b64}" style="position: relative; left: 0; top: 0; width: 400px; height: auto;" />'
    st.markdown(html, unsafe_allow_html=True)

def list_years_and_tracks(tracks_root='tracks', data_root='data'):
    years = sorted([d for d in os.listdir(tracks_root) if os.path.isdir(os.path.join(tracks_root, d))])
    st.write(f"Available years found in '{tracks_root}': {years}")

    year = st.selectbox("Select Year", years)

    track_dir = os.path.join(tracks_root, year)
    svg_files = sorted([f for f in os.listdir(track_dir) if f.endswith('.svg')])
    st.write(f"SVG files found for year {year}: {svg_files}")

    # strip .svg to get track names
    track_names = [os.path.splitext(f)[0] for f in svg_files]
    track = st.selectbox("Select Track", track_names)

    return year, track

def show_track_analysis():
    st.title("Track SVG Viewer")

    year, track = list_years_and_tracks()

    svg_path = os.path.join('tracks', year, f'{track}.svg')
    st.write(f"Attempting to load SVG file from: {svg_path}")

    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        st.write(f"Loaded SVG content preview (first 500 chars):")
        st.code(svg_content[:500], language='xml')
        render_svg(svg_content)
    except Exception as e:
        st.error(f"Failed to load SVG file: {e}")

    data_path = os.path.join('data', year, f'{track}.csv')
    if os.path.exists(data_path):
        st.write(f"Data CSV found for {track} in {year}: {data_path}")
        # Optional: load CSV here if needed
    else:
        st.write(f"No data CSV found for {track} in {year}")

def main():
    show_track_analysis()

if __name__ == '__main__':
    main()
