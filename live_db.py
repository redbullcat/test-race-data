"""
live_db.py — Read the live SQLite database and return a dataframe
in the same format as load_race() from data_loader.py.

Used by streamlit_app.py when Live mode is enabled.
"""

from __future__ import annotations

import os
import platform
import sqlite3
import pandas as pd

# Default database path — matches live_collector.py
if platform.system() == "Windows":
    DEFAULT_DB = r"G:\My Drive\ontheapex_live.db"
else:
    DEFAULT_DB = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-philip.e.oakley@gmail.com/My Drive/ontheapex_live.db"
    )


def live_db_available(db_path: str = DEFAULT_DB) -> bool:
    """Return True if the live database exists and has at least one lap."""
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        n = conn.execute("SELECT COUNT(*) FROM laps").fetchone()[0]
        conn.close()
        return n > 0
    except Exception:
        return False


def load_live_race(db_path: str = DEFAULT_DB) -> pd.DataFrame:
    """
    Load all laps from the live database and return a DataFrame
    with the same columns as the Al-Kamel race CSV loader produces.
    """
    if not os.path.exists(db_path):
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(
            """
            SELECT
                l.NUMBER,
                l.TEAM,
                l.CLASS,
                l.DRIVER_NAME,
                l.LAP_NUMBER,
                l.LAP_TIME,
                l.LAP_TIME_SECONDS,
                l.S1,
                l.S2,
                l.S3,
                l.ELAPSED_SECONDS,
                l.FLAG_AT_FL,
                l.PIT,
                l.IS_VALID,
                l.LAP_COLOR,
                l.POSITION,
                l.pid,
                l.session_id
            FROM laps l
            ORDER BY l.ELAPSED_SECONDS, l.LAP_NUMBER
            """,
            conn
        )
        conn.close()
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    # Match Al-Kamel convention for pit laps
    df["CROSSING_FINISH_LINE_IN_PIT"] = df["PIT"].apply(
        lambda x: "B" if x == 1 else ""
    )

    # Ensure correct dtypes
    df["LAP_NUMBER"]       = pd.to_numeric(df["LAP_NUMBER"], errors="coerce")
    df["LAP_TIME_SECONDS"] = pd.to_numeric(df["LAP_TIME_SECONDS"], errors="coerce")
    df["ELAPSED_SECONDS"]  = pd.to_numeric(df["ELAPSED_SECONDS"], errors="coerce")

    for col in ("NUMBER", "TEAM", "CLASS", "DRIVER_NAME", "LAP_TIME",
                "FLAG_AT_FL", "S1", "S2", "S3"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


def get_session_meta(db_path: str = DEFAULT_DB) -> dict:
    if not os.path.exists(db_path):
        return {}
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT key, value FROM session_meta").fetchall()
        conn.close()
        return {k: v for k, v in rows}
    except Exception:
        return {}


def get_live_stats(db_path: str = DEFAULT_DB) -> dict:
    if not os.path.exists(db_path):
        return {}
    try:
        conn = sqlite3.connect(db_path)
        n_laps      = conn.execute("SELECT COUNT(*) FROM laps").fetchone()[0]
        max_lap     = conn.execute("SELECT MAX(LAP_NUMBER) FROM laps").fetchone()[0]
        max_elapsed = conn.execute("SELECT MAX(ELAPSED_SECONDS) FROM laps").fetchone()[0]
        last_rec    = conn.execute(
            "SELECT recorded_at FROM laps ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return {
            "n_laps":        n_laps,
            "max_lap":       max_lap or 0,
            "elapsed_hours": (max_elapsed or 0) / 3600,
            "last_recorded": last_rec[0] if last_rec else None,
        }
    except Exception:
        return {}
