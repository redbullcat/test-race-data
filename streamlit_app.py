import streamlit as st
import pandas as pd
import plotly.express as px
import csv

st.set_page_config(page_title="Race Pace Chart", layout="wide")

st.title("Average Race Pace by Car")

uploaded_file = st.file_uploader("Upload your race CSV file", type=["csv"])

if uploaded_file:
    # Auto-detect delimiter and clean headers
    sample = uploaded_file.read().decode('utf-8-sig')
    uploaded_file.seek(0)
    dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    delimiter = dialect.delimiter

    df = pd.read_csv(uploaded_file, sep=delimiter, encoding='utf-8-sig')
    df.columns = df.columns.str.strip().str.replace('\ufeff', '').str.upper()

    required_cols = {"NUMBER", "LAP_TIME", "TEAM", "CLASS"}
    if not required_cols.issubset(df.columns):
        st.error(f"❌ CSV must include {required_cols}. Found columns: {list(df.columns)}")
        st.stop()

    def lap_to_seconds(x):
        try:
            mins, secs = x.split(":")
            return int(mins) * 60 + float(secs)
        except:
            return None

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
    df = df.dropna(subset=["LAP_TIME_SECONDS"])

    available_classes = df["CLASS"].dropna().unique().tolist()
    selected_classes = st.multiselect(
        "Select classes to include:", available_classes, default=available_classes
    )
    df = df[df["CLASS"].isin(selected_classes)]

    # --- New slider for top % laps filter ---
    percentage_options = [20, 40, 60, 80, 100]
    top_percent = st.select_slider(
        "Select % of fastest laps per car to include:",
        options=percentage_options,
        value=100
    )

    # Filter laps to top X% per car
    def filter_top_percent_laps(df, percent):
        filtered_dfs = []
        for car_number, group in df.groupby("NUMBER"):
            group_sorted = group.sort_values("LAP_TIME_SECONDS")
            n_laps = len(group_sorted)
            n_keep = max(1, int(n_laps * percent / 100))  # Keep at least 1 lap per car
            filtered_dfs.append(group_sorted.head(n_keep))
        return pd.concat(filtered_dfs)

    df = filter_top_percent_laps(df, top_percent)

    avg_df = (
        df.groupby(["NUMBER", "TEAM", "CLASS"], as_index=False)["LAP_TIME_SECONDS"]
        .mean()
        .sort_values("LAP_TIME_SECONDS", ascending=True)
    )

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

    def get_team_color(team):
        for key, color in team_colors.items():
            if key.lower() in team.lower():
                return color
        return "#888888"

    avg_df["color"] = avg_df["TEAM"].apply(get_team_color)

    avg_df["Label"] = avg_df["NUMBER"].astype(str) + " — " + avg_df["TEAM"]

    fig = px.bar(
        avg_df,
        y="Label",
        x="LAP_TIME_SECONDS",
        color="TEAM",
        orientation="h",
        color_discrete_map={team: col for team, col in zip(avg_df["TEAM"], avg_df["color"])},
    )

    fig.update_yaxes(
        type='category',
        categoryorder='array',
        categoryarray=avg_df["Label"]
    )

    x_min = avg_df["LAP_TIME_SECONDS"].min() - 0.5
    x_max = avg_df["LAP_TIME_SECONDS"].max() + 0.5
    fig.update_xaxes(range=[x_min, x_max])

    fig.update_layout(
        plot_bgcolor="#2b2b2b",
        paper_bgcolor="#2b2b2b",
        font=dict(color="white", size=14),
        xaxis_title="Average Lap Time (s)",
        yaxis_title="Car Number — Team",
        title="Average Race Pace by Car",
        title_font=dict(size=22),
        showlegend=True,
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Please upload a race CSV file to generate the chart.")
