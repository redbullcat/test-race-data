"""pages/qualifying.py — Qualifying session analysis page."""
import os

import streamlit as st

from data_loader import load_practice_sessions
from practice_analysis import show_practice_analysis
from qualifying_story_chart import show_qualifying_story


def show_qualifying(session_dir: str, session_files: list[str], team_colors: dict):
    st.subheader("Qualifying Analysis")

    analysis_tab, story_tab = st.tabs(["Analysis", "Story"])

    with analysis_tab:
        show_practice_analysis(
            session_dir=session_dir,
            session_files=session_files,
            team_colors=team_colors,
            key_prefix="qual",
        )

    with story_tab:
        if not session_files:
            st.warning("No qualifying session files found.")
        else:
            df = load_practice_sessions(session_dir, tuple(session_files))
            if df.empty:
                st.error("Failed to load qualifying data.")
            else:
                show_qualifying_story(
                    df=df,
                    team_colors=team_colors,
                    session_files=session_files,
                    key_prefix="qual_story",
                )
