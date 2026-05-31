#!/usr/bin/env python3
"""
cleanup_data.py — review and remove unwanted CSV files from the data/ directory.

Identifies and optionally deletes:

  1. Intermediate race hour files — e.g. race_hour1.csv, race_hour2.csv when a
     higher hour (race_hour6.csv, race_hour24.csv) exists in the same folder.
     Only the final (highest-numbered) hour is needed; earlier ones are snapshots.

  2. 'other/' session folders — warm_up.csv, superpole.csv, historic_cars_run.csv
     etc. These are not race/practice/qualifying sessions and the app doesn't use them.

  3. Tiny race files — any CSV in a race/ folder under a configurable size threshold
     (default 50 KB). Small race files are almost certainly support race classifications
     that slipped through the championship filter, not full lap-by-lap analysis CSVs.
     NOTE: the threshold only applies to race/ folders — qualifying and practice
     sessions legitimately produce small files and are never flagged on size alone.

  4. Duplicate race.csv alongside race_hourN.csv — some events have both a flat
     race.csv (small, often a classification) and a race_hourN.csv (the full analysis).
     When both exist, the flat race.csv is redundant.

Usage:
    python3 cleanup_data.py                  # dry run — lists everything that would go
    python3 cleanup_data.py --apply          # delete the files
    python3 cleanup_data.py --apply --quiet  # delete without listing each file
    python3 cleanup_data.py --min-kb 100     # change size threshold (default 50)
    python3 cleanup_data.py --no-tiny        # disable tiny file check entirely
    python3 cleanup_data.py --no-other       # skip removing 'other/' folders
    python3 cleanup_data.py --series WEC     # one series only
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# Intermediate hour pattern — matches race_hour1.csv through race_hour23.csv etc.
HOUR_RE = re.compile(r"^race_hour(\d+)(?:_\d{8})?\.csv$", re.IGNORECASE)
# Flat race file — race.csv or race_20260509.csv
FLAT_RACE_RE = re.compile(r"^race(?:_\d{8})?\.csv$", re.IGNORECASE)


def find_intermediate_hours(race_dir: Path) -> list[Path]:
    """
    In a race/ folder, find all but the highest-numbered race_hourN file.
    Also find any flat race.csv that coexists with race_hourN files.
    """
    to_delete: list[Path] = []
    hour_files: dict[int, Path] = {}
    flat_files: list[Path] = []

    for f in race_dir.iterdir():
        if not f.suffix.lower() == ".csv":
            continue
        m = HOUR_RE.match(f.name)
        if m:
            hour_files[int(m.group(1))] = f
        elif FLAT_RACE_RE.match(f.name):
            flat_files.append(f)

    if hour_files:
        max_hour = max(hour_files.keys())
        for hour, path in hour_files.items():
            if hour < max_hour:
                to_delete.append(path)
        # Flat race.csv alongside hourly files is a classification, not lap data
        to_delete.extend(flat_files)

    return to_delete


def find_tiny_race_files(race_dir: Path, min_bytes: int) -> list[Path]:
    """
    Find CSV files in a race/ folder below the size threshold.
    Only applied to race/ folders — practice and qualifying are never flagged on size.
    """
    tiny = []
    for f in race_dir.iterdir():
        if f.suffix.lower() == ".csv" and f.stat().st_size < min_bytes:
            tiny.append(f)
    return tiny


def collect_deletions(
    data_dir: Path,
    series_filter: str | None,
    min_kb: int,
    check_tiny: bool,
    remove_other: bool,
) -> list[tuple[Path, str]]:
    """
    Walk data_dir and return a list of (path, reason) tuples for files to delete.
    """
    min_bytes = min_kb * 1024
    deletions: list[tuple[Path, str]] = []

    for series_dir in sorted(data_dir.iterdir()):
        if not series_dir.is_dir() or series_dir.name.startswith("."):
            continue
        if series_filter and series_dir.name != series_filter:
            continue

        for year_dir in sorted(series_dir.iterdir()):
            if not year_dir.is_dir():
                continue

            for race_dir in sorted(year_dir.iterdir()):
                if not race_dir.is_dir():
                    continue

                for session_dir in sorted(race_dir.iterdir()):
                    if not session_dir.is_dir():
                        continue

                    session_type = session_dir.name

                    # Remove entire 'other/' folder contents
                    if session_type == "other" and remove_other:
                        for f in session_dir.iterdir():
                            if f.suffix.lower() == ".csv":
                                deletions.append((f, "other/ session (warm_up etc.)"))
                        continue

                    if session_type == "race":
                        # Intermediate hours + redundant flat race.csv
                        for f in find_intermediate_hours(session_dir):
                            m = HOUR_RE.match(f.name)
                            if m:
                                deletions.append((f, "intermediate race hour (not the final hour)"))
                            else:
                                deletions.append((f, "flat race.csv alongside race_hourN files"))

                        # Tiny files — race/ only
                        if check_tiny:
                            for f in find_tiny_race_files(session_dir, min_bytes):
                                if not any(f == d[0] for d in deletions):
                                    size_kb = f.stat().st_size // 1024
                                    deletions.append((
                                        f,
                                        f"tiny race file ({size_kb} KB < {min_kb} KB — likely support race or classification)"
                                    ))

    return deletions


def main():
    parser = argparse.ArgumentParser(
        description="Clean up unwanted CSV files from the data/ directory."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete files (default is dry run)")
    parser.add_argument("--quiet", action="store_true",
                        help="Don't list every file, just show summary")
    parser.add_argument("--min-kb", type=int, default=50,
                        help="Size threshold in KB for race files (default: 50). Only race/ folders are checked.")
    parser.add_argument("--no-tiny", action="store_true",
                        help="Disable the tiny file size check entirely")
    parser.add_argument("--no-other", action="store_true",
                        help="Don't remove 'other/' session folders")
    parser.add_argument("--series", choices=["WEC", "ELMS", "IMSA"],
                        help="Only process one series")
    args = parser.parse_args()

    if not DATA_DIR.is_dir():
        print(f"data/ directory not found at {DATA_DIR}")
        return

    if not args.apply:
        print("DRY RUN — nothing will be deleted. Use --apply to delete.\n")

    if args.no_tiny:
        print("Tiny file check disabled.\n")

    deletions = collect_deletions(
        data_dir=DATA_DIR,
        series_filter=args.series,
        min_kb=args.min_kb,
        check_tiny=not args.no_tiny,
        remove_other=not args.no_other,
    )

    if not deletions:
        print("Nothing to clean up.")
        return

    # Group by reason for display
    by_reason: dict[str, list[Path]] = {}
    for path, reason in deletions:
        by_reason.setdefault(reason, []).append(path)

    total_bytes = 0
    for reason, paths in sorted(by_reason.items()):
        print(f"\n── {reason} ({len(paths)} file{'s' if len(paths) != 1 else ''}) ──")
        for path in sorted(paths):
            size_kb = path.stat().st_size // 1024
            rel = path.relative_to(DATA_DIR)
            if not args.quiet:
                action = "DELETE" if args.apply else "would delete"
                print(f"  {action}: {rel}  ({size_kb} KB)")
            total_bytes += path.stat().st_size
            if args.apply:
                path.unlink()

    total_kb = total_bytes // 1024
    total_mb = total_kb / 1024
    print(f"\n{'='*50}")
    print(f"  Files: {len(deletions)}")
    print(f"  Space: {total_kb:,} KB ({total_mb:.1f} MB)")

    if args.apply:
        print("  Deleted.")
        # Remove empty 'other/' directories left behind
        if not args.no_other:
            for series_dir in DATA_DIR.iterdir():
                if not series_dir.is_dir():
                    continue
                for year_dir in series_dir.iterdir():
                    if not year_dir.is_dir():
                        continue
                    for race_dir in year_dir.iterdir():
                        other_dir = race_dir / "other"
                        if other_dir.is_dir() and not any(other_dir.iterdir()):
                            other_dir.rmdir()
    else:
        print("  Run with --apply to delete.")


if __name__ == "__main__":
    main()
