#!/usr/bin/env python3
"""
download_alkamel.py — local Al-Kamel CSV downloader for On The Apex.

Drives a real Chromium browser (via Playwright) on your machine, so Al-Kamel's
IP allowlist doesn't block it. Navigates each series page, selects every season
and event, extracts Analysis CSV links, and saves them into the correct folder
structure ready to push to GitHub.

Usage:
    python3 download_alkamel.py                        # download everything
    python3 download_alkamel.py --series WEC           # one series
    python3 download_alkamel.py --series WEC --year 2026
    python3 download_alkamel.py --series WEC --year 2026 --event spa
    python3 download_alkamel.py --dry-run              # show without saving
    python3 download_alkamel.py --skip-existing        # skip already-downloaded
    python3 download_alkamel.py --final-hour-only      # race: only download the
                                                       # last hour, not all hours

Setup (first time only):
    pip3 install playwright requests beautifulsoup4
    playwright install chromium

Output: ./data/  relative to this script's location.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

# ---------------------------------------------------------------------------
# Series config
# ---------------------------------------------------------------------------

SERIES_CONFIG = {
    "WEC": {
        "url": "https://fiawec.alkamelsystems.com/",
        # Filter on the championship folder segment only (not the whole URL).
        # All WEC main-series folders contain "WEC" (e.g. "01_WEC", "653_FIA WEC").
        # Support races (Legends of Le Mans, Porsche Supercup, etc.) never do.
        "championship_keywords": ["WEC"],
        "excluded_events": [],
    },
    "ELMS": {
        "url": "https://elms.alkamelsystems.com/",
        # Filter to the main ELMS championship folder only.
        # "European Le Mans Series" is the main series folder.
        # "ELMS Collective Test Day" is a test event folder — we still want those
        # so no filter needed; all content on this page is ELMS-related.
        "championship_keywords": [],
        "excluded_events": [],
    },
    "IMSA": {
        "url": "https://imsa.results.alkamelcloud.com/",
        # The old imsa.alkamelsystems.com is an incomplete mirror — it's missing
        # events (e.g. Belle Isle 2016). The cloud site is the full archive 2016–2026.
        # Match all naming variations of the main WeatherTech/SportsCar Championship:
        #   "01_IMSA SportsCar Championship"             (2016–2017 folder naming)
        #   "01_IMSA WeatherTech SportsCar Championship" (2018+ folder naming)
        # The championship folder filter checks parts[ri+3] specifically, so
        # "IMSA SportsCar" cannot match "02_IMSA Michelin Pilot Challenge".
        "championship_keywords": ["IMSA WeatherTech", "IMSA SportsCar"],
        # Skip these event types entirely regardless of championship filter
        "excluded_events": ["Encore", "encore"],
    },
}

# Filename patterns we want — everything else is ignored.
# Note: URLs encode spaces as %20, but BeautifulSoup decodes hrefs,
# so we match against the decoded string.
WANTED_PATTERNS = [
    "23_Analysis_",   # WEC/ELMS lap-by-lap analysis CSV
    "23_Time Cards",  # IMSA lap-by-lap time cards CSV — matches both
                      # "23_Time Cards.CSV" (older, no suffix) and
                      # "23_Time Cards_Race.CSV" (newer, with session suffix)
    "03_Results_",    # IMSA results CSV — fallback for sprint events that lack Time Cards
]

# Seconds to wait after selecting an event before reading the page
# Le Mans and other long events need longer because the HTML is huge
WAIT_NORMAL  = 2.0
WAIT_LE_MANS = 6.0   # Le Mans has up to 24 hours of results = very large page

DOWNLOAD_DELAY = 0.4   # seconds between file downloads

# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def strip_prefix(s: str) -> str:
    """Remove leading NN_ or YYYYMMDDHHNN_ numeric prefixes."""
    s = re.sub(r"^\d{12}_", "", s)
    s = re.sub(r"^\d{2}_", "", s)
    return s.strip()


def classify_session(session_name: str, sub_session: str = "", event_slug: str = "") -> str:
    combined = (session_name + " " + sub_session).lower()
    if "hyperpole" in combined or "qualifying" in combined:
        return "qualifying"
    if "race" in combined and "practice" not in combined:
        return "race"
    # Classify entire event as test if the event slug indicates it's a test/prologue:
    # "roar"     → IMSA Roar Before the 24
    # "test"     → WEC/ELMS/IMSA test days, IMSA February Test etc.
    # "prologue" → WEC Prologue (e.g. prologue-spa-francorchamps, the-prologue-paul-ricard)
    # "rookie"   → WEC Rookie Test (e.g. bahrain-rookie-test)
    # "official" → ELMS Official Test Session
    if any(kw in event_slug for kw in ("roar", "test", "prologue", "rookie", "official")):
        return "test"
    if "practice" in combined or "test" in combined or "session" in combined:
        return "practice"
    return "other"


def make_filename(session_name: str, sub_session: str, session_type: str, date_str: str = "") -> str:
    sn = session_name.lower()
    sub = (sub_session or "").lower()

    # Date suffix — only appended to race files
    date_suffix = f"_{date_str}" if date_str and session_type == "race" else ""

    if session_type == "race":
        m = re.search(r"hour\s*(\d+)", sub)
        if m:
            return f"race_hour{m.group(1)}{date_suffix}.csv"
        return f"race{date_suffix}.csv"

    if session_type == "qualifying":
        base = re.sub(r"[^a-z0-9_]", "_", sn.replace(" ", "_"))
        base = re.sub(r"_+", "_", base).strip("_")
        return base + ".csv"

    if session_type in ("practice", "test"):
        m = re.search(r"(\d+)", sn)
        if m:
            prefix = "test" if session_type == "test" else "practice"
            return f"{prefix}{m.group(1)}.csv"
        clean = re.sub(r"[^a-z0-9_]", "_",
                       sn.replace("free ", "").replace("practice", "practice_"))
        clean = re.sub(r"_+", "_", clean).strip("_")
        return clean + ".csv"

    return slugify(sn).replace("-", "_") + ".csv"


def parse_csv_url(url: str) -> dict | None:
    """
    Parse a CSV URL into metadata.
    Handles both flat session folders AND nested hour subfolders:
      .../Race/23_Analysis_Race.CSV            (flat — ELMS, IMSA)
      .../Race/06_Hour 6/23_Analysis_Race_Hour 6.CSV  (nested — WEC 6h)
      .../Race/24_Hour 24/23_Analysis_Race_Hour 24.CSV (nested — Le Mans)
    """
    decoded = unquote(url)
    parts = decoded.split("/")

    try:
        ri = parts.index("Results")
    except ValueError:
        return None

    if ri + 4 >= len(parts):
        return None

    season_part  = parts[ri + 1]   # e.g. "15_2026"
    round_part   = parts[ri + 2]   # e.g. "02_SPA FRANCORCHAMPS"
    # parts[ri+3] = championship folder
    session_part = parts[ri + 4]   # e.g. "202605071100_Free Practice 1" or "202605091400_Race"
    filename     = parts[-1]

    # Determine if there's a sub-session folder (Hour N) between session and filename
    # That happens when parts length allows it and parts[-2] is not the session folder
    maybe_sub = parts[ri + 5] if ri + 5 < len(parts) and not parts[ri + 5].upper().endswith(".CSV") else ""

    year       = re.sub(r"^\d+_", "", season_part)
    round_name = strip_prefix(round_part)
    round_slug = slugify(round_name)

    session_name = strip_prefix(session_part)
    sub_session  = strip_prefix(maybe_sub) if maybe_sub else ""

    # Extract YYYYMMDD date from the session folder timestamp prefix (first 8 chars)
    date_str = session_part[:8] if len(session_part) >= 8 and session_part[:8].isdigit() else ""

    session_type = classify_session(session_name, sub_session, event_slug=round_slug)
    new_filename = make_filename(session_name, sub_session, session_type, date_str)

    return {
        "year":         year,
        "round":        round_slug,
        "round_name":   round_name,
        "session_name": session_name,
        "sub_session":  sub_session,
        "session_type": session_type,
        "filename":     new_filename,
        "date":         date_str,
        "url":          url,
    }


def is_final_race_hour(url: str) -> bool:
    """
    Return True if this is the FINAL hour of a race (i.e. the cumulative file).
    We determine this by checking whether the URL contains a higher hour number
    than any other hour in the same race. Since we process URLs in order, we
    use a simpler heuristic: a URL is the "final" hour if it's the highest-
    numbered Hour N in the set. This is handled at the event level.
    """
    return True  # handled in the event loop below


# ---------------------------------------------------------------------------
# Browser scraper
# ---------------------------------------------------------------------------

def get_csv_links(page, base_url: str) -> list[str]:
    """Extract all wanted CSV links from the current page HTML."""
    from bs4 import BeautifulSoup
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.upper().endswith(".CSV"):
            continue
        if not href.startswith("http"):
            href = base_url.rstrip("/") + "/" + href.lstrip("/")
        # Check both encoded and decoded form — "23_Time Cards_" may appear
        # as "23_Time%20Cards_" in the raw href
        href_decoded = unquote(href)
        if any(p in href_decoded for p in WANTED_PATTERNS):
            links.append(href)
    return list(dict.fromkeys(links))


def filter_by_championship(links: list[str], championship_kws: list[str]) -> list[str]:
    """
    Keep only URLs where the championship folder (4th segment after 'Results')
    contains one of the keywords. Checking the folder specifically — rather than
    the whole URL — prevents false matches from event or session names.
    """
    if not championship_kws:
        return links
    filtered = []
    for url in links:
        decoded = unquote(url)
        parts = decoded.split("/")
        try:
            ri = parts.index("Results")
        except ValueError:
            continue
        # Championship folder is parts[ri+3]
        champ_folder = parts[ri + 3] if ri + 3 < len(parts) else ""
        if any(kw.lower() in champ_folder.lower() for kw in championship_kws):
            filtered.append(url)
    return filtered


def keep_final_hour_only(links: list[str]) -> list[str]:
    """
    For race events with multiple Hour N files, keep only the highest hour number.
    Practice and qualifying files are kept as-is.
    """
    # Separate race hour files from everything else
    hour_pattern = re.compile(r"/(\d{2})_Hour%20(\d+)/", re.IGNORECASE)
    race_hours: dict[str, tuple[int, str]] = {}  # race_session_key -> (max_hour, url)
    non_hour: list[str] = []

    for url in links:
        m = hour_pattern.search(url)
        if m:
            hour_num = int(m.group(2))
            # Key by the race session folder (everything up to the Hour subfolder)
            race_key = url[:url.index(m.group(0))]
            if race_key not in race_hours or hour_num > race_hours[race_key][0]:
                race_hours[race_key] = (hour_num, url)
        else:
            non_hour.append(url)

    return non_hour + [v[1] for v in race_hours.values()]


def prefer_time_cards(links: list[str]) -> list[str]:
    """
    For IMSA: when both a 23_Time Cards_ and a 03_Results_ file exist for the
    same session folder, keep only the Time Cards (it's the lap-by-lap data).
    The 03_Results_ is a classification/results table, not lap data.
    If only 03_Results_ exists (sprint events with no Time Cards), keep it.
    """
    from urllib.parse import unquote as _unquote

    # Group links by their session folder path
    session_groups: dict[str, list[str]] = {}
    for url in links:
        decoded = _unquote(url)
        parts = decoded.split("/")
        # Session folder = everything up to (not including) the filename
        session_key = "/".join(parts[:-1])
        session_groups.setdefault(session_key, []).append(url)

    result = []
    for session_key, session_links in session_groups.items():
        time_cards = [u for u in session_links
                      if "23_Time Cards" in unquote(u) or "23_Time%20Cards" in u]
        if time_cards:
            result.extend(time_cards)
        else:
            result.extend(session_links)

    return result


def safe_content(page, retries: int = 4, base_wait: float = 0.5) -> str:
    """Get page HTML with retries to handle mid-navigation calls."""
    for attempt in range(retries):
        try:
            time.sleep(base_wait * (attempt + 1))
            return page.content()
        except Exception:
            if attempt == retries - 1:
                raise
    return ""


def scrape_series(
    series: str,
    filter_year: str | None,
    filter_event: str | None,
    output_dir: Path,
    dry_run: bool,
    skip_existing: bool,
    final_hour_only: bool,
) -> list[dict]:
    from playwright.sync_api import sync_playwright
    import requests as req

    cfg = SERIES_CONFIG[series]
    base_url = cfg["url"]
    championship_kws = cfg["championship_keywords"]
    excluded_events = cfg.get("excluded_events", [])

    results = []

    sess = req.Session()
    sess.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": base_url,
    })

    def make_browser(p):
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ))
        page = ctx.new_page()
        return browser, page

    with sync_playwright() as p:
        browser, page = make_browser(p)

        print(f"\n{'='*60}")
        print(f"  {series}  —  {base_url}")
        print(f"{'='*60}")

        page.goto(base_url, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        from bs4 import BeautifulSoup

        # ── Discover seasons ──────────────────────────────────────────────
        body_text = page.inner_text("body")
        season_section = re.search(r"SEASON(.*?)EVENT", body_text, re.DOTALL)
        if not season_section:
            print(f"  [!] Could not find SEASON section")
            browser.close()
            return results

        season_pattern = re.compile(r"^(\d{4}(?:-\d{4})?)$")
        raw_seasons = season_section.group(1).strip().split()
        seasons = [s for s in raw_seasons if season_pattern.match(s)]

        if filter_year:
            seasons = [s for s in seasons if filter_year in s]

        if not seasons:
            print(f"  [!] No seasons found (filter: {filter_year})")
            browser.close()
            return results

        print(f"  Seasons to process: {seasons}")

        # ── Iterate seasons ───────────────────────────────────────────────
        for season in seasons:
            print(f"\n  Season: {season}")

            # Restart browser if it crashed
            try:
                page.title()
            except Exception:
                print(f"    [!] Browser crashed, restarting...")
                try:
                    browser.close()
                except Exception:
                    pass
                browser, page = make_browser(p)
                page.goto(base_url, wait_until="networkidle", timeout=30000)
                time.sleep(2)

            # Select season
            try:
                print(f"    Selecting season {season}...", end=" ", flush=True)
                page.locator("select").first.select_option(label=season)
                time.sleep(1.5)
                print("done")
            except Exception as e:
                print(f"\n    [!] Could not select season: {e}")
                continue

            # Read events for this season
            body_text = page.inner_text("body")
            event_section = re.search(r"EVENT(.*?)(?:,\s*SEASON|\Z)", body_text, re.DOTALL)
            if not event_section:
                print(f"    [!] No events found")
                continue

            raw_events = event_section.group(1).strip().split("\n")
            events = [e.strip() for e in raw_events if e.strip() and not e.strip().startswith("*")]
            starred = [e.strip().lstrip("* ") for e in raw_events if e.strip().startswith("*")]
            events = events + starred

            # Deduplicate events while preserving order
            seen_events: set[str] = set()
            unique_events: list[str] = []
            for e in events:
                if e not in seen_events:
                    seen_events.add(e)
                    unique_events.append(e)
            events = unique_events

            if filter_event:
                events = [e for e in events if filter_event.lower() in e.lower()]

            if not events:
                print(f"    [!] No events (filter: {filter_event})")
                continue

            print(f"    Events: {events}")

            # ── Iterate events ────────────────────────────────────────────
            for event_name in events:
                # Skip excluded event types (e.g. Encore post-season events)
                if any(ex.lower() in event_name.lower() for ex in excluded_events):
                    print(f"\n    Event: {event_name}")
                    print(f"      [skip] Excluded event type.")
                    continue

                print(f"\n    Event: {event_name}")

                # Select event
                try:
                    print(f"      Selecting...", end=" ", flush=True)
                    page.locator("select").nth(1).select_option(label=event_name)

                    # Le Mans is enormous — wait much longer for all hours to render
                    wait_time = WAIT_LE_MANS if "LE MANS" in event_name.upper() else WAIT_NORMAL
                    time.sleep(wait_time)
                    print("done")
                except Exception as e:
                    print(f"\n      [!] Could not select event: {e}")
                    continue

                html = safe_content(page)
                csv_links = get_csv_links(page, base_url)
                csv_links = filter_by_championship(csv_links, championship_kws)

                if not csv_links:
                    print(f"      No Analysis CSVs found.")
                    continue

                # For IMSA: prefer 23_Time Cards_ over 03_Results_ when both exist
                if series == "IMSA":
                    csv_links = prefer_time_cards(csv_links)

                # If --final-hour-only, discard intermediate race hour files
                if final_hour_only:
                    csv_links = keep_final_hour_only(csv_links)

                print(f"      Found {len(csv_links)} CSV(s)")

                # ── Download ──────────────────────────────────────────────
                for url in csv_links:
                    meta = parse_csv_url(url)
                    if not meta:
                        continue

                    dest = (
                        output_dir
                        / series
                        / meta["year"]
                        / meta["round"]
                        / meta["session_type"]
                        / meta["filename"]
                    )

                    rel = dest.relative_to(output_dir)

                    if skip_existing and dest.exists():
                        print(f"      [skip] {rel}")
                        results.append({**meta, "status": "skipped"})
                        continue

                    if dry_run:
                        print(f"      [dry]  {rel}")
                        results.append({**meta, "status": "dry-run"})
                        continue

                    dest.parent.mkdir(parents=True, exist_ok=True)

                    try:
                        r = sess.get(url, timeout=60)
                        if r.status_code == 200:
                            dest.write_bytes(r.content)
                            size_kb = len(r.content) // 1024
                            print(f"      [ok]   {rel}  ({size_kb} KB)")
                            results.append({**meta, "status": "downloaded"})
                        else:
                            print(f"      [err]  HTTP {r.status_code}  {dest.name}")
                            results.append({**meta, "status": f"http_{r.status_code}"})
                    except Exception as e:
                        print(f"      [err]  {e}  {dest.name}")
                        results.append({**meta, "status": "error"})

                    time.sleep(DOWNLOAD_DELAY)

        browser.close()

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Download Al-Kamel Analysis CSVs into the On The Apex data structure."
    )
    parser.add_argument("--series", choices=list(SERIES_CONFIG.keys()),
                        help="Series to download (default: all)")
    parser.add_argument("--year",  help="Year to download, e.g. 2026")
    parser.add_argument("--event", help="Event name substring, e.g. spa")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be downloaded without saving")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip files that already exist on disk")
    parser.add_argument("--final-hour-only", action="store_true",
                        help="For races with hourly files, only download the final hour")
    parser.add_argument("--output-dir", default="data",
                        help="Root data directory (default: ./data)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    print(f"Output directory: {output_dir}")

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        from bs4 import BeautifulSoup                    # noqa: F401
        import requests                                   # noqa: F401
    except ImportError as e:
        print(f"\nMissing dependency: {e}")
        print("\nRun:")
        print("  pip3 install playwright requests beautifulsoup4")
        print("  playwright install chromium")
        sys.exit(1)

    series_list = [args.series] if args.series else list(SERIES_CONFIG.keys())

    all_results = []
    for series in series_list:
        results = scrape_series(
            series=series,
            filter_year=args.year,
            filter_event=args.event,
            output_dir=output_dir,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            final_hour_only=args.final_hour_only,
        )
        all_results.extend(results)

    # Summary
    print(f"\n{'='*60}")
    print("  Summary")
    print(f"{'='*60}")
    from collections import Counter
    counts = Counter(r["status"] for r in all_results)
    for status, count in sorted(counts.items()):
        print(f"  {status:15s} {count}")
    print(f"  {'total':15s} {len(all_results)}")

    if args.dry_run:
        print("\n  Dry run — no files were saved.")
    elif any(r["status"] == "downloaded" for r in all_results):
        print(f"\n  Files saved to: {output_dir}")
        print("  Push to GitHub to make them available in the app.")


if __name__ == "__main__":
    main()
