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

<div class="masthead-eyebrow">
FIFA WORLD CUP 2026
</div>

<div class="masthead-title">
World Cup <span class="masthead-accent">Prediction</span> Engine
</div>

<div class="masthead-sub">
Poisson-based forecasting for every FIFA World Cup 2026 fixture,
combining historical performance, expected goals and team strength
to estimate win probabilities and the most likely scorelines.
</div>

</div>
""",
        unsafe_allow_html=True,
    )