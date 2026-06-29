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

import hashlib
import colorsys
import re
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Car number sorting
# ---------------------------------------------------------------------------

def sort_cars(car_numbers) -> list:
    """
    Sort car number strings numerically (by integer value) while preserving
    leading zeros in the display strings.

    e.g. ["007", "7", "51", "023", "2", "10"] → ["2", "007", "7", "10", "023", "23", "51"]
    i.e. sorted by int value, with "007" and "7" adjacent (both = 7).

    Falls back to lexicographic sort for non-numeric entries (e.g. "LMP2").
    """
    def _key(s: str):
        try:
            return (0, int(s), s)   # numeric: sort by value, then by string for tie-break
        except (ValueError, TypeError):
            return (1, 0, str(s))   # non-numeric: after all numeric entries

    return sorted(car_numbers, key=_key)


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
    _hour_re = re.compile(r"^(\d+):(\d{2}):(\d{2}(?:\.\d+)?)$")

    def _parse_seconds(val):
        """Return total seconds since midnight, supporting H >= 24 (Al-Kamel extended format)."""
        m = _hour_re.match(str(val).strip())
        if not m:
            return None
        h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h * 3600 + mn * 60 + s

    _epoch = datetime.combine(race_start_date, datetime.min.time())
    result = pd.Series(index=df.index, dtype="datetime64[ns]")

    for car_id, car_df in df.sort_values("LAP_NUMBER").groupby(group_col):
        day_offset = 0.0  # seconds to add for midnight rollover (0-23h format only)
        last_secs = None
        for idx, row in car_df.iterrows():
            secs = _parse_seconds(row["HOUR"])
            if secs is None:
                result.loc[idx] = pd.NaT
                continue
            # Only apply rollover for 0-23h format (secs < 24*3600).
            # Extended-hour format (secs >= 24*3600) is already monotonic.
            if secs < 86400 and last_secs is not None and secs < last_secs:
                day_offset += 86400
            last_secs = secs
            result.loc[idx] = _epoch + timedelta(seconds=secs + day_offset)

    return result


# ---------------------------------------------------------------------------
# Team colour lookup
# ---------------------------------------------------------------------------

def _team_fallback_color(team: str) -> str:
    """
    Derive a deterministic, visually distinct colour from the team name.
    Uses SHA-256 to map the name to a hue, then fixes saturation and
    lightness so the colour is vivid enough to read on a dark background.
    """
    digest = hashlib.sha256(team.encode()).digest()
    hue = int.from_bytes(digest[:2], "big") / 65536          # 0.0–1.0
    sat = 0.65 + (digest[2] / 255) * 0.20                    # 0.65–0.85
    light = 0.50 + (digest[3] / 255) * 0.15                  # 0.50–0.65
    r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def _ensure_readable(hex_color: str, min_luminance: float = 0.06) -> str:
    """Lighten any hex colour that is too dark to read on a dark background.

    Preserves hue and saturation; only raises lightness enough to meet the
    minimum relative luminance threshold (~mid-dark grey equivalent).
    Toyota's #100100 has luminance ~0.0003 and gets lifted to a dark red.
    """
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if luminance >= min_luminance:
        return hex_color
    hue, _, sat = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb(hue, 0.35, max(sat, 0.6))
    return f"#{int(r2*255):02x}{int(g2*255):02x}{int(b2*255):02x}"


def get_team_color(team: str, team_colors: dict) -> str:
    """
    Fuzzy-match a team name against the team_colors dict.
    Falls back to a deterministic colour derived from the team name so
    every team gets a unique, consistent colour across all charts.
    Always returns a colour readable on a dark background.
    """
    team_lower = str(team).lower()
    for key, color in team_colors.items():
        if key.lower() in team_lower:
            return _ensure_readable(color)
    return _team_fallback_color(str(team))


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
# DataFrame validation
# ---------------------------------------------------------------------------

def validate_dataframe(df: pd.DataFrame, required_cols: list[str], context: str = "") -> None:
    """
    Raise a clear ValueError if any required columns are missing from df.
    Pass context (e.g. 'load_race') to make the error message actionable.
    """
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        prefix = f"[{context}] " if context else ""
        raise ValueError(f"{prefix}Missing required columns: {missing}. Present: {list(df.columns)}")


# ---------------------------------------------------------------------------
# Plotly dark layout defaults
# ---------------------------------------------------------------------------

def apply_dark_layout(fig, **overrides):
    """Apply the On The Apex Plotly theme to a figure. Delegates to theme.apply_ota_layout."""
    from theme import apply_ota_layout
    return apply_ota_layout(fig, **overrides)


# ---------------------------------------------------------------------------
# Export helper — SVG and high-res PNG for Plotly figures and DataFrames
# ---------------------------------------------------------------------------

def chart_export_buttons(
    fig=None,
    df=None,
    filename: str = "chart",
    width: int = 1800,
    height: int = 600,
) -> None:
    """
    Render SVG and high-res PNG export buttons beneath a Plotly figure.
    Pass `fig` for Plotly figures, `df` for DataFrames.

    Uses st.iframe (replaces deprecated st.components.v1.html) to render the
    figure and trigger Plotly.downloadImage — no kaleido required.

    For DataFrames: exports as CSV.
    If both fig and df are provided, Plotly export is used.
    """
    import hashlib

    safe_name = filename.replace(" ", "_").replace("/", "-")

    if fig is not None:
        fig_json = fig.to_json()
        iframe_html = f"""<!DOCTYPE html>
<html>
<head>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body {{ margin:0; background:transparent; font-family:sans-serif; }}
  .btn {{
    background:#1f1f2e; color:#fff; border:1px solid #555;
    padding:5px 12px; border-radius:4px; cursor:pointer;
    font-size:12px; margin-right:6px;
  }}
  .btn:hover {{ background:#2d2d45; }}
</style>
</head>
<body>
<div id="chart" style="display:none;"></div>
<div style="padding:3px 0;">
  <button class="btn" onclick="doExport('svg')">⬇ SVG</button>
  <button class="btn" onclick="doExport('png')">⬇ PNG (3×)</button>
</div>
<script>
  var figData = {fig_json};
  Plotly.newPlot('chart', figData.data, figData.layout, {{staticPlot: true}});
  function doExport(fmt) {{
    Plotly.downloadImage('chart', {{
      format:   fmt,
      width:    {width},
      height:   {height},
      scale:    fmt === 'png' ? 3 : 1,
      filename: '{safe_name}',
    }});
  }}
</script>
</body>
</html>"""
        st.iframe(iframe_html, height=38)

    elif df is not None:
        # DataFrame export as CSV.
        # Key must be unique across all calls on the page, including when the
        # same filename is used multiple times in a loop (e.g. per-class dfs).
        # Use a hash of the CSV content so identical calls stay stable across
        # reruns but differ when content differs.
        csv = df.to_csv(index=False)
        content_hash = hashlib.md5(csv.encode()).hexdigest()[:8]
        st.download_button(
            label="⬇ Download CSV",
            data=csv,
            file_name=f"{safe_name}.csv",
            mime="text/csv",
            key=f"_csv_{safe_name}_{content_hash}",
        )
