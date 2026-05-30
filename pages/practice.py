"""pages/practice.py — Practice / test session analysis page."""

from practice_analysis import show_practice_analysis


def show_practice(session_dir: str, session_files: list[str], team_colors: dict):
    """
    New signature: receives the resolved session directory and list of filenames
    rather than rebuilding paths from series/year/race.
    """
    show_practice_analysis(
        session_dir=session_dir,
        session_files=session_files,
        team_colors=team_colors,
    )
