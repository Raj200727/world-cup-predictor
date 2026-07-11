"""
layout.py

Reusable layout helpers shared across the application.
"""

from __future__ import annotations

import streamlit as st



def render_footer(
    model_metadata: dict,
    team_count: int,
) -> None:
    """
    Render the application footer.
    """

    st.markdown(
    f"""
    <div class="footer">
        World Cup Prediction Engine
        &nbsp;&nbsp;•&nbsp;&nbsp;
        {model_metadata["label"]}
        &nbsp;&nbsp;•&nbsp;&nbsp;
        {team_count} Teams
    </div>
    """,
    unsafe_allow_html=True,
)


def section(title: str) -> None:
    """
    Render a standard section label.
    """

    st.markdown(
        f"""
        <div class="section-block">
            <div class="section-label">{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )