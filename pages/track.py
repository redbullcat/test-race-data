"""pages/track.py — Track SVG viewer page."""

import streamlit as st
from track_analysis import show_track_analysis


def show_track(df, team_colors):
    show_track_analysis(df, team_colors)
