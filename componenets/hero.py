"""
hero.py

Renders the application hero section.
"""

import streamlit as st


def render() -> None:
    """Render the application masthead."""

    st.markdown(
        """
        <div class="masthead">
            <div class="masthead-title">
                World Cup <span class="masthead-accent">2026</span>
            </div>
        </div>

        <div class="masthead-sub">
            Match Probability Engine · Poisson Model
        </div>
        """,
        unsafe_allow_html=True,
    )