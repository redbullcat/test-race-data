import streamlit as st
import os
import base64

def render_svg(svg_content):
    b64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    html = f'<img src="data:image/svg+xml;base64,{b64}" style="position: relative; left: 0; top: 0; width: 400px; height: auto;" />'
    st.markdown(html, unsafe_allow_html=True)

def list_years_and_tracks(tracks_root='tracks', data_root='data'):
    years = sorted([d for d in os.listdir(tracks_root) if os.path.isdir(os.path.join(tracks_root, d))])
    year = st.selectbox("Select Year", years)

    track_dir = os.path.join(tracks_root, year)
    svg_files = sorted([f for f in os.listdir(track_dir) if f.endswith('.svg')])
    # strip .svg to get track names
    track_names = [os.path.splitext(f)[0] for f in svg_files]
    track = st.selectbox("Select Track", track_names)

    return year, track

def show_track_analysis():
    st.title("Track SVG Viewer")

    year, track = list_years_and_tracks()

    svg_path = os.path.join('tracks', year, f'{track}.svg')
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        render_svg(svg_content)
    except Exception as e:
        st.error(f"Failed to load SVG file: {e}")

    # Optional: load and display data CSV too
    data_path = os.path.join('data', year, f'{track}.csv')
    if os.path.exists(data_path):
        st.write(f"Data CSV found for {track} in {year}")
        # You could load it with pandas if needed
        # import pandas as pd
        # df = pd.read_csv(data_path)
        # st.dataframe(df.head())
    else:
        st.write(f"No data CSV found for {track} in {year}")

if __name__ == '__main__':
    main()
