import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Race Pace Chart", layout="wide")

st.title("Average Race Pace by Car")

uploaded_file = st.file_uploader("Upload your race CSV file", type=["csv"])

if uploaded_file:
    # Handle potential BOM character in header
    df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8-sig')
    df.columns = df.columns.str.strip().str.replace('\ufeff', '').str.upper()

    # Ensure needed columns exist
    required_cols = {"NUMBER", "LAP_TIME", "TEAM", "CLASS"}
    if not required_cols.issubset(df.columns):
        st.error(f"CSV must include {required_cols}. Found columns: {list(df.columns)}")
        st.stop()

    # Convert LAP_TIME to seconds
    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SECONDS"])

    # Filter by class
    available_classes = df["CLASS"].dropna().unique().tolist()
    selected_classes = st.multiselect(
        "Select classes to include:", available_classes, default=available_classes
    )

    df = df[df["CLASS"].isin(selected_classes)]

    # Calculate average pace per car
    avg_df = (
        df.groupby(["NUMBER", "TEAM", "CLASS"], as_index=False)["LAP_TIME_SECONDS"]
        .mean()
        .sort_values("LAP_TIME_SECONDS", ascending=True)
    )

    # Color map for Hypercar teams
    team_colors = {
        'Cadillac Hertz Team JOTA': '#d4af37',
        'Peugeot TotalEnergies': '#BBD64D',
        'Ferrari AF Corse': '#d62728',
        'Toyota Gazoo Racing': '#000000',
        'BMW M Team WRT': '#2426a8',
        'Porsche Penske Motorsport': '#ffffff',
        'Alpine Endurance Team': '#2673e2',
        'Aston Martin Thor Team': '#01655c',
        "AF Corse": "#FCE903",
        "Proton Competition": "#fcfcff"
    }

    # Assign colors based on team name match (case-insensitive partial)
    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"  # default grey for unmatched teams

    avg_df["color"] = avg_df["TEAM"].apply(get_team_color)

    # Plot (horizontal bar chart)
    fig = px.bar(
        avg_df,
        y="NUMBER",
        x="LAP_TIME_SECONDS",
        color="TEAM",
        orientation="h",
        text="TEAM",
        color_discrete_map={team: col for team, col in zip(avg_df["TEAM"], avg_df["color"])},
    )

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white", size=14),
        xaxis_title="Average Lap Time (s)",
        yaxis_title="Car Number",
        title="Average Race Pace by Car",
        title_font=dict(size=22),
        showlegend=True,
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Please upload a race CSV file to generate the chart.")
