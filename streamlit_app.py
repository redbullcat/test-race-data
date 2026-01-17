import os
import pandas as pd
import streamlit as st

from pace_chart import show_pace_chart
from lap_position_chart import show_lap_position_chart
from driver_pace_chart import show_driver_pace_chart
from driver_pace_comparison_chart import show_driver_pace_comparison
from team_driver_pace_comparison import show_team_driver_pace_comparison
from results_table import show_results_table
from gap_evolution_chart import show_gap_evolution_chart
from stint_pace_chart import show_stint_pace_chart
from team_season_comparison import show_team_season_comparison
from track_analysis import show_track_analysis
from practice_analysis import show_practice_analysis

# --- Load available race data ---
DATA_DIR = "data"

# Structure: { year: { series: [races] } }
race_files = {}

for year in sorted(os.listdir(DATA_DIR)):
    year_path = os.path.join(DATA_DIR, year)
    if not os.path.isdir(year_path):
        continue

    series_dict = {}

    for series in sorted(os.listdir(year_path)):
        series_path = os.path.join(year_path, series)
        if not os.path.isdir(series_path):
            continue

        csv_files = [
            f.replace(".csv", "")
            for f in os.listdir(series_path)
            if f.endswith(".csv")
        ]

        if csv_files:
            series_dict[series] = sorted(csv_files)

    if series_dict:
        race_files[year] = series_dict

# --- Sidebar Selectors ---

st.sidebar.header("Configuration")

selected_series = st.sidebar.selectbox(
    "Series",
    ["IMSA", "FIA WEC"]
)

page = st.sidebar.selectbox(
    "Page",
    ["Overview", "Team by team", "Team season comparison", "Track analysis", "Practice / Test analysis"]
)

selected_year = st.sidebar.selectbox(
    "Year",
    sorted(race_files.keys(), reverse=True)
)

available_series_for_year = race_files[selected_year].keys()

if selected_series not in available_series_for_year:
    st.error(f"No {selected_series} data available for {selected_year}.")
    st.stop()

selected_race = st.sidebar.selectbox(
    "Race",
    race_files[selected_year][selected_series]
)

# --- Load the selected dataset ---
file_path = os.path.join(
    DATA_DIR,
    selected_year,
    selected_series,
    f"{selected_race}.csv"
)

df = pd.read_csv(file_path, delimiter=";")

# --- Clean column names ---
df.columns = df.columns.str.strip()
if "\ufeffNUMBER" in df.columns:
    df.rename(columns={"\ufeffNUMBER": "NUMBER"}, inplace=True)

# --- Aston Martin 007 / 009 fix (safe for IMSA/WEC) ---
if {"TEAM", "NUMBER"}.issubset(df.columns):
    df["NUMBER"] = df.apply(
        lambda row: (
            "007"
            if row["TEAM"] == "Aston Martin Thor Team"
            and str(row["NUMBER"]).strip() == "7"
            else "009"
            if row["TEAM"] == "Aston Martin Thor Team"
            and str(row["NUMBER"]).strip() == "9"
            else str(row["NUMBER"]).lstrip("0")
        ),
        axis=1
    )

df["NUMBER"] = df["NUMBER"].astype(str)

# --- Apply global filters checkbox ---
apply_global_filters = st.sidebar.checkbox(
    "Apply global filters",
    value=False
)

# --- Sidebar Filters ---
st.sidebar.header("Filters")

available_classes = (
    df["CLASS"].dropna().unique().tolist()
    if "CLASS" in df.columns
    else []
)

selected_classes = st.sidebar.multiselect(
    "Select Classes",
    available_classes,
    default=available_classes,
    disabled=not apply_global_filters
)

available_cars = df["NUMBER"].unique().tolist()

selected_cars = st.sidebar.multiselect(
    "Select Cars",
    available_cars,
    default=available_cars,
    disabled=not apply_global_filters
)

top_percent = st.sidebar.slider(
    "Select Top Lap Percentage",
    0,
    100,
    100,
    step=20,
    help="Use 0% to hide all data.",
    disabled=not apply_global_filters
)

if top_percent == 0:
    st.warning("You selected 0%. You won't see any data.")

# --- Team color mapping ---
team_colors = {
    'Cadillac Hertz Team JOTA': '#d4af37',
    'Peugeot TotalEnergies': '#BBD64D',
    'Ferrari AF Corse': '#d62728',
    'Toyota Gazoo Racing': '#000000',
    'BMW M Team WRT': '#2426a8',
    'Porsche Penske Motorsport': '#ffffff',
    'Alpine Endurance Team': '#2673e2',
    'Aston Martin Thor Team': '#01655c',
    'AF Corse': '#FCE903',
    'Proton Competition': '#fcfcff',
    'WRT': '#2426a8',
    'United Autosports': '#FF8000',
    'Akkodis ASP': '#ff443b',
    'Iron Dames': '#e5017d',
    'Manthey': '#0192cf',
    'Heart of Racing': '#242c3f',
    'Racing Spirit of Leman': '#428ca8',
    'Iron Lynx': '#fefe00',
    'TF Sport': '#eaaa1d'
}

# --- Page Header ---
st.header(f"{selected_year} {selected_series} – {selected_race} Analysis")

# --- Show charts ---

if page == "Overview":
    show_pace_chart(df, team_colors)
    show_driver_pace_chart(df, team_colors)
    show_lap_position_chart(df, team_colors)
    show_driver_pace_comparison(df, team_colors)
    show_results_table(df, team_colors)
    show_gap_evolution_chart(df, team_colors)
    show_stint_pace_chart(df, team_colors)

elif page == "Team by team":
    race_classes = sorted(df["CLASS"].dropna().unique())

    if not race_classes:
        st.warning("No class data available in this race.")
    else:
        tabs = st.tabs(race_classes)

        for tab, race_class in zip(tabs, race_classes):
            with tab:
                st.subheader(f"{race_class}")

                class_df = df[df["CLASS"] == race_class]

                if class_df.empty:
                    st.info("No data available for this class in this race.")
                else:
                    show_team_driver_pace_comparison(class_df, team_colors)

elif page == "Team season comparison":
    show_team_season_comparison(df, team_colors)

elif page == "Track analysis":
    show_track_analysis(df, team_colors)

elif page == "Practice / Test analysis":
    show_practice_analysis(
        data_dir=DATA_DIR,
        year=selected_year,
        series=selected_series,
        race=selected_race,
        team_colors=team_colors
    )
