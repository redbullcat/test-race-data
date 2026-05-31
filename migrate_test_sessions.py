#!/usr/bin/env python3
"""
migrate_test_sessions.py — move practice/ folders to test/ for test events.

Test events (Prologue, Roar Before the 24, official test days) had their
sessions downloaded into practice/ folders. This script renames them to test/
so they're correctly classified as standalone test events rather than race
weekend practice sessions.

Detection: an event folder is a test event if its slug contains any of:
  "test", "prologue", "roar", "rookie", "official"

Usage:
    python3 migrate_test_sessions.py             # dry run — shows what would move
    python3 migrate_test_sessions.py --apply     # actually move the files
    python3 migrate_test_sessions.py --series WEC
"""

from __future__ import annotations

import argparse
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# Keywords in the event slug that indicate a test event (not a race weekend)
TEST_KEYWORDS = ("test", "prologue", "roar", "rookie", "official")


def is_test_event(event_slug: str) -> bool:
    return any(kw in event_slug for kw in TEST_KEYWORDS)


def find_migrations(data_dir: Path, series_filter: str | None) -> list[tuple[Path, Path]]:
    """Return list of (src, dst) pairs — practice/ dirs to rename to test/."""
    migrations = []

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

                if not is_test_event(event_dir.name):
                    continue

                practice_dir = event_dir / "practice"
                test_dir     = event_dir / "test"

                if not practice_dir.is_dir():
                    continue

                if test_dir.exists():
                    # test/ already exists — need to merge files in
                    for f in practice_dir.iterdir():
                        if f.suffix.lower() == ".csv":
                            # Rename practice1.csv -> test1.csv etc if not already test-named
                            new_name = f.name
                            if new_name.startswith("practice"):
                                new_name = "test" + new_name[len("practice"):]
                            dst_file = test_dir / new_name
                            migrations.append((f, dst_file))
                else:
                    # Simple rename of the whole directory
                    migrations.append((practice_dir, test_dir))

    return migrations


def main():
    parser = argparse.ArgumentParser(
        description="Move practice/ → test/ for test/prologue events."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Actually move files (default is dry run)")
    parser.add_argument("--series", choices=["WEC", "ELMS", "IMSA"],
                        help="Only process one series")
    args = parser.parse_args()

    if not DATA_DIR.is_dir():
        print(f"data/ directory not found at {DATA_DIR}")
        return

    if not args.apply:
        print("DRY RUN — nothing will be moved. Use --apply to move.\n")

    migrations = find_migrations(DATA_DIR, args.series)

    if not migrations:
        print("Nothing to migrate — all test events already have test/ folders.")
        return

    moved = 0
    for src, dst in migrations:
        rel_src = src.relative_to(DATA_DIR)
        rel_dst = dst.relative_to(DATA_DIR)
        action = "move" if args.apply else "would move"
        print(f"  {action}: {rel_src}  →  {rel_dst}")

        if args.apply:
            if src.is_dir():
                src.rename(dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dst)
                # Remove practice/ dir if now empty
                if src.parent.is_dir() and not any(src.parent.iterdir()):
                    src.parent.rmdir()
        moved += 1

    print(f"\n{'='*50}")
    print(f"  Items: {moved}")
    if args.apply:
        print("  Done. Commit the data/ changes to GitHub.")
    else:
        print("  Run with --apply to move.")


if __name__ == "__main__":
    main()
