"""
data_loader.py — all CSV loading and preprocessing behind st.cache_data.

Rules:
  - Every chart module imports from here instead of reading CSVs itself.
  - No chart module calls lap_to_seconds or parse_hour_with_rollover —
    those are applied once here and the result reused everywhere.
  - cache keys are file paths + metadata so Streamlit invalidates correctly.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATA_DIR
from utils import lap_to_seconds, parse_hour_with_rollover

# ---------------------------------------------------------------------------
# File index (which races/sessions exist on disk)
# ---------------------------------------------------------------------------

_RACE_RE = re.compile(r"^(.+)\.csv$", re.IGNORECASE)
_SESSION_RE = re.compile(r"^(.+?)_(practice|session)(\d+)\.csv$", re.IGNORECASE)
_DATE_RE = re.compile(r"_(\d{8})")


@st.cache_data(show_spinner=False)
def load_file_index(data_dir: str = DATA_DIR) -> dict:
    """
    Walk data_dir and return a nested dict:
        { year: { series: { event_key: { race_file, sessions } } } }

    event_key is the lowercased base filename (e.g. 'qatar', 'daytona').
    """
    index: dict = {}

    for year in sorted(os.listdir(data_dir)):
        year_path = os.path.join(data_dir, year)
        if not os.path.isdir(year_path):
            continue

        series_dict: dict = {}

        for series in sorted(os.listdir(year_path)):
            series_path = os.path.join(year_path, series)
            if not os.path.isdir(series_path):
                continue

            events: dict = {}
            for filename in os.listdir(series_path):
                if not filename.lower().endswith(".csv"):
                    continue

                session_match = _SESSION_RE.match(filename)
                if session_match:
                    base = session_match.group(1).lower()
                    event = events.setdefault(base, {"race_file": None, "sessions": []})
                    event["sessions"].append(filename)
                    continue

                race_match = _RACE_RE.match(filename)
                if race_match:
                    base = race_match.group(1).lower()
                    event = events.setdefault(base, {"race_file": None, "sessions": []})
                    event["race_file"] = filename

            if events:
                series_dict[series] = events

        if series_dict:
            index[year] = series_dict

    return index


# ---------------------------------------------------------------------------
# Race start date (extracted from filename like Daytona_20260124.csv)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def parse_race_start_date(filename: str):
    """Return datetime.date parsed from an _YYYYMMDD suffix in the filename, or None."""
    m = _DATE_RE.search(filename)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Core race loader — called once per file, result shared by all charts
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading race data…")
def load_race(file_path: str, year: str, series: str) -> pd.DataFrame:
    """
    Load and fully preprocess a race CSV.

    Columns added / normalised:
      YEAR, SERIES, CAR_ID        — identity
      LAP_TIME_SECONDS            — lap time as float seconds
      LAP_NUMBER                  — numeric
      ELAPSED_SECONDS             — total elapsed race time as float seconds

    The returned DataFrame is the single source of truth for all race charts.
    """
    df = pd.read_csv(file_path, delimiter=";")
    df.columns = df.columns.str.strip()

    # Fix UTF-8 BOM on NUMBER column (common in Al-Kamel exports)
    if "\ufeffNUMBER" in df.columns:
        df.rename(columns={"\ufeffNUMBER": "NUMBER"}, inplace=True)

    # Strip whitespace from key string columns
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

    # Lap time → seconds
    df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)

    # Lap number → numeric
    df["LAP_NUMBER"] = pd.to_numeric(df.get("LAP_NUMBER", pd.Series(dtype=float)), errors="coerce")

    # ELAPSED → seconds
    if "ELAPSED" in df.columns:
        df["ELAPSED_SECONDS"] = df["ELAPSED"].apply(lap_to_seconds)

    return df


# ---------------------------------------------------------------------------
# Practice / session loader
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading session data…")
def load_practice_sessions(
    session_files: dict[int, str],
    selected_sessions: tuple[int, ...],
) -> pd.DataFrame:
    """
    Load and concatenate multiple practice/session CSVs.

    Parameters
    ----------
    session_files   : { session_number: absolute_file_path }
    selected_sessions : tuple of session numbers to load (tuple for hashability)

    Returns a single concatenated DataFrame with a PRACTICE_SESSION column.
    """
    frames = []
    for session_num in sorted(selected_sessions):
        path = session_files.get(session_num)
        if path is None or not os.path.exists(path):
            continue
        df = pd.read_csv(path, delimiter=";")
        df.columns = df.columns.str.strip()

        if "\ufeffNUMBER" in df.columns:
            df.rename(columns={"\ufeffNUMBER": "NUMBER"}, inplace=True)

        for col in ("NUMBER", "TEAM", "CLASS", "DRIVER_NAME"):
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        df["LAP_TIME_SECONDS"] = df["LAP_TIME"].apply(lap_to_seconds)
        df["LAP_NUMBER"] = pd.to_numeric(df.get("LAP_NUMBER", pd.Series(dtype=float)), errors="coerce")
        df["PRACTICE_SESSION"] = f"Session {session_num}"
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Season comparison loader — loads all races for a year+series
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading season data…")
def load_season_races(year: str, series: str, data_dir: str = DATA_DIR) -> dict[str, pd.DataFrame]:
    """
    Load every race CSV for a given year+series.
    Returns { event_display_name: dataframe }.
    """
    series_path = os.path.join(data_dir, year, series)
    if not os.path.isdir(series_path):
        return {}

    races: dict[str, pd.DataFrame] = {}
    for filename in sorted(os.listdir(series_path)):
        if not filename.lower().endswith(".csv"):
            continue
        # Skip practice/session files
        if _SESSION_RE.match(filename):
            continue
        file_path = os.path.join(series_path, filename)
        name = filename.replace(".csv", "").replace("_", " ").title()
        try:
            df = load_race(file_path, year, series)
            races[name] = df
        except Exception:
            pass

    return races
