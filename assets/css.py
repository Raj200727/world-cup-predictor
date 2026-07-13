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
    max-width: 1180px;
    padding-top: 1.5rem;
    padding-bottom: 5rem;
    padding-left: 2rem;
    padding-right: 2rem;
    }}

    /* ── Typography ── */
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Space Grotesk', sans-serif;
        color: {CLR_TEXT};
    }}

    /* ── Premium Masthead ───────────────────────────── */

.masthead {{

    padding-bottom:.5rem;

    margin-bottom:2.6rem;

}}

.masthead-eyebrow{{

    font-family:'Space Mono', monospace;

    font-size:.70rem;

    color:{CLR_MUTED};

    letter-spacing:.24em;

    text-transform:uppercase;

    margin-bottom:.55rem;

}}

.masthead-title{{

    font-family:'Space Grotesk', sans-serif;

    font-size:3.2rem;

    font-weight:700;

    line-height:1;

    letter-spacing:-1.2px;

    color:{CLR_TEXT};

}}

.masthead-accent{{

    color:{CLR_ACCENT};

}}
.masthead-title span {{

    white-space:nowrap;

}}

.masthead-sub{{

    margin-top:.9rem;

    font-size:.95rem;

    color:{CLR_MUTED};

    line-height:1.6;

    letter-spacing:.02em;

    max-width:760px;

    opacity:.88;

}}

    /* ── Section labels ── */
    .section-label{{

    font-family:'Space Mono', monospace;

    font-size:.72rem;

    font-weight:700;

    letter-spacing:.20em;

    text-transform:uppercase;

    color:{CLR_MUTED};

    margin-top:2.25rem;

    margin-bottom:.9rem;

    }}
    .section-block{{
    margin-bottom:2.5rem;
    }}

    /* ── Fixture selector card ── */
    .fixture-card{{

    background:{CLR_SURFACE};

    border:1px solid {CLR_BORDER};

    border-radius:20px;

    padding:2rem;

    margin-top:1rem;

    margin-bottom:2.5rem;

    box-shadow:
    0 12px 30px rgba(0,0,0,.16),
    0 1px 0 rgba(255,255,255,.03) inset;

    }}
    .fixture-header {{

    display:flex;

    justify-content:space-between;

    align-items:center;

    gap:1rem;

    margin-bottom:1.4rem;

}}
.fixture-divider {{

    height:1px;

    background:{CLR_BORDER};

    margin-bottom:1.5rem;

}}
    .fixture-date{{

    font-family:'Space Mono', monospace;

    font-size:.74rem;

    color:{CLR_MUTED};

    text-transform:uppercase;

    letter-spacing:.16em;

    margin-bottom:.7rem;

    }}
    .fixture-matchup{{

    font-size:2rem;

    font-weight:700;

    color:{CLR_TEXT};

    letter-spacing:-.8px;

    line-height:1.25;

    }}
    .fixture-vs{{

    color:{CLR_MUTED};

    font-family:'Space Mono', monospace;

    font-size:.78rem;

    font-weight:700;

    letter-spacing:.35em;

    margin:0 1rem;

    }}
    .fixture-stage{{

    font-family:'Space Mono', monospace;

    font-size:.72rem;

    color:{CLR_ACCENT};

    text-transform:uppercase;

    letter-spacing:.18em;

    margin-top:.85rem;

    }}
    .fixture-match-row {{

    display:flex;

    align-items:center;

    justify-content:space-between;

    gap:1.5rem;

    }}
    .fixture-team {{

    flex:1;

    text-align:center;

    font-size:1.9rem;

    font-weight:700;

    color:{CLR_TEXT};

    letter-spacing:-0.6px;

    line-height:1.2;

    }}
    .fixture-card:hover {{

    border-color:{CLR_ACCENT};

    box-shadow:
        0 18px 36px rgba(0,0,0,.18),
        0 1px 0 rgba(255,255,255,.03) inset;

    }}  
    .fixture-header > div {{

    white-space:nowrap;

    }}

    /* ── Outcome metric cards ── */
    .metric-row {{
        display: flex;
        gap: 10px;
        margin: 1rem 0;
    }}
    .metric-card{{

    flex:1;

    background:{CLR_SURFACE};

    border:1px solid {CLR_BORDER};

    border-radius:14px;

    padding:1.35rem;

    text-align:center;

    }}
    .metric-card:hover {{

    border-color:{CLR_ACCENT};

    }}
    .metric-card.home  {{ border-top: 3px solid {CLR_HOME}; }}
    .metric-card.draw  {{ border-top: 3px solid {CLR_DRAW}; }}
    .metric-card.away  {{ border-top: 3px solid {CLR_AWAY}; }}
    .metric-label {{
        font-family: 'Space Mono', monospace;
        font-size: 0.68rem;
        letter-spacing:0.18em;
        text-transform: uppercase;
        color: {CLR_MUTED};
        margin-bottom: 0.4rem;
    }}
    .metric-team {{
        font-size: 1.05rem;
        font-weight: 600;
        color: {CLR_TEXT};
        margin-bottom: 0.5rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .metric-pct{{

    font-family:'Space Mono', monospace;

    font-size:2.6rem;

    font-weight:700;

    line-height:1;

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
        border-radius: 999px;
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
        background:{CLR_SURFACE}!important;
        border:1px solid {CLR_BORDER}!important;
        border-radius:12px!important;
        color:{CLR_TEXT}!important;
        min-height:54px;
    }}

    div[data-baseweb="select"] > div:hover {{
        border-color:{CLR_ACCENT}!important;
    }}
    div[data-baseweb="select"] span {{

    font-size:.96rem;

    font-weight:600;

    }}
    div[role="listbox"] {{

    background:{CLR_SURFACE}!important;

    border:1px solid {CLR_BORDER}!important;

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
/* ──────────────────────────────────────────────
   Quarter Final Bracket
────────────────────────────────────────────── */

.bracket-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: {CLR_TEXT};
    margin-top: 1.2rem;
    margin-bottom: 2rem;
    letter-spacing: -.4px;
}}

.bracket-card {{
    background: {CLR_SURFACE};
    border: 1px solid {CLR_BORDER};
    padding: 1.25rem;
    margin-bottom: 1.0rem;
    border-radius: 22px;
    min-height: 115px;
    box-shadow:
        0 8px 22px rgba(0,0,0,.16),
        0 1px 0 rgba(255,255,255,.03) inset;
    transition:
        transform .2s ease,
        box-shadow .2s ease,
        border .2s ease;
}}

.bracket-quarter{{
    min-height:220px;
}}

.bracket-semi{{
    min-height:290px;
    width:108%;
    margin-left:-4%;
}}

.bracket-final{{
    min-height:340px;
    width:115%;
    margin-left:-7.5%;
}}

.bracket-third{{
    min-height:300px;
}}

.bracket-card:hover {{
    border-color: {CLR_ACCENT};
    box-shadow:
        0 14px 34px rgba(0,0,0,.20),
        0 1px 0 rgba(255,255,255,.03) inset;
}}

.bracket-header {{
    display: flex;
    justify-content: flex-end;
    margin-bottom: 1.4rem;
}}

.bracket-status {{
    border-radius: 999px;
    font-size:.82rem;
    padding:.45rem .95rem;
    color: #b7c3d0;
    font-family: 'Space Mono', monospace;
    font-weight: 700;
    letter-spacing: .16em;
    text-transform: uppercase;
}}

.bracket-status.complete {{
    background: rgba(34,197,94,.12);
    color: #4ADE80;
}}

.bracket-status.upcoming {{
    background: rgba(245,158,11,.12);
    color: #FBBF24;
}}

.bracket-team {{
    display: flex;
    align-items: center;
    justify-content: space-between;

    font-size: 1.18rem;
    font-weight: 600;
    color: {CLR_TEXT};

    padding: .55rem 0;
    line-height: 1.5;
}}
.bracket-flag {{
    font-size: 1.7rem;
    margin-right: .7rem;
}}
.bracket-team-name {{
    display: flex;
    align-items: center;
    flex: 1;
}}

.bracket-team.winner {{
    background:linear-gradient(
    90deg,
    rgba(34,197,94,.18),
    rgba(34,197,94,.05)
    );
    color: #fff;
    font-weight: 700;
    border-left: 6px solid #22c55e;
}}

.bracket-vs {{
    font-family: 'Space Mono', monospace;
    font-size: .72rem;
    letter-spacing: .22em;
    color: {CLR_MUTED};
    text-align: center;
    margin: 1rem 0;
}}

/* ── Tournament Bracket ───────────────────────── */

.bracket-layout {{
    display: flex;
    justify-content: space-between;
    gap:6rem;
    margin:3rem 0 4rem;
}}

.bracket-column {{
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2rem;
}}

/* ── CHANGED: stage label uses margin-bottom:auto to push the card
      below it into the flex-centered position within the column. ── */
.bracket-stage {{
    text-align: center;
    font-size: 1.15rem;
    letter-spacing:.12em;
    padding-bottom:40px;
    font-weight: 700;
    text-transform: uppercase;
    margin-top: 0;
    margin-bottom: auto;
}}

.bracket-connector {{
    display: flex;
    align-items: center;
    justify-content: center;
    color: {CLR_BORDER};
    font-size: 1.6rem;
    opacity: .7;
}}

.bracket-line {{
    height: 2px;
    background: {CLR_BORDER};
    width: 100%;
    opacity: .55;
    border-radius: 2px;
    margin: 1.4rem 0;
}}

.bracket-line-short {{
    height: 2px;
    background: {CLR_BORDER};
    width: 55%;
    margin: auto;
    opacity: .55;
    border-radius: 2px;
}}

.bracket-card-selected {{
    border: 2px solid #4da3ff;
    box-shadow: 0 0 18px rgba(77,163,255,.45);
    transform:
    translateY(-3px)
    scale(1.02);
}}

.score {{
    float: right;
    font-size:1.3rem;
    font-weight:800;
}}

.bracket-team.selected {{
    color: #ffffff;
    font-weight: 700;
}}

.bracket-click-area button {{
    opacity: 0;
    height: 0;
    padding: 0;
    margin: 0;
    border: none;
}}

.bracket-click-area {{
    position: absolute;
    inset: 0;
    z-index: 20;
}}
.sf-slot{{
    margin-top:90px;
}}

.final-slot{{
    margin-top:20px;
    margin-bottom:55px;
}}

.third-slot{{
    margin-top:40px;
}}
/*Prediction section
*/
.prediction-header{{
    text-align:center;
    margin-bottom:1.5rem;
}}

.prediction-title{{
    font-size:1.8rem;
    font-weight:700;
    color:#ffffff;
}}

.prediction-subtitle{{
    margin-top:.35rem;
    color:#8da59a;
    font-size:.95rem;
    text-transform:uppercase;
    letter-spacing:.08em;
}}

.prediction-callout{{
    margin-top:1.5rem;
    padding:1rem;
    border-radius:14px;
    text-align:center;
    background:#123322;
    border:1px solid rgba(255,255,255,.08);
}}

.prediction-callout strong{{
    display:block;
    margin:.35rem 0;
    font-size:1.3rem;
    color:white;
}}
.qf-left,
.qf-right,
.sf-left,
.sf-right,
.final-column{{
    position:relative;
}}
.qf-left::after{{
    content:"";
    position:absolute;

    top:50%;
    right:-42px;

    width:42px;
    height:2px;

    background:#35584A;
}}
.qf-right::before{{
    content:"";

    position:absolute;

    top:50%;
    left:-42px;

    width:42px;
    height:2px;

    background:#35584A;
}}
.qf-left::before{{
    content:"";

    position:absolute;

    right:-42px;

    top:22%;

    width:2px;
    height:56%;

    background:#35584A;
}}
.qf-right::after{{
    content:"";

    position:absolute;

    left:-42px;

    top:22%;

    width:2px;
    height:56%;

    background:#35584A;
}}
.sf-left::after{{
    content:"";

    position:absolute;

    top:50%;
    right:-55px;

    width:55px;
    height:2px;

    background:#35584A;
}}
.sf-right::before{{
    content:"";

    position:absolute;

    top:50%;
    left:-55px;

    width:55px;
    height:2px;

    background:#35584A;
}}
.final-column::before{{
    content:"";

    position:absolute;

    left:-55px;

    top:50%;

    width:55px;
    height:3px;

    background:#B9FF37;
}}
.final-column::after{{
    content:"";

    position:absolute;

    right:-55px;

    top:50%;

    width:55px;
    height:3px;

    background:#B9FF37;
}}
    /* ── Footer ── */
    .footer {{

    font-family:'Space Mono', monospace;

    font-size:.68rem;

    color:{CLR_MUTED};

    text-align:center;

    padding-top:5rem;

    opacity:.7;

    letter-spacing:.12em;

    }}
    </style>
    """, unsafe_allow_html=True)