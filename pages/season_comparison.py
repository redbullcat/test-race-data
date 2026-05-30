"""pages/season_comparison.py — Team season comparison page."""

import streamlit as st
from team_season_comparison import show_team_season_comparison


def show_season_comparison(df, team_colors, year, series):
    show_team_season_comparison(df, team_colors, year=year, series=series)
