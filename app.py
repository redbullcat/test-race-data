import streamlit as st
import pandas as pd
import csv

from pace_chart import show_pace_chart
from lap_position_chart import show_lap_position_chart

def main():
    st.title("Race Data Visualization")

    uploaded_file = st.file_uploader("Upload your race CSV file", type=["csv"])

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

    if uploaded_file:
        sample = uploaded_file.read().decode('utf-8-sig')
        uploaded_file.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        delimiter = dialect.delimiter

        df = pd.read_csv(uploaded_file, sep=delimiter, encoding='utf-8-sig')
        df.columns = df.columns.str.strip().str.replace('\ufeff', '').str.upper()

        required_cols = {"NUMBER", "LAP_TIME", "TEAM", "CLASS", "LAP_NUMBER", "ELAPSED"}
        if not required_cols.issubset(df.columns):
            st.error(f"❌ CSV must include {required_cols}. Found columns: {list(df.columns)}")
            st.stop()

        df["NUMBER"] = df["NUMBER"].astype(str)
        mask_am = (df["TEAM"].str.lower() == "aston martin thor team") & (df["NUMBER"].isin(["7", "9"]))
        df.loc[mask_am & (df["NUMBER"] == "7"), "NUMBER"] = "007"
        df.loc[mask_am & (df["NUMBER"] == "9"), "NUMBER"] = "009"

        available_classes = df["CLASS"].dropna().unique().tolist()
        selected_classes = st.multiselect("Select classes to include:", available_classes, default=available_classes)
        df = df[df["CLASS"].isin(selected_classes)]

        percentage_options = [0, 20, 40, 60, 80, 100]
        top_percent = st.select_slider("Select % of fastest laps per car to include:", options=percentage_options, value=100)

        if top_percent == 0:
            st.warning("⚠️ You won't see any data because 0% of laps are selected.")
            st.stop()

        available_cars = df["NUMBER"].dropna().unique().tolist()
        selected_cars = st.multiselect("Select cars to include (hide others):", options=sorted(available_cars), default=sorted(available_cars))
        df = df[df["NUMBER"].isin(selected_cars)]

        # Pass team_colors to the charts
        show_pace_chart(df, selected_cars, top_percent, selected_classes, team_colors)
        show_lap_position_chart(df, selected_cars, selected_classes, team_colors)

    else:
        st.info("Please upload a race CSV file to generate the charts.")

if __name__ == "__main__":
    main()
