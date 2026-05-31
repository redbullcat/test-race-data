"""
manifest.py — lightweight JSON manifest of all data files.

The manifest (data/manifest.json) is written by generate_manifest() and read
by load_manifest(). It stores a nested dict identical to load_file_index() but
also includes per-event metadata (lap counts, file sizes) for display in the UI.

Call generate_manifest() after any download or file reorganisation.
"""

from __future__ import annotations

import json
import os

import pandas as pd

from config import DATA_DIR, SESSION_TYPES

MANIFEST_PATH = os.path.join(DATA_DIR, "manifest.json")


def _count_laps(csv_path: str) -> int:
    """Return number of data rows in a CSV (proxy for lap count). Fast."""
    try:
        # Count lines minus header, no full parse
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return 0


def _file_size_kb(path: str) -> int:
    try:
        return os.path.getsize(path) // 1024
    except Exception:
        return 0


def generate_manifest(data_dir: str = DATA_DIR) -> dict:
    """
    Walk data_dir and build the manifest dict, then write it to manifest.json.
    Returns the manifest dict.
    """
    index: dict = {}

    if not os.path.isdir(data_dir):
        return index

    for series in sorted(os.listdir(data_dir)):
        if series.startswith(".") or series == "manifest.json":
            continue
        series_path = os.path.join(data_dir, series)
        if not os.path.isdir(series_path):
            continue

        years: dict = {}
        for year in sorted(os.listdir(series_path), reverse=True):
            if year.startswith("."):
                continue
            year_path = os.path.join(series_path, year)
            if not os.path.isdir(year_path):
                continue

            races: dict = {}
            for race in sorted(os.listdir(year_path)):
                if race.startswith("."):
                    continue
                race_path = os.path.join(year_path, race)
                if not os.path.isdir(race_path):
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
                    if not csvs:
                        continue

                    files_meta = []
                    for csv in csvs:
                        full = os.path.join(session_path, csv)
                        files_meta.append({
                            "filename": csv,
                            "size_kb": _file_size_kb(full),
                            "laps": _count_laps(full),
                        })
                    sessions[session_type] = files_meta

                if sessions:
                    races[race] = sessions

            if races:
                years[year] = races

        if years:
            index[series] = years

    with open(MANIFEST_PATH, "w") as f:
        json.dump(index, f)

    return index


def load_manifest(data_dir: str = DATA_DIR) -> dict | None:
    """
    Load manifest.json if it exists and is newer than no files have changed.
    Returns None if manifest doesn't exist (fall back to load_file_index).
    """
    path = os.path.join(data_dir, "manifest.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def manifest_to_file_index(manifest: dict) -> dict:
    """
    Convert manifest format (with metadata dicts) to the simple
    { series: { year: { race: { session_type: [filename, …] } } } }
    format that the rest of the app expects.
    """
    index: dict = {}
    for series, years in manifest.items():
        index[series] = {}
        for year, races in years.items():
            index[series][year] = {}
            for race, sessions in races.items():
                index[series][year][race] = {}
                for session_type, files_meta in sessions.items():
                    index[series][year][race][session_type] = [
                        f["filename"] for f in files_meta
                    ]
    return index


def get_event_meta(manifest: dict, series: str, year: str, race: str) -> dict:
    """
    Return metadata for a specific race event from the manifest.
    Returns dict with 'laps', 'size_kb', 'sessions' keys.
    """
    try:
        sessions = manifest[series][year][race]
        race_sessions = sessions.get("race", [])
        total_laps = sum(f["laps"] for f in race_sessions)
        total_kb = sum(f["size_kb"] for f in race_sessions)
        return {
            "laps": total_laps,
            "size_kb": total_kb,
            "sessions": list(sessions.keys()),
        }
    except (KeyError, TypeError):
        return {}
