"""
css.py

Centralized stylesheet for the Streamlit application.

Contains all custom CSS used across the application.

No business logic should ever exist here.
"""

import streamlit as st

from assets.theme import (
    CLR_BG,
    CLR_SURFACE,
    CLR_BORDER,
    CLR_TEXT,
    CLR_MUTED,
    CLR_ACCENT,
    CLR_HOME,
    CLR_DRAW,
    CLR_AWAY,
)

def inject_css():

    st.markdown(f"""
    <style>
    /* ── Root ── */
    .stApp, [data-testid="stAppViewContainer"] {{
        background: {CLR_BG};
        color: {CLR_TEXT};
    }}
    [data-testid="stHeader"] {{
        background: transparent;
    }}

    /* ── Remove default Streamlit padding ── */
    .block-container {{
        padding-top: 2rem;
        padding-bottom: 4rem;
        max-width: 900px;
    }}

    /* ── Typography ── */
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Space Grotesk', sans-serif;
        color: {CLR_TEXT};
    }}

    /* ── Masthead ── */
    .masthead {{
        display: flex;
        align-items: baseline;
        gap: 12px;
        margin-bottom: 0.25rem;
    }}
    .masthead-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2rem;
        font-weight: 700;
        color: {CLR_TEXT};
        letter-spacing: -0.5px;
        line-height: 1;
    }}
    .masthead-accent {{
        color: {CLR_ACCENT};
    }}
    .masthead-sub {{
        font-family: 'Space Mono', monospace;
        font-size: 0.72rem;
        color: {CLR_MUTED};
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 2rem;
    }}

    /* ── Section labels ── */
    .section-label {{
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: {CLR_MUTED};
        margin-bottom: 0.6rem;
        padding-top: 1.6rem;
    }}

    /* ── Fixture selector card ── */
    .fixture-card {{
        background: {CLR_SURFACE};
        border: 1px solid {CLR_BORDER};
        border-radius: 8px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 0.5rem;
    }}
    .fixture-date {{
        font-family: 'Space Mono', monospace;
        font-size: 0.7rem;
        color: {CLR_MUTED};
        letter-spacing: 0.08em;
        margin-bottom: 0.3rem;
    }}
    .fixture-matchup {{
        font-size: 1.35rem;
        font-weight: 600;
        color: {CLR_TEXT};
        letter-spacing: -0.3px;
    }}
    .fixture-vs {{
        color: {CLR_MUTED};
        font-weight: 400;
        font-size: 1rem;
        margin: 0 8px;
    }}
    .fixture-stage {{
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        color: {CLR_ACCENT};
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-top: 0.25rem;
    }}

    /* ── Outcome metric cards ── */
    .metric-row {{
        display: flex;
        gap: 10px;
        margin: 1rem 0;
    }}
    .metric-card {{
        flex: 1;
        background: {CLR_SURFACE};
        border: 1px solid {CLR_BORDER};
        border-radius: 8px;
        padding: 1.1rem 1rem;
        text-align: center;
    }}
    .metric-card.home  {{ border-top: 3px solid {CLR_HOME}; }}
    .metric-card.draw  {{ border-top: 3px solid {CLR_DRAW}; }}
    .metric-card.away  {{ border-top: 3px solid {CLR_AWAY}; }}
    .metric-label {{
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: {CLR_MUTED};
        margin-bottom: 0.4rem;
    }}
    .metric-team {{
        font-size: 0.95rem;
        font-weight: 600;
        color: {CLR_TEXT};
        margin-bottom: 0.5rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .metric-pct {{
        font-family: 'Space Mono', monospace;
        font-size: 2.1rem;
        font-weight: 700;
        line-height: 1;
    }}
    .metric-card.home .metric-pct  {{ color: {CLR_HOME}; }}
    .metric-card.draw .metric-pct  {{ color: {CLR_DRAW}; }}
    .metric-card.away .metric-pct  {{ color: {CLR_AWAY}; }}
    .metric-xg {{
        font-family: 'Space Mono', monospace;
        font-size: 0.68rem;
        color: {CLR_MUTED};
        margin-top: 0.4rem;
    }}

    /* ── Expected goals display ── */
    .xg-bar-row {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 0.3rem 0;
    }}
    .xg-team-name {{
        font-size: 0.85rem;
        font-weight: 500;
        width: 130px;
        text-align: right;
        color: {CLR_TEXT};
    }}
    .xg-bar-outer {{
        flex: 1;
        background: {CLR_BORDER};
        border-radius: 3px;
        height: 6px;
        overflow: hidden;
    }}
    .xg-bar-inner {{
        height: 100%;
        border-radius: 3px;
        background: {CLR_ACCENT};
    }}
    .xg-val {{
        font-family: 'Space Mono', monospace;
        font-size: 0.8rem;
        color: {CLR_ACCENT};
        width: 36px;
    }}

    /* ── Team stat pills ── */
    .stat-grid {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 0.5rem;
    }}
    .stat-pill {{
        background: {CLR_SURFACE};
        border: 1px solid {CLR_BORDER};
        border-radius: 5px;
        padding: 5px 10px;
        font-family: 'Space Mono', monospace;
        font-size: 0.68rem;
        color: {CLR_MUTED};
    }}
    .stat-pill span {{
        color: {CLR_TEXT};
        font-weight: 700;
    }}

    /* ── Fallback warning ── */
    .fallback-warning {{
        background: #1A2E22;
        border-left: 3px solid #F59E0B;
        padding: 0.6rem 1rem;
        border-radius: 0 5px 5px 0;
        font-size: 0.8rem;
        color: #F59E0B;
        margin-bottom: 0.8rem;
    }}

    /* ── Model badge (Milestone 5) ── */
    .model-badge {{
        font-family: 'Space Mono', monospace;
        font-size: 0.72rem;
        color: {CLR_MUTED};
        letter-spacing: 0.02em;
        margin: 0.6rem 0 0.2rem 0;
    }}
    .model-badge b {{
        color: {CLR_ACCENT};
        font-weight: 700;
    }}

    /* ── Streamlit widget overrides ── */
    div[data-baseweb="select"] > div {{
        background: {CLR_SURFACE} !important;
        border-color: {CLR_BORDER} !important;
        color: {CLR_TEXT} !important;
    }}
    .stSelectbox label, .stMultiSelect label {{
        color: {CLR_MUTED} !important;
        font-family: 'Space Mono', monospace !important;
        font-size: 0.65rem !important;
        letter-spacing: 0.14em !important;
        text-transform: uppercase !important;
    }}
    div[data-testid="stMetricValue"] {{
        color: {CLR_ACCENT} !important;
    }}
    .stButton > button {{
        background: {CLR_ACCENT};
        color: {CLR_BG};
        border: none;
        border-radius: 6px;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 600;
        font-size: 0.85rem;
    }}
    .stButton > button:hover {{
        background: #bfda2e;
        color: {CLR_BG};
    }}

    /* ── Footer ── */
    .footer {{
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        color: {CLR_MUTED};
        text-align: center;
        padding-top: 3rem;
        letter-spacing: 0.08em;
    }}
    </style>
    """, unsafe_allow_html=True)