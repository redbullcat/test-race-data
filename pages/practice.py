"""pages/practice.py — Practice / test session analysis page."""

from practice_analysis import show_practice_analysis


def show_practice(data_dir, year, series, race, team_colors):
    show_practice_analysis(
        data_dir=data_dir,
        year=year,
        series=series,
        race=race,
        team_colors=team_colors,
    )
