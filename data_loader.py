"""
data_loader.py — all CSV loading and preprocessing behind st.cache_data.

Directory structure expected:
    data/
        {SERIES}/           e.g. WEC, IMSA, ELMS
            {year}/         e.g. 2026
                {race}/     e.g. spa, daytona  (lowercase, hyphenated)
                    race/           → one CSV  (full-race analysis)
                    practice/       → one or more CSVs (practice1.csv, practice2.csv …)
                    qualifying/     → one or more CSVs (qualifying_hypercar.csv …)
"""

from __future__ import annotations

import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATA_DIR, SESSION_TYPES
from utils import lap_to_seconds

# ---------------------------------------------------------------------------
# File index
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_file_index(data_dir: str = DATA_DIR) -> dict:
    """
    Walk data_dir and return a nested dict:
        { series: { year: { race: { session_type: [filename, …] } } } }

    Only directories that actually contain CSV files appear in the index.
    session_type is one of 'race', 'practice', 'qualifying', 'test' (from SESSION_TYPES).
    """
    index: dict = {}

    if not os.path.isdir(data_dir):
        return index

    for series in sorted(os.listdir(data_dir)):
        series_path = os.path.join(data_dir, series)
        if not os.path.isdir(series_path) or series.startswith("."):
            continue

        years: dict = {}
        for year in sorted(os.listdir(series_path), reverse=True):
            year_path = os.path.join(series_path, year)
            if not os.path.isdir(year_path) or year.startswith("."):
                continue

            races: dict = {}
            for race in sorted(os.listdir(year_path)):
                race_path = os.path.join(year_path, race)
                if not os.path.isdir(race_path) or race.startswith("."):
                    continue

                sessions: dict = {}
                for session_type in SESSION_TYPES:
                    session_path = os.path.join(race_path, session_type)
                    if not os.path.isdir(session_path):
                        continue
                    csvs = sorted(
                        f for f in os.listdir(session_path)
                        if f.lower().endswith(".csv") and not f.startswith(".")
                    )
                    if csvs:
                        sessions[session_type] = csvs

                if sessions:
                    races[race] = sessions

            if races:
                years[year] = races

        if years:
            index[series] = years

    return index


# ---------------------------------------------------------------------------
# Race start date (from filename like race_20260507.csv or just race.csv)
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"_(\d{8})")


@st.cache_data(show_spinner=False)
def parse_race_start_date(filename: str):
    m = _DATE_RE.search(filename)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Core race loader
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading race data…")
def load_race(file_path: str, year: str, series: str) -> pd.DataFrame:
    """
    Load and fully preprocess a race CSV.
    Adds: YEAR, SERIES, CAR_ID, LAP_TIME_SECONDS, LAP_NUMBER (numeric), ELAPSED_SECONDS.
    """
    df = pd.read_csv(file_path, delimiter=";", dtype=str)
    df.columns = df.columns.str.strip()

    if "\ufeffNUMBER" in df.columns:
        df.rename(columns={"\ufeffNUMBER": "NUMBER"}, inplace=True)

    for col in ("NUMBER", "TEAM", "CLASS", "DRIVER_NAME"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df["YEAR"] = year
    df["SERIES"] = series
    df["CAR_ID"] = (
        df["YEAR"].astype(str) + "_"
        + df["SERIES"].astype(str) + "_"
        + df["TEAM"] + "_"
        + df["NUMBER"]
    )

    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
    df["LAP_NUMBER"] = pd.to_numeric(
        df.get("LAP_NUMBER", pd.Series(dtype=float)), errors="coerce"
    )
    if "ELAPSED" in df.columns:
        df["ELAPSED_SECONDS"] = df["ELAPSED"].apply(lap_to_seconds)

    return df


# ---------------------------------------------------------------------------
# Practice / session loader
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading session data…")
def load_practice_sessions(
    session_dir: str,
    selected_files: tuple[str, ...],
) -> pd.DataFrame:
    """
    Load and concatenate one or more practice CSVs from session_dir.
    selected_files is a tuple of filenames (for hashability).
    Adds PRACTICE_SESSION column derived from the filename.
    """
    frames = []
    for filename in sorted(selected_files):
        path = os.path.join(session_dir, filename)
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, delimiter=";", dtype=str)
        df.columns = df.columns.str.strip()

        if "\ufeffNUMBER" in df.columns:
            df.rename(columns={"\ufeffNUMBER": "NUMBER"}, inplace=True)

        for col in ("NUMBER", "TEAM", "CLASS", "DRIVER_NAME"):
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
        df["LAP_NUMBER"] = pd.to_numeric(
            df.get("LAP_NUMBER", pd.Series(dtype=float)), errors="coerce"
        )
        # Session label: strip .csv, replace _ with space, title-case
        label = os.path.splitext(filename)[0].replace("_", " ").title()
        df["PRACTICE_SESSION"] = label
        frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# Season comparison loader
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading season data…")
def load_season_races(
    series: str, year: str, data_dir: str = DATA_DIR
) -> dict[str, pd.DataFrame]:
    """
    Load all race CSVs for a given series+year.
    Returns { race_display_name: dataframe }.
    """
    year_path = os.path.join(data_dir, series, year)
    if not os.path.isdir(year_path):
        return {}

    races: dict[str, pd.DataFrame] = {}
    for race in sorted(os.listdir(year_path)):
        race_path = os.path.join(year_path, race)
        if not os.path.isdir(race_path):
            continue
        race_dir = os.path.join(race_path, "race")
        if not os.path.isdir(race_dir):
            continue
        csvs = [f for f in os.listdir(race_dir) if f.lower().endswith(".csv")]
        if not csvs:
            continue
        # Take the first race CSV (should only be one)
        file_path = os.path.join(race_dir, csvs[0])
        display = race.replace("-", " ").title()
        try:
            races[display] = load_race(file_path, year, series)
        except Exception:
            pass

    return races
