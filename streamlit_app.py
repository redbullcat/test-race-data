import os
import pandas as pd
import streamlit as st
from pace_chart import show_pace_chart
from lap_position_chart import show_lap_position_chart
from driver_pace_chart import show_driver_pace_chart
from driver_pace_comparison_chart import show_driver_pace_comparison
from results_table import show_results_table
from gap_evolution_chart import show_gap_evolution_chart

# --- Load available race data ---
DATA_DIR = "data"

# Create dictionary: { year: [races] }
race_files = {}
for year in sorted(os.listdir(DATA_DIR)):
    year_path = os.path.join(DATA_DIR, year)
    if os.path.isdir(year_path):
        csv_files = [f.replace(".csv", "") for f in os.listdir(year_path) if f.endswith(".csv")]
        if csv_files:
            race_files[year] = sorted(csv_files)

# --- Sidebar Selectors ---
st.sidebar.header("Select Race")

selected_year = st.sidebar.selectbox("Year", sorted(race_files.keys(), reverse=True))
selected_race = st.sidebar.selectbox("Race", race_files[selected_year])

# Load the selected dataset
file_path = os.path.join(DATA_DIR, selected_year, f"{selected_race}.csv")
df = pd.read_csv(file_path, delimiter=";")

# --- Clean column names ---
df.columns = df.columns.str.strip()
if "\ufeffNUMBER" in df.columns:
    df.rename(columns={"\ufeffNUMBER": "NUMBER"}, inplace=True)

# --- Aston Martin 007 / 009 fix ---
df["NUMBER"] = df.apply(
    lambda row: (
        "007" if row["TEAM"] == "Aston Martin Thor Team" and str(row["NUMBER"]).strip() == "7"
        else "009" if row["TEAM"] == "Aston Martin Thor Team" and str(row["NUMBER"]).strip() == "9"
        else str(row["NUMBER"]).lstrip("0")
    ),
    axis=1
)

# Convert NUMBER column to string for consistency
df["NUMBER"] = df["NUMBER"].astype(str)

# --- Sidebar Filters ---
st.sidebar.header("Filters")

available_classes = df["CLASS"].dropna().unique().tolist()
selected_classes = st.sidebar.multiselect("Select Classes", available_classes, default=available_classes)

available_cars = df["NUMBER"].unique().tolist()
selected_cars = st.sidebar.multiselect("Select Cars", available_cars, default=available_cars)

top_percent = st.sidebar.slider(
    "Select Top Lap Percentage",
    0,
    100,
    100,
    step=20,
    help="Use 0% to hide all data."
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

# --- Show charts ---
st.header(f"{selected_year} {selected_race} Analysis")

show_pace_chart(df, team_colors)
show_lap_position_chart(df, [], [], team_colors)
show_driver_pace_chart(df, selected_cars, top_percent, selected_classes, team_colors)
show_driver_pace_comparison(df, team_colors)
show_results_table(df, team_colors)
show_gap_evolution_chart(df, team_colors)
