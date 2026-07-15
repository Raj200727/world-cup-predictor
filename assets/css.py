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

    /* === 1. DESIGN SYSTEM (VARIABLES) === */

    :root {{
        --card-bg-gradient:  linear-gradient(145deg, #0d1a13 0%, #0a140f 100%);
        --card-border:       #182e22;
        --card-radius:       12px;
        --bracket-gap:       4px !important;
        --winner-highlight:  rgba(255, 255, 255, 0.08);

        /* Semantic colour aliases (sourced from theme.py) */
        --clr-bg:      {CLR_BG};
        --clr-surface: {CLR_SURFACE};
        --clr-border:  {CLR_BORDER};
        --clr-text:    {CLR_TEXT};
        --clr-muted:   {CLR_MUTED};
        --clr-accent:  {CLR_ACCENT};
        --clr-home:    {CLR_HOME};
        --clr-draw:    {CLR_DRAW};
        --clr-away:    {CLR_AWAY};

        /* Winner accent */
        --clr-winner:        #00ff66;
        --clr-winner-glow:   rgba(0, 255, 102, 0.05);
        --clr-selected:      #4da3ff;
        --clr-selected-glow: rgba(77, 163, 255, 0.45);

        /* Gold tokens */
        --clr-gold:          #ffd700;
        --clr-gold-glow:     rgba(255, 215, 0, 0.25);
        --clr-gold-bg:       rgba(255, 215, 0, 0.1);
        --clr-gold-border:   rgba(255, 215, 0, 0.2);
    }}

    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');


    /* === 2. GLOBAL STREAMLIT OVERRIDES === */

    .stApp,
    [data-testid="stAppViewContainer"] {{
        background: var(--clr-bg);
        color: var(--clr-text);
    }}

    [data-testid="stHeader"] {{
        background: transparent;
    }}

    html, body, [class*="css"] {{
        font-family: 'Space Grotesk', sans-serif;
        color: var(--clr-text);
    }}

    .block-container {{
        max-width: 1180px;
        padding-top: 1.5rem;
        padding-bottom: 5rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }}

    /* Streamlit select widget */
    div[data-baseweb="select"] > div {{
        background: var(--clr-surface) !important;
        border: 1px solid var(--clr-border) !important;
        border-radius: var(--card-radius) !important;
        color: var(--clr-text) !important;
        min-height: 54px;
    }}
    div[data-baseweb="select"] > div:hover {{
        border-color: var(--clr-accent) !important;
    }}
    div[data-baseweb="select"] span {{
        font-size: .96rem;
        font-weight: 600;
    }}
    div[role="listbox"] {{
        background: var(--clr-surface) !important;
        border: 1px solid var(--clr-border) !important;
    }}
    .stSelectbox label,
    .stMultiSelect label {{
        color: var(--clr-muted) !important;
        font-family: 'Space Mono', monospace !important;
        font-size: 0.65rem !important;
        letter-spacing: 0.14em !important;
        text-transform: uppercase !important;
    }}
    div[data-testid="stMetricValue"] {{
        color: var(--clr-accent) !important;
    }}
    .stButton > button {{
        background: var(--clr-accent);
        color: var(--clr-bg);
        border: none;
        border-radius: 6px;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 600;
        font-size: 0.85rem;
    }}
    .stButton > button:hover {{
        background: #bfda2e;
        color: var(--clr-bg);
    }}

    /* Forces bracket buttons to hug the bottom of their HTML cards */
    div[data-testid="stButton"] {{
        margin-top: -12px !important;
        position: relative;
        z-index: 10;
    }}


    /* === 3. BRACKET GRID & LAYOUT === */

    .bracket-wrapper {{
        position: relative;
        width: 100%;
        margin: 2rem 0;
    }}

    .bracket-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2rem;
        font-weight: 700;
        color: var(--clr-text);
        margin-top: 1.2rem;
        margin-bottom: 2rem;
        letter-spacing: -.4px;
    }}

    .bracket-layout {{
        display: flex;
        justify-content: space-between;
        gap: 6rem;
        margin: 3rem 0 4rem;
    }}

    .bracket-column {{
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 2rem;
    }}

    /* Row containers — must be position:relative so the SVG bridge
       anchors correctly and overflows into the gap below. */
    .bracket-final-row,
    .bracket-semi-row,
    .bracket-quarter-row {{
        position: relative;
        overflow: visible;
    }}

    .bracket-final-row   {{ margin-bottom: 70px; }}
    .bracket-semi-row    {{ margin-bottom: 70px; }}
    .bracket-quarter-row {{ margin-bottom: 90px; }}
    .bracket-third-row   {{ margin-top: 30px; }}

    /* Stage size constraints */
    .bracket-quarter {{ max-width: 340px; margin: 0 auto; }}
    .bracket-semi    {{ max-width: 520px; margin: 0 auto; }}
    .bracket-final   {{ max-width: 760px; margin: 0 auto 80px auto; }}
    .bracket-third   {{ max-width: 520px; margin: 0 auto; }}

    /* Positional helpers */
    .sf-slot    {{ margin-top: 90px; }}
    .final-slot {{ margin-top: 20px; margin-bottom: 55px; }}
    .third-slot {{ margin-top: 40px; }}

    .qf-left, .qf-right,
    .sf-left,  .sf-right,
    .final-column {{ position: relative; }}

    .bracket-stage {{
        text-align: center;
        font-size: 1.15rem;
        letter-spacing: .12em;
        padding-bottom: 40px;
        font-weight: 700;
        text-transform: uppercase;
        margin-top: 0;
        margin-bottom: 24px;
    }}

    .bracket-line {{
        height: 2px;
        background: var(--clr-border);
        width: 100%;
        opacity: .55;
        border-radius: 2px;
        margin: 1.4rem 0;
    }}

    .bracket-line-short {{
        height: 2px;
        background: var(--clr-border);
        width: 55%;
        margin: auto;
        opacity: .55;
        border-radius: 2px;
    }}

    .bracket-connector {{
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--clr-border);
        font-size: 1.6rem;
        opacity: .7;
    }}


    /* === 4. MATCH CARDS & CONTAINERS === */

    .bracket-card {{
        background: var(--card-bg-gradient);
        border: 1px solid var(--card-border);
        border-radius: var(--card-radius);
        padding: 12px;
        color: #e2e8f0;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
        transition: all 0.2s ease-in-out;
        position: relative;
        z-index: 10;
    }}

    .bracket-card:hover {{
        border-color: #274734;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.6);
        transform: translateY(-2px);
    }}

    /* Championship final — premium gold treatment */
    .bracket-card.bracket-final {{
        border: 2px solid var(--clr-gold);
        box-shadow: 0 0 25px var(--clr-gold-glow);
        padding: 22px 15px;
        background: linear-gradient(145deg, #0d1a13 0%, #050a07 100%);
    }}
    .bracket-card.bracket-final .bracket-team-name {{
        font-size: 1.15rem;
        font-weight: 700;
    }}
    .bracket-card.bracket-final .bracket-header {{
        font-size: 0.85rem;
        margin-bottom: 12px;
    }}

    /* Selected card highlight */
    .bracket-card-selected {{
        border: 2px solid var(--clr-selected);
        box-shadow: 0 0 18px var(--clr-selected-glow);
        transform: translateY(-3px) scale(1.02);
    }}

    .bracket-header {{
        display: flex;
        justify-content: center;
        margin-bottom: 8px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.05em;
    }}

    .bracket-status {{
        border-radius: 999px;
        font-size: .82rem;
        padding: .45rem .95rem;
        font-family: 'Space Mono', monospace;
        font-weight: 700;
        letter-spacing: .16em;
        text-transform: uppercase;
        color: #b7c3d0;
    }}
    .bracket-status.complete {{
        color: #a0aec0;
        background: rgba(160, 174, 192, 0.1);
        padding: 2px 8px;
        border-radius: 12px;
    }}
    .bracket-status.upcoming {{
        color: var(--clr-gold);
        background: var(--clr-gold-bg);
        padding: 2px 8px;
        border-radius: 12px;
        border: 1px solid var(--clr-gold-border);
    }}

    .bracket-team {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px;
        border-radius: 6px;
        background: transparent;
        transition: background 0.3s ease;
    }}
    .bracket-team.winner {{
        color: var(--clr-winner);
        font-weight: 700;
        background: var(--clr-winner-glow);
        border-left: 3px solid var(--clr-winner);
    }}
    .bracket-team.selected {{
        color: #ffffff;
        font-weight: 700;
    }}

    .bracket-team-name {{
        display: flex;
        align-items: center;
        flex: 1;
    }}

    .bracket-vs {{
        font-family: 'Space Mono', monospace;
        font-size: .72rem;
        letter-spacing: .22em;
        color: var(--clr-muted);
        text-align: center;
        margin: 1rem 0;
    }}

    .bracket-flag {{
        font-size: 1.7rem;
        margin-right: .7rem;
    }}

    .team-flag {{
        width: 30px;
        height: 22px;
        object-fit: cover;
        border-radius: 3px;
        margin-right: 10px;
        flex-shrink: 0;
        display: inline-block;
        vertical-align: middle;
    }}

    .score {{
        float: right;
        font-size: 1.3rem;
        font-weight: 800;
    }}

    .bracket-click-area {{
        position: absolute;
        inset: 0;
        z-index: 20;
    }}
    .bracket-click-area button {{
        opacity: 0;
        height: 0;
        padding: 0;
        margin: 0;
        border: none;
    }}

    /* Masthead */
    .masthead {{
        padding-bottom: .5rem;
        margin-bottom: 2.6rem;
    }}
    .masthead-eyebrow {{
        font-family: 'Space Mono', monospace;
        font-size: .70rem;
        color: var(--clr-muted);
        letter-spacing: .24em;
        text-transform: uppercase;
        margin-bottom: .55rem;
    }}
    .masthead-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 3.2rem;
        font-weight: 700;
        line-height: 1;
        letter-spacing: -1.2px;
        color: var(--clr-text);
    }}
    .masthead-title span {{ white-space: nowrap; }}
    .masthead-accent {{ color: var(--clr-accent); }}
    .masthead-sub {{
        margin-top: .9rem;
        font-size: .95rem;
        color: var(--clr-muted);
        line-height: 1.6;
        letter-spacing: .02em;
        max-width: 760px;
        opacity: .88;
    }}

    /* Section labels */
    .section-label {{
        font-family: 'Space Mono', monospace;
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .20em;
        text-transform: uppercase;
        color: var(--clr-muted);
        margin-top: 2.25rem;
        margin-bottom: .9rem;
    }}
    .section-block {{ margin-bottom: 2.5rem; }}

    /* Fixture selector card */
    .fixture-card {{
        background: var(--clr-surface);
        border: 1px solid var(--clr-border);
        border-radius: 20px;
        padding: 2rem;
        margin-top: 1rem;
        margin-bottom: 2.5rem;
        box-shadow:
            0 12px 30px rgba(0, 0, 0, .16),
            0 1px 0 rgba(255, 255, 255, .03) inset;
    }}
    .fixture-card:hover {{
        border-color: var(--clr-accent);
        box-shadow:
            0 18px 36px rgba(0, 0, 0, .18),
            0 1px 0 rgba(255, 255, 255, .03) inset;
    }}
    .fixture-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1.4rem;
    }}
    .fixture-header > div {{ white-space: nowrap; }}
    .fixture-divider {{
        height: 1px;
        background: var(--clr-border);
        margin-bottom: 1.5rem;
    }}
    .fixture-date {{
        font-family: 'Space Mono', monospace;
        font-size: .74rem;
        color: var(--clr-muted);
        text-transform: uppercase;
        letter-spacing: .16em;
        margin-bottom: .7rem;
    }}
    .fixture-matchup {{
        font-size: 2rem;
        font-weight: 700;
        color: var(--clr-text);
        letter-spacing: -.8px;
        line-height: 1.25;
    }}
    .fixture-vs {{
        color: var(--clr-muted);
        font-family: 'Space Mono', monospace;
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .35em;
        margin: 0 1rem;
    }}
    .fixture-stage {{
        font-family: 'Space Mono', monospace;
        font-size: .72rem;
        color: var(--clr-accent);
        text-transform: uppercase;
        letter-spacing: .18em;
        margin-top: .85rem;
    }}
    .fixture-match-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1.5rem;
    }}
    .fixture-team {{
        flex: 1;
        text-align: center;
        font-size: 1.9rem;
        font-weight: 700;
        color: var(--clr-text);
        letter-spacing: -0.6px;
        line-height: 1.2;
    }}

    /* Outcome metric cards */
    .metric-row {{
        display: flex;
        gap: 10px;
        margin: 1rem 0;
    }}
    .metric-card {{
        flex: 1;
        background: var(--clr-surface);
        border: 1px solid var(--clr-border);
        border-radius: 14px;
        padding: 1.35rem;
        text-align: center;
    }}
    .metric-card:hover          {{ border-color: var(--clr-accent); }}
    .metric-card.home           {{ border-top: 3px solid var(--clr-home); }}
    .metric-card.draw           {{ border-top: 3px solid var(--clr-draw); }}
    .metric-card.away           {{ border-top: 3px solid var(--clr-away); }}
    .metric-card.home .metric-pct {{ color: var(--clr-home); }}
    .metric-card.draw .metric-pct {{ color: var(--clr-draw); }}
    .metric-card.away .metric-pct {{ color: var(--clr-away); }}

    .metric-label {{
        font-family: 'Space Mono', monospace;
        font-size: 0.68rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--clr-muted);
        margin-bottom: 0.4rem;
    }}
    .metric-team {{
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--clr-text);
        margin-bottom: 0.5rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .metric-pct {{
        font-family: 'Space Mono', monospace;
        font-size: 2.6rem;
        font-weight: 700;
        line-height: 1;
    }}
    .metric-xg {{
        font-family: 'Space Mono', monospace;
        font-size: 0.68rem;
        color: var(--clr-muted);
        margin-top: 0.4rem;
    }}

    /* xG bar display */
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
        color: var(--clr-text);
    }}
    .xg-bar-outer {{
        flex: 1;
        background: var(--clr-border);
        border-radius: 3px;
        height: 6px;
        overflow: hidden;
    }}
    .xg-bar-inner {{
        height: 100%;
        border-radius: 3px;
        background: var(--clr-accent);
    }}
    .xg-val {{
        font-family: 'Space Mono', monospace;
        font-size: 0.8rem;
        color: var(--clr-accent);
        width: 36px;
    }}

    /* Team stat pills */
    .stat-grid {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 0.5rem;
    }}
    .stat-pill {{
        background: var(--clr-surface);
        border: 1px solid var(--clr-border);
        border-radius: 999px;
        padding: 5px 10px;
        font-family: 'Space Mono', monospace;
        font-size: 0.68rem;
        color: var(--clr-muted);
    }}
    .stat-pill span {{
        color: var(--clr-text);
        font-weight: 700;
    }}

    /* Fallback warning */
    .fallback-warning {{
        background: #1A2E22;
        border-left: 3px solid #F59E0B;
        padding: 0.6rem 1rem;
        border-radius: 0 5px 5px 0;
        font-size: 0.8rem;
        color: #F59E0B;
        margin-bottom: 0.8rem;
    }}

    /* Model badge */
    .model-badge {{
        font-family: 'Space Mono', monospace;
        font-size: 0.72rem;
        color: var(--clr-muted);
        letter-spacing: 0.02em;
        margin: 0.6rem 0 0.2rem 0;
    }}
    .model-badge b {{
        color: var(--clr-accent);
        font-weight: 700;
    }}

    /* Prediction section */
    .prediction-header {{
        text-align: center;
        margin-bottom: 1.5rem;
    }}
    .prediction-title {{
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--clr-text);
    }}
    .prediction-subtitle {{
        margin-top: .35rem;
        color: #8da59a;
        font-size: .95rem;
        text-transform: uppercase;
        letter-spacing: .08em;
    }}
    .prediction-callout {{
        margin-top: 1.5rem;
        padding: 1rem;
        border-radius: 14px;
        text-align: center;
        background: #123322;
        border: 1px solid var(--winner-highlight);
    }}
    .prediction-callout strong {{
        display: block;
        margin: .35rem 0;
        font-size: 1.3rem;
        color: var(--clr-text);
    }}

    /* Footer */
    .footer {{
        font-family: 'Space Mono', monospace;
        font-size: .68rem;
        color: var(--clr-muted);
        text-align: center;
        padding-top: 5rem;
        opacity: .7;
        letter-spacing: .12em;
    }}


    /* === 5. SVG CONNECTOR GEOMETRY === */

    /* The SVG canvas locked behind bracket columns */
    .bracket-svg-canvas {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 0;
        pointer-events: none;
    }}

    /* Bridge container — sits between rows, fills the margin-bottom gap */
    .bracket-bridge {{
        width: 100%;
        position: relative;
        z-index: 1;
        pointer-events: none;
        margin: -15px 0;
    }}
    .bracket-bridge svg {{
        width: 100%;
        height: 100%;
        overflow: visible;
        display: block;
    }}

    /* Connector line base state */
    .connector-line {{
        transition: stroke 0.3s ease, filter 0.3s ease;
    }}

    /* Winner path — glowing green stroke */
    .connector-line.winner-path {{
        stroke: var(--clr-winner) !important;
        filter: drop-shadow(0px 0px 8px rgba(0, 255, 102, 0.6));
    }}

    </style>
    """, unsafe_allow_html=True)