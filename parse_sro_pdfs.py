#!/usr/bin/env python3
"""
parse_sro_pdfs.py — Convert SRO post-race PDFs to Al-Kamel-compatible CSV.

Usage:
    python parse_sro_pdfs.py <pdf_dir> <output_csv> [--date YYYYMMDD] [--track-length M]

Reads from pdf_dir (auto-detected by filename pattern):
    *Sector_List*      → core lap/sector data (required)
    *Message_List*     → SC/FCY periods for FLAG_AT_FL
    *Pit_Stop_List*    → CROSSING_FINISH_LINE_IN_PIT
    *Top_Speed_List*   → TEAM, MANUFACTURER per car
    *Lap_Chart*        → (not yet used — ELAPSED gives position)

Output CSV is semicolon-delimited, Al-Kamel column format, BOM-prefixed.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF required: pip install pymupdf")


# ─── constants ────────────────────────────────────────────────────────────────

ALKAMEL_COLUMNS = [
    "NUMBER", "DRIVER_NUMBER", "LAP_NUMBER", "LAP_TIME", "LAP_IMPROVEMENT",
    "CROSSING_FINISH_LINE_IN_PIT", "S1", "S1_IMPROVEMENT", "S2", "S2_IMPROVEMENT",
    "S3", "S3_IMPROVEMENT", "KPH", "ELAPSED", "HOUR", "S1_LARGE", "S2_LARGE",
    "S3_LARGE", "TOP_SPEED", "DRIVER_NAME", "PIT_TIME", "CLASS", "GROUP",
    "TEAM", "MANUFACTURER", "FLAG_AT_FL", "S1_SECONDS", "S2_SECONDS", "S3_SECONDS",
]

DEFAULT_CLASS = "GT3"
DEFAULT_GROUP = ""

# Known GT3 manufacturer brands for name extraction from car model strings
BRANDS = [
    "Ferrari", "BMW", "Porsche", "Mercedes-AMG", "Audi", "McLaren",
    "Aston Martin", "Lamborghini", "Chevrolet", "Ford", "Honda", "Acura",
    "Bentley", "Nissan", "Lexus",
]


# ─── time helpers ─────────────────────────────────────────────────────────────

def parse_secs(s: str) -> float | None:
    """Parse M:SS.sss, H:MM:SS.sss, or SS.sss → float seconds. None on failure."""
    s = str(s).strip()
    if not s:
        return None
    try:
        parts = s.split(":")
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except Exception:
        pass
    return None


def fmt_laptime(secs: float | None) -> str:
    """Seconds → M:SS.sss (Al-Kamel lap time format)."""
    if secs is None or math.isnan(secs):
        return ""
    m = int(secs // 60)
    s = secs % 60
    return f"{m}:{s:06.3f}"


def fmt_sector(secs: float | None) -> str:
    """Seconds → SS.sss or M:SS.sss if >= 60 s (Al-Kamel S1/S2/S3 format)."""
    if secs is None:
        return ""
    if secs < 60:
        return f"{secs:.3f}"
    m = int(secs // 60)
    s = secs % 60
    return f"{m}:{s:06.3f}"


def fmt_sector_large(secs: float | None) -> str:
    """Seconds → 0:SS.sss (Al-Kamel S1_LARGE format)."""
    if secs is None:
        return ""
    m = int(secs // 60)
    s = secs % 60
    return f"{m}:{s:06.3f}"


def fmt_elapsed(secs: float | None) -> str:
    """Elapsed seconds → H:MM:SS.sss (Al-Kamel ELAPSED format)."""
    if secs is None:
        return ""
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:06.3f}"
    return f"{m}:{s:06.3f}"


def fmt_hour(elapsed_secs: float | None, race_start_secs: float) -> str:
    """Race elapsed seconds → absolute HH:MM:SS.sss wall-clock time."""
    if elapsed_secs is None:
        return ""
    total = race_start_secs + elapsed_secs
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def compute_kph(lap_secs: float | None, track_m: float) -> str:
    if not lap_secs or lap_secs <= 0:
        return ""
    return str(round(track_m / 1000 / (lap_secs / 3600), 1))


# ─── PDF word helpers ──────────────────────────────────────────────────────────

def page_words_by_column(page, mid_x: float | None = None):
    """
    Return (left_words, right_words) where each is a list of (y, x, text)
    sorted by (y, x).  mid_x defaults to half the page width.
    """
    if mid_x is None:
        mid_x = page.rect.width / 2
    left, right = [], []
    for x0, y0, x1, y1, text, *_ in page.get_text("words"):
        entry = (round(y0, 1), x0, text)
        if x0 < mid_x:
            left.append(entry)
        else:
            right.append(entry)
    left.sort()
    right.sort()
    return left, right


def _is_page_header(text: str) -> bool:
    """Return True for tokens that only ever appear in page headers, never in data."""
    return False  # We filter headers by y-position (< DATA_Y_MIN) instead.


def _is_time(text: str) -> bool:
    """True if text looks like a time value (SS.sss, M:SS.sss, H:MM:SS.sss)."""
    return bool(re.match(r'^\d+\.\d{3}$', text) or
                re.match(r'^\d+:\d{2}\.\d+$', text) or
                re.match(r'^\d+:\d{2}:\d{2}\.\d+$', text))


def _is_lap_row(tokens: list[str]) -> bool:
    """Check if a list of tokens looks like the start of a lap record."""
    if len(tokens) < 3:
        return False
    return (tokens[0].isdigit() and
            tokens[1] in ("1", "2", "3") and
            _is_time(tokens[2]))


# ─── Sector List parser ────────────────────────────────────────────────────────

def _parse_driver_line(tokens: list[str]) -> dict[int, str]:
    """
    Parse tokens like ["Schuring,", "NED(#1)", "/", "Boccolacci,", "FRA(#2)", ...]
    Returns {1: "Schuring", 2: "Boccolacci", ...}
    """
    drivers: dict[int, str] = {}
    last_name = ""
    for tok in tokens:
        m = re.match(r'([A-Z]{2,4})\(#(\d)\)', tok)
        if m:
            driver_id = int(m.group(2))
            drivers[driver_id] = last_name.rstrip(",")
        elif tok != "/" and not _is_page_header(tok):
            last_name = tok
    return drivers


def _parse_lap_record(tokens: list[str]) -> dict | None:
    """
    Parse 10 tokens: Lap Id Time SE1 SP1 SE2 SP2 SE3 SP3 TSP.
    Returns dict or None if tokens don't look like a valid lap row.
    """
    if len(tokens) < 3:
        return None
    lap_num_str, driver_id_str, lap_time_str = tokens[0], tokens[1], tokens[2]
    if not lap_num_str.isdigit():
        return None
    if not driver_id_str.isdigit():
        return None
    if not _is_time(lap_time_str):
        return None

    se1 = tokens[3] if len(tokens) > 3 else ""
    sp1 = tokens[4] if len(tokens) > 4 else ""
    se2 = tokens[5] if len(tokens) > 5 else ""
    sp2 = tokens[6] if len(tokens) > 6 else ""
    se3 = tokens[7] if len(tokens) > 7 else ""
    sp3 = tokens[8] if len(tokens) > 8 else ""
    tsp = tokens[9] if len(tokens) > 9 else ""

    return {
        "lap": int(lap_num_str),
        "driver_id": int(driver_id_str),
        "lap_time": lap_time_str,
        "se1": se1, "sp1": sp1,
        "se2": se2, "sp2": sp2,
        "se3": se3, "sp3": sp3,
        "tsp": tsp,
    }


def _parse_column_stream(
    col_words: list[tuple],
    initial_car: str | None = None,
    initial_sections: dict | None = None,
) -> tuple[dict[str, dict], str | None]:
    """
    Parse a single column's word stream (list of (y, x, text)).
    Groups words by y-row, then parses car sections and lap records.

    The SRO sector list has two car-header formats per page:
      Format A — driver names and car number on the SAME row:
          "5 Rappange, NED(#1) / Oliveira, POR(#2) ..."
      Format B — driver names one row, car number the next (0-1 px apart):
          y=161: "Schuring, NED(#1) / ..."
          y=162: "2"

    When a car's section spans multiple pages, the continuation page has no
    header.  Pass `initial_car` (the car active at the end of the previous
    page) so orphaned laps are attributed correctly.

    Returns (car_sections_dict, last_active_car).
    car_sections: {car_num: {"drivers": {id: name}, "rows": [(y, lap_record)]}}
    """
    DATA_Y_MIN = 148
    rows: dict[int, list] = defaultdict(list)
    for y, x, text in col_words:
        if y < DATA_Y_MIN:
            continue
        rows[round(y)].append((x, text))

    car_sections: dict[str, dict] = dict(initial_sections) if initial_sections else {}
    current_car: str | None = initial_car
    pending_drivers: dict[int, str] = {}

    for y_key in sorted(rows.keys()):
        row = sorted(rows[y_key])
        texts = [t for _, t in row]

        if "besttime:" in texts or "besttime" in texts:
            continue

        has_nat = any(re.search(r'\([#\d]+\)', t) for t in texts)
        first_is_int = bool(texts) and texts[0].isdigit()

        if has_nat and first_is_int:
            # Format A: "5 Rappange, NED(#1) / ..."  — car num + drivers on same row
            current_car = texts[0]
            drivers = _parse_driver_line(texts[1:])
            if current_car not in car_sections:
                car_sections[current_car] = {"drivers": drivers, "rows": []}
            else:
                car_sections[current_car]["drivers"].update(drivers)
            pending_drivers = {}
            continue

        if has_nat and not first_is_int:
            # Format B driver line — buffer drivers, car number comes next row
            pending_drivers = _parse_driver_line(texts)
            continue

        if not has_nat and first_is_int and len(texts) == 1:
            # Format B car number — use buffered pending_drivers
            current_car = texts[0]
            if current_car not in car_sections:
                car_sections[current_car] = {"drivers": dict(pending_drivers), "rows": []}
            else:
                car_sections[current_car]["drivers"].update(pending_drivers)
            pending_drivers = {}
            continue

        # Not a header row — try to parse as lap record
        pending_drivers = {}
        if current_car and current_car in car_sections:
            rec = _parse_lap_record(texts)
            if rec is not None:
                car_sections[current_car]["rows"].append((y_key, rec))

    return car_sections, current_car


def parse_sector_list(pdf_path: str) -> dict[str, dict]:
    """
    Parse the SRO Sector List PDF.

    Layout: the left column contains car headers and each car's first N laps;
    the right column contains the continuation laps (no headers) at the SAME
    y-range as the left-column section for each car.  We parse the left column
    to identify car sections (and their y extents), then collect right-column
    laps that fall within each section's y-range on the same page.

    Returns {car_num: {"drivers": {id: name}, "laps": [lap_record, ...]}}
    """
    doc = fitz.open(pdf_path)
    result: dict[str, dict] = {}

    # left_carry: the car number active at the end of the previous page's left
    # column; used to attribute continuation laps that have no header on the
    # next page.
    left_carry: str | None = None

    for page_idx, page in enumerate(doc):
        mid_x = page.rect.width / 2
        left_words, right_words = page_words_by_column(page, mid_x)

        # Build right-column lookup: y-row → list of (x, text)
        right_by_y: dict[int, list] = defaultdict(list)
        for y, x, text in right_words:
            if y >= 148:
                right_by_y[round(y)].append((x, text))

        # Parse left column.  If a car's section continued from the previous
        # page, seed with a stub entry so orphaned laps are attributed.
        seed: dict = {}
        if left_carry and left_carry not in seed:
            seed[left_carry] = {"drivers": {}, "rows": []}
        left_sections, left_carry = _parse_column_stream(
            left_words,
            initial_car=left_carry,
            initial_sections=seed,
        )

        for car_num, section in left_sections.items():
            if car_num not in result:
                result[car_num] = {"drivers": section["drivers"], "laps": []}
            else:
                result[car_num]["drivers"].update(section["drivers"])

            left_laps = [rec for _, rec in section["rows"]]
            left_y_set = {y for y, _ in section["rows"]}

            # The right-column continuation occupies the same y-range as the
            # left-column section on this page.
            right_laps = []
            if left_y_set:
                min_y = min(left_y_set)
                max_y = max(left_y_set)
                for y_key in sorted(right_by_y.keys()):
                    if y_key < min_y or y_key > max_y:
                        continue
                    r_row = sorted(right_by_y[y_key])
                    r_texts = [t for _, t in r_row]
                    if "besttime:" in r_texts or "besttime" in r_texts:
                        continue
                    rec = _parse_lap_record(r_texts)
                    if rec is not None:
                        right_laps.append(rec)

            all_laps = left_laps + right_laps
            result[car_num]["laps"].extend(all_laps)

    # Deduplicate and sort laps per car
    for car_num in result:
        seen: set[int] = set()
        deduped = []
        for lap in result[car_num]["laps"]:
            if lap["lap"] not in seen:
                seen.add(lap["lap"])
                deduped.append(lap)
        result[car_num]["laps"] = sorted(deduped, key=lambda r: r["lap"])

    return result


# ─── Top Speed List parser ─────────────────────────────────────────────────────

_TSL_SKIP = {
    "Top speed list", "Provisional", "Race", "# Name (NAT)",
    "Team", "Car name", "Speed", "Lap", "Race time",
    "TIME", "RACE TIME", "MESSAGE",
}
_TSL_HEADER_RE = re.compile(
    r'^(Autodromo|GTWorldChEU|Page \d|GT WorldChEU|ver:|Sunday,|printed:|\d{2}\.\d{1,2}\.\d{4})',
    re.I,
)


def parse_top_speed_list(pdf_path: str) -> dict[str, dict]:
    """
    Returns {car_num: {"team": str, "manufacturer": str, "car_name": str}}.

    Each entry in the PDF is 6 lines:
        {car_num} {driver} ({NAT})
        {team} ({country})
        {car_model}
        {speed}
        {lap}
        {race_time}
    """
    doc = fitz.open(pdf_path)
    all_lines: list[str] = []
    for page in doc:
        for line in page.get_text().splitlines():
            line = line.strip()
            if not line or line in _TSL_SKIP or _TSL_HEADER_RE.match(line):
                continue
            all_lines.append(line)

    car_info: dict[str, dict] = {}
    CAR_RE = re.compile(r'^(\d+)\s+.+\([A-Z]{2,4}\)$')
    BRANDS_SORTED = sorted(BRANDS, key=len, reverse=True)

    i = 0
    while i < len(all_lines):
        m = CAR_RE.match(all_lines[i])
        if m and i + 2 < len(all_lines):
            car_num = m.group(1)
            team_line = all_lines[i + 1]
            car_model = all_lines[i + 2]
            # Validate: car_model must start with a known brand; otherwise this
            # line is a team name that happens to start with a digit (e.g. "2 Seas").
            manufacturer = ""
            for brand in BRANDS_SORTED:
                if car_model.startswith(brand):
                    manufacturer = brand
                    break
            if manufacturer and car_num not in car_info:
                team = re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', team_line).strip()
                car_info[car_num] = {
                    "team": team,
                    "manufacturer": manufacturer,
                    "car_name": car_model,
                }
        i += 1

    return car_info


# ─── Message List parser ───────────────────────────────────────────────────────

_WALL_RE = re.compile(r'^\d{2}:\d{2}:\d{2}(?:\.\d+)?$')
_ELAPSED_RE = re.compile(r'^\d+:\d{2}(?::\d{2})?\.\d+$')


def parse_message_list(pdf_path: str) -> tuple[str, list]:
    """
    Parse SRO Message List PDF (multi-line record format):
        {wall_time}
        [{race_elapsed}]   ← only present once race clock is running
        {message text}

    Returns (race_start_wall_str, [(start_s, end_s, flag_type), ...]).
    flag_type is "SC" or "FCY".
    """
    doc = fitz.open(pdf_path)
    skip = {"Message List", "TIME", "RACE TIME", "MESSAGE"}
    header_re = re.compile(
        r'^(Autodromo|GTWorldChEU|Page \d|GT WorldChEU|ver:|Sunday,|printed:|'
        r'\d{2}\.\d{1,2}\.\d{4})',
        re.I,
    )

    all_lines: list[str] = []
    for page in doc:
        for line in page.get_text().splitlines():
            line = line.strip()
            if not line or line in skip or header_re.match(line):
                continue
            all_lines.append(line)

    events: list[tuple[float, str]] = []
    race_start_wall = "16:00:00.000"

    i = 0
    while i < len(all_lines):
        line = all_lines[i]
        if not _WALL_RE.match(line):
            i += 1
            continue
        wall_time = line
        i += 1
        elapsed_str = None
        if i < len(all_lines) and _ELAPSED_RE.match(all_lines[i]):
            elapsed_str = all_lines[i]
            i += 1
        # Collect message lines until next wall time
        msg_parts: list[str] = []
        while i < len(all_lines) and not _WALL_RE.match(all_lines[i]):
            msg_parts.append(all_lines[i])
            i += 1
        msg = " ".join(msg_parts).upper()
        elapsed = parse_secs(elapsed_str) if elapsed_str else None

        # Race start: "Green flag" with no elapsed time = clock starts here
        if "GREEN FLAG" == msg and elapsed is None:
            race_start_wall = wall_time if "." in wall_time else wall_time + ".000"

        if elapsed is None:
            continue

        if "SAFETY CAR DEPLOYED" in msg:
            events.append((elapsed, "SC_START"))
        elif re.search(r'FULL COURSE YELLOW DEPLOYED|FCY DEPLOYED', msg):
            events.append((elapsed, "FCY_START"))
        elif msg == "GREEN FLAG" or (msg.startswith("GREEN FLAG") and "AT M" not in msg):
            events.append((elapsed, "GREEN"))
        elif "END OF MINIMUM FCY DURATION" in msg:
            events.append((elapsed, "FCY_END_POSSIBLE"))

    windows: list[tuple[float, float, str]] = []
    active_flag: str | None = None
    active_start: float = 0.0

    for elapsed, event in sorted(events):
        if event in ("SC_START", "FCY_START"):
            if active_flag is None:
                active_flag = "SC" if event == "SC_START" else "FCY"
                active_start = elapsed
            elif event == "SC_START" and active_flag == "FCY":
                windows.append((active_start, elapsed, "FCY"))
                active_flag = "SC"
                active_start = elapsed
        elif event == "GREEN" and active_flag is not None:
            windows.append((active_start, elapsed, active_flag))
            active_flag = None
        elif event == "FCY_END_POSSIBLE" and active_flag == "FCY":
            windows.append((active_start, elapsed, "FCY"))
            active_flag = None

    return race_start_wall, windows


def flag_for_elapsed(elapsed_secs: float, windows: list) -> str:
    """Return FLAG_AT_FL value for a given race elapsed time."""
    for start, end, flag_type in windows:
        if start <= elapsed_secs <= end:
            return flag_type
    return "GF"


# ─── Pit Stop List parser ──────────────────────────────────────────────────────

def parse_pit_stops(pdf_path: str) -> dict[str, list[float]]:
    """
    Returns {car_num: [race_elapsed_time_in_secs, ...]}.

    PDF format (multi-line per stop):
        {car_num} {driver_in_name}
        {wall_time_in}   ← HH:MM:SS.sss
        {elapsed_in}     ← M:SS.sss or H:MM:SS.sss  ← what we capture
        {driver_out} / {wall_time_out} / ...
    """
    doc = fitz.open(pdf_path)
    skip = {"Nr. Driver in", "Day time in", "Time in", "Driver out",
            "Day time out", "Time out Reason", "Net Time",
            "Refueling:", "Start time", "Duration", "Is Violation"}
    header_re = re.compile(
        r'^(Autodromo|GTWorldChEU|Page \d|GT WorldChEU|ver:|Sunday,|printed:|'
        r'\d{2}\.\d{1,2}\.\d{4})',
        re.I,
    )
    CAR_RE = re.compile(r'^(\d+)\s+\w')

    all_lines: list[str] = []
    for page in doc:
        for line in page.get_text().splitlines():
            line = line.strip()
            if not line or line in skip or header_re.match(line):
                continue
            all_lines.append(line)

    pit_entries: dict[str, list[float]] = defaultdict(list)

    for idx, line in enumerate(all_lines):
        m = CAR_RE.match(line)
        if m and idx + 2 < len(all_lines):
            car_num = m.group(1)
            wall_line = all_lines[idx + 1]
            elapsed_line = all_lines[idx + 2]
            if _WALL_RE.match(wall_line) and _ELAPSED_RE.match(elapsed_line):
                secs = parse_secs(elapsed_line)
                if secs is not None:
                    pit_entries[car_num].append(secs)

    return dict(pit_entries)


# ─── Build Al-Kamel CSV ────────────────────────────────────────────────────────

def build_csv(
    sector_data: dict,
    top_speed_data: dict,
    race_start_wall: str,
    flag_windows: list,
    pit_entries: dict,
    output_path: str,
    track_length_m: float = 5793.0,
) -> int:
    """
    Combine all parsed data into an Al-Kamel format CSV.
    Returns number of rows written.
    """
    race_start_secs = parse_secs(race_start_wall) or (16 * 3600)

    rows = []

    for car_num, car_data in sector_data.items():
        drivers = car_data.get("drivers", {})
        laps = car_data.get("laps", [])
        if not laps:
            continue

        car_info = top_speed_data.get(car_num, {})
        team = car_info.get("team", "")
        manufacturer = car_info.get("manufacturer", "")

        # Pit entry times for this car (in race-elapsed seconds)
        car_pit_times = sorted(pit_entries.get(car_num, []))

        # Per-car bests for improvement flags
        best_lap = float("inf")
        best_s1 = float("inf")
        best_s2 = float("inf")
        best_s3 = float("inf")

        elapsed_secs = 0.0  # cumulative

        for lap in laps:
            lap_num = lap["lap"]
            driver_id = lap["driver_id"]
            driver_name = drivers.get(driver_id, f"Driver {driver_id}")

            lap_time_secs = parse_secs(lap["lap_time"])
            if lap_time_secs is None:
                continue

            s1_secs = parse_secs(lap["se1"])
            s2_secs = parse_secs(lap["se2"])
            s3_secs = parse_secs(lap["se3"])

            elapsed_secs += lap_time_secs
            elapsed_str = fmt_elapsed(elapsed_secs)
            hour_str = fmt_hour(elapsed_secs, race_start_secs)

            # Improvement flags
            lap_improvement = 1 if lap_time_secs < best_lap else 0
            s1_improvement = 1 if (s1_secs and s1_secs < best_s1) else 0
            s2_improvement = 1 if (s2_secs and s2_secs < best_s2) else 0
            s3_improvement = 1 if (s3_secs and s3_secs < best_s3) else 0

            if lap_time_secs < best_lap:
                best_lap = lap_time_secs
            if s1_secs and s1_secs < best_s1:
                best_s1 = s1_secs
            if s2_secs and s2_secs < best_s2:
                best_s2 = s2_secs
            if s3_secs and s3_secs < best_s3:
                best_s3 = s3_secs

            # Crossing finish line in pit:
            # A car crosses the line in pit if it entered the pit BEFORE this
            # lap's elapsed time and exits AFTER (i.e. elapsed is still < time_out).
            # Simplification: if any pit entry time falls within [prev_elapsed, elapsed],
            # this lap was a pit lap.
            prev_elapsed = elapsed_secs - lap_time_secs
            in_pit = any(prev_elapsed <= t <= elapsed_secs for t in car_pit_times)
            crossing_in_pit = "B" if in_pit else ""

            # Flag at finish line
            flag = flag_for_elapsed(elapsed_secs, flag_windows)

            rows.append({
                "NUMBER": car_num,
                "DRIVER_NUMBER": str(driver_id),
                "LAP_NUMBER": str(lap_num),
                "LAP_TIME": fmt_laptime(lap_time_secs),
                "LAP_IMPROVEMENT": str(lap_improvement),
                "CROSSING_FINISH_LINE_IN_PIT": crossing_in_pit,
                "S1": fmt_sector(s1_secs),
                "S1_IMPROVEMENT": str(s1_improvement),
                "S2": fmt_sector(s2_secs),
                "S2_IMPROVEMENT": str(s2_improvement),
                "S3": fmt_sector(s3_secs),
                "S3_IMPROVEMENT": str(s3_improvement),
                "KPH": compute_kph(lap_time_secs, track_length_m),
                "ELAPSED": elapsed_str,
                "HOUR": hour_str,
                "S1_LARGE": fmt_sector_large(s1_secs),
                "S2_LARGE": fmt_sector_large(s2_secs),
                "S3_LARGE": fmt_sector_large(s3_secs),
                "TOP_SPEED": lap.get("tsp", ""),
                "DRIVER_NAME": driver_name,
                "PIT_TIME": "",
                "CLASS": DEFAULT_CLASS,
                "GROUP": DEFAULT_GROUP,
                "TEAM": team,
                "MANUFACTURER": manufacturer,
                "FLAG_AT_FL": flag,
                "S1_SECONDS": f"{s1_secs:.3f}" if s1_secs is not None else "",
                "S2_SECONDS": f"{s2_secs:.3f}" if s2_secs is not None else "",
                "S3_SECONDS": f"{s3_secs:.3f}" if s3_secs is not None else "",
            })

    # Sort by car number (numeric), then lap number
    def sort_key(r):
        try:
            return (int(r["NUMBER"]), int(r["LAP_NUMBER"]))
        except ValueError:
            return (0, 0)

    rows.sort(key=sort_key)

    # Write BOM-prefixed semicolon-delimited CSV (Al-Kamel format)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=ALKAMEL_COLUMNS, delimiter=";", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


# ─── PDF auto-detection ────────────────────────────────────────────────────────

PDF_PATTERNS = {
    "sector":   re.compile(r"sector.?list", re.I),
    "messages": re.compile(r"message.?list", re.I),
    "pits":     re.compile(r"pit.?stop.?list", re.I),
    "speeds":   re.compile(r"top.?speed", re.I),
    "lap_chart": re.compile(r"lap.?chart", re.I),
}


def find_pdfs(pdf_dir: str) -> dict[str, str | None]:
    found: dict[str, str | None] = {k: None for k in PDF_PATTERNS}
    for fname in os.listdir(pdf_dir):
        if not fname.lower().endswith(".pdf"):
            continue
        fpath = os.path.join(pdf_dir, fname)
        for key, pat in PDF_PATTERNS.items():
            if pat.search(fname) and found[key] is None:
                found[key] = fpath
    return found


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_dir", help="Directory containing SRO PDFs")
    parser.add_argument("output_csv", help="Output CSV path (e.g. data/GTWC/2026/monza/race/race_20260531.csv)")
    parser.add_argument("--track-length", type=float, default=5793.0,
                        help="Track length in metres (default: 5793 = Monza)")
    args = parser.parse_args()

    pdfs = find_pdfs(args.pdf_dir)

    if not pdfs["sector"]:
        sys.exit(f"ERROR: No Sector List PDF found in {args.pdf_dir}")

    print(f"Parsing Sector List: {pdfs['sector']}")
    sector_data = parse_sector_list(pdfs["sector"])
    print(f"  Found {len(sector_data)} cars, "
          f"{sum(len(v['laps']) for v in sector_data.values())} total lap records")

    top_speed_data: dict = {}
    if pdfs["speeds"]:
        print(f"Parsing Top Speed List: {pdfs['speeds']}")
        top_speed_data = parse_top_speed_list(pdfs["speeds"])
        print(f"  Found {len(top_speed_data)} cars with team/manufacturer info")
    else:
        print("WARNING: No Top Speed List found — TEAM/MANUFACTURER will be empty")

    race_start_wall = "16:00:00.000"
    flag_windows: list = []
    if pdfs["messages"]:
        print(f"Parsing Message List: {pdfs['messages']}")
        race_start_wall, flag_windows = parse_message_list(pdfs["messages"])
        print(f"  Race start: {race_start_wall}, {len(flag_windows)} neutralisation windows")

    pit_entries: dict = {}
    if pdfs["pits"]:
        print(f"Parsing Pit Stop List: {pdfs['pits']}")
        pit_entries = parse_pit_stops(pdfs["pits"])
        print(f"  Found pit data for {len(pit_entries)} cars")

    print(f"Building CSV: {args.output_csv}")
    n = build_csv(
        sector_data=sector_data,
        top_speed_data=top_speed_data,
        race_start_wall=race_start_wall,
        flag_windows=flag_windows,
        pit_entries=pit_entries,
        output_path=args.output_csv,
        track_length_m=args.track_length,
    )
    print(f"Done — {n} rows written to {args.output_csv}")


if __name__ == "__main__":
    main()
