"""
utils.py — shared helpers used across all chart modules.

Single source of truth for:
  - lap time parsing
  - HOUR column parsing with midnight rollover
  - team colour lookup
  - lap range formatting
  - top-N% lap filtering
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Lap time parsing
# ---------------------------------------------------------------------------

def lap_to_seconds(value) -> float | None:
    """
    Parse a lap time string in 'M:SS.sss' or 'H:MM:SS.sss' format to seconds.
    Returns None for any value that cannot be parsed.
    """
    try:
        parts = str(value).strip().split(":")
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        elif len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        pass
    return None


def seconds_to_laptime(seconds: float) -> str:
    """Format a seconds value back to 'M:SS.sss' display string."""
    if pd.isna(seconds):
        return ""
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:06.3f}"


# ---------------------------------------------------------------------------
# HOUR column → absolute datetime with midnight rollover (per-car)
# ---------------------------------------------------------------------------

def parse_hour_with_rollover(
    df: pd.DataFrame,
    race_start_date,
    group_col: str = "NUMBER",
) -> pd.Series:
    """
    Convert the 'HOUR' column (hh:mm:ss[.sss]) to absolute datetimes.

    Handles midnight rollover correctly: if a car's next lap time is earlier
    than the previous one, we increment the date by one day.

    Parameters
    ----------
    df : DataFrame that must contain 'HOUR' and group_col columns.
    race_start_date : datetime.date — the calendar date the race started.
    group_col : column to group by (NUMBER for races, can differ for practice).

    Returns
    -------
    pd.Series of datetime64[ns], indexed identically to df.
    """
    def _parse_time(val):
        for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
            try:
                return datetime.strptime(str(val).strip(), fmt).time()
            except Exception:
                continue
        return None

    result = pd.Series(index=df.index, dtype="datetime64[ns]")

    for car_id, car_df in df.sort_values("LAP_NUMBER").groupby(group_col):
        current_date = race_start_date
        last_time = None
        for idx, row in car_df.iterrows():
            t = _parse_time(row["HOUR"])
            if t is None:
                result.loc[idx] = pd.NaT
                continue
            if last_time is not None and t < last_time:
                current_date += timedelta(days=1)
            last_time = t
            result.loc[idx] = datetime.combine(current_date, t)

    return result


# ---------------------------------------------------------------------------
# Team colour lookup
# ---------------------------------------------------------------------------

def get_team_color(team: str, team_colors: dict) -> str:
    """
    Fuzzy-match a team name against the team_colors dict.
    Returns '#888888' if no match found.
    """
    team_lower = str(team).lower()
    for key, color in team_colors.items():
        if key.lower() in team_lower:
            return color
    return "#888888"


def build_color_map(df: pd.DataFrame, team_colors: dict) -> dict:
    """
    Build a {team_name: color} dict for every team present in df.
    Useful for passing directly to Plotly's color_discrete_map.
    """
    teams = df["TEAM"].dropna().unique()
    return {team: get_team_color(team, team_colors) for team in teams}


# ---------------------------------------------------------------------------
# Lap range formatting
# ---------------------------------------------------------------------------

def laps_to_ranges(laps: list[int]) -> str:
    """Convert a list of lap numbers to a compact range string, e.g. '1–5, 8, 10–12'."""
    if not laps:
        return ""
    laps = sorted(laps)
    ranges = []
    start = prev = laps[0]
    for lap in laps[1:]:
        if lap == prev + 1:
            prev = lap
        else:
            ranges.append(f"{start}" if start == prev else f"{start}–{prev}")
            start = prev = lap
    ranges.append(f"{start}" if start == prev else f"{start}–{prev}")
    return ", ".join(ranges)


# ---------------------------------------------------------------------------
# Top-N% lap filtering
# ---------------------------------------------------------------------------

def filter_top_percent(df: pd.DataFrame, percent: int, group_col: str = "NUMBER") -> pd.DataFrame:
    """
    For each group (default: car number), keep only the fastest `percent`% of laps
    by LAP_TIME_SECONDS.  Returns a concatenated DataFrame.
    """
    if percent >= 100:
        return df

    parts = []
    for _, group in df.groupby(group_col):
        n_keep = max(1, int(len(group) * percent / 100))
        parts.append(group.nsmallest(n_keep, "LAP_TIME_SECONDS"))
    return pd.concat(parts, ignore_index=True) if parts else df.iloc[0:0]


# ---------------------------------------------------------------------------
# Plotly dark layout defaults
# ---------------------------------------------------------------------------

DARK_LAYOUT = dict(
    plot_bgcolor="#2b2b2b",
    paper_bgcolor="#2b2b2b",
    font=dict(color="white", size=14),
    xaxis=dict(color="white", gridcolor="#444"),
    yaxis=dict(color="white", gridcolor="#444"),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)


def apply_dark_layout(fig, **overrides):
    """Apply standard dark theme to a Plotly figure, with optional overrides."""
    layout = {**DARK_LAYOUT, **overrides}
    fig.update_layout(**layout)
    return fig
