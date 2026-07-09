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
        (
            f'<div class="footer">'
            f'WC 2026 Predictor'
            f' &nbsp; · &nbsp; '
            f'{model_metadata["label"]}'
            f' &nbsp; · &nbsp; '
            f'{team_count} Teams'
            f'</div>'
        ),
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    """
    Render a standard section label.
    """

    st.markdown(
        f'<div class="section-label">{title}</div>',
        unsafe_allow_html=True,
    )