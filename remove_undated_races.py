#!/usr/bin/env python3
"""
remove_undated_races.py — one-time cleanup for duplicate race files.

When the downloader added date suffixes to race filenames, running it with
--skip-existing didn't recognise old undated files as already downloaded,
so both versions now exist:
    race_hour6.csv              ← old, no date
    race_hour6_20260509.csv     ← new, with date (correct)

This script deletes the undated version wherever a dated equivalent exists.

Usage:
    python3 remove_undated_races.py             # dry run
    python3 remove_undated_races.py --apply     # delete
    python3 remove_undated_races.py --series WEC
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# Undated race file: race.csv or race_hour6.csv (no 8-digit date)
UNDATED_RE = re.compile(r"^(race(?:_hour\d+)?)\.csv$", re.IGNORECASE)
# Dated race file: race_20260509.csv or race_hour6_20260509.csv
DATED_RE   = re.compile(r"^(race(?:_hour\d+)?)_\d{8}\.csv$", re.IGNORECASE)


def find_duplicates(data_dir: Path, series_filter: str | None) -> list[Path]:
    """Return list of undated race files that have a dated counterpart."""
    to_delete = []

    for series_dir in sorted(data_dir.iterdir()):
        if not series_dir.is_dir() or series_dir.name.startswith("."):
            continue
        if series_filter and series_dir.name != series_filter:
            continue

        for year_dir in sorted(series_dir.iterdir()):
            if not year_dir.is_dir():
                continue
            for event_dir in sorted(year_dir.iterdir()):
                if not event_dir.is_dir():
                    continue
                race_dir = event_dir / "race"
                if not race_dir.is_dir():
                    continue

                # Build index of base names that have dated versions
                dated_bases: set[str] = set()
                for f in race_dir.iterdir():
                    m = DATED_RE.match(f.name)
                    if m:
                        dated_bases.add(m.group(1).lower())

                # Find undated files whose base has a dated counterpart
                for f in race_dir.iterdir():
                    m = UNDATED_RE.match(f.name)
                    if m and m.group(1).lower() in dated_bases:
                        to_delete.append(f)

    return sorted(to_delete)


def main():
    parser = argparse.ArgumentParser(
        description="Remove undated race files where a dated version exists."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete files (default: dry run)")
    parser.add_argument("--series", choices=["WEC", "ELMS", "IMSA"],
                        help="Only process one series")
    args = parser.parse_args()

    if not DATA_DIR.is_dir():
        print(f"data/ not found at {DATA_DIR}")
        return

    if not args.apply:
        print("DRY RUN — nothing will be deleted. Use --apply to delete.\n")

    duplicates = find_duplicates(DATA_DIR, args.series)

    if not duplicates:
        print("No duplicates found — nothing to do.")
        return

    total_bytes = 0
    for f in duplicates:
        rel = f.relative_to(DATA_DIR)
        size_kb = f.stat().st_size // 1024
        action = "delete" if args.apply else "would delete"
        print(f"  {action}: {rel}  ({size_kb} KB)")
        total_bytes += f.stat().st_size
        if args.apply:
            f.unlink()

    print(f"\n{'='*50}")
    print(f"  Files:  {len(duplicates)}")
    print(f"  Space:  {total_bytes // 1024:,} KB ({total_bytes / 1024 / 1024:.1f} MB)")
    if args.apply:
        print("  Done. Commit the data/ changes to GitHub.")
    else:
        print("  Run with --apply to delete.")


if __name__ == "__main__":
    main()
