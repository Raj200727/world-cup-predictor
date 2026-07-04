"""
layout.py

Reusable layout helpers shared across the application.
"""

from __future__ import annotations

import streamlit as st

import math_engine as me


def render_footer(
    model_info: dict,
    stats: me.TeamStats,
) -> None:
    """
    Render the application footer.
    """

    st.markdown(
        (
            f'<div class="footer">'
            f'WC 2026 Predictor'
            f' &nbsp; · &nbsp; '
            f'{model_info["label"]}'
            f' &nbsp; · &nbsp; '
            f'{len(me.available_teams(stats))} Teams'
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