"""pages/qualifying.py — Qualifying session analysis page."""
import streamlit as st
from practice_analysis import show_practice_analysis


def show_qualifying(session_dir: str, session_files: list[str], team_colors: dict):
    st.subheader("Qualifying Analysis")
    show_practice_analysis(
        session_dir=session_dir,
        session_files=session_files,
        team_colors=team_colors,
        key_prefix="qual",
    )
