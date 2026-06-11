"""
app.py — World Cup 2026 Predictor
===================================
Streamlit frontend for the Poisson match prediction engine.

Run with:
    streamlit run app.py

Requires predictor.db in the same directory (populated by ingest_api.py
and ingest_csv.py) and math_engine.py on the Python path.

Architecture
------------
- All heavy computation (team stats, Poisson matrix) is @st.cache_data
  so widget interactions are instant — no recalculation on every click.
- Fixtures are read from upcoming_fixtures table (WC 2026 schedule).
  Falls back to a manual team picker if that table is empty.
- Imports math_engine directly — zero duplicated Poisson logic.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Math engine import
# ---------------------------------------------------------------------------
try:
    import math_engine as me
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).parent))
    import math_engine as me

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH         = "predictor.db"
TRAIN_SEASONS   = list(range(1930, 2023, 4))   # 1930–2022 full history
UPCOMING_SEASON = 2026

# Palette
CLR_BG          = "#0D1F17"
CLR_SURFACE     = "#132B1E"
CLR_BORDER      = "#1F3D2B"
CLR_ACCENT      = "#D4F13A"
CLR_TEXT        = "#E8F5E9"
CLR_MUTED       = "#6B8F77"
CLR_HOME        = "#D4F13A"   # acid yellow  — home team
CLR_DRAW        = "#4A9B6F"   # mid green    — draw
CLR_AWAY        = "#1A6B42"   # deep green   — away team
CLR_SCORELINE   = "#2ECC71"   # bright green — scoreline bars

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title  = "WC 2026 Predictor",
    page_icon   = "⚽",
    layout      = "wide",
    initial_sidebar_state = "collapsed",
)

# ---------------------------------------------------------------------------
# Global CSS injection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_stats() -> me.TeamStats:
    """Load team stats once; cached for the session."""
    return me.load_team_stats(
        db_path            = DB_PATH,
        seasons            = TRAIN_SEASONS,
        exclude_extra_time = True,
    )


@st.cache_data(show_spinner=False)
def load_fixtures() -> list[dict]:
    """
    Load WC 2026 upcoming fixtures from predictor.db.
    Returns list of dicts sorted by utc_date.
    Falls back to [] if table doesn't exist or is empty.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                match_id,
                utc_date,
                home_team_name,
                away_team_name,
                stage,
                "group",
                status
            FROM upcoming_fixtures
            WHERE competition = 'WC'
              AND season      = ?
            ORDER BY utc_date
            """,
            (UPCOMING_SEASON,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _format_date(raw: str) -> str:
    """Convert ISO datetime string to display format."""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", ""))
        return dt.strftime("%a %d %b  ·  %H:%M UTC")
    except Exception:
        return str(raw)


def _format_stage(stage: Optional[str], group: Optional[str]) -> str:
    if not stage:
        return ""
    label = stage.replace("_", " ").title()
    if group:
        label = f"{group}  ·  {label}"
    return label


# ---------------------------------------------------------------------------
# Plotly chart builders
# ---------------------------------------------------------------------------

def make_outcome_bar(result: me.MatchResult) -> go.Figure:
    """
    Horizontal probability bar — home / draw / away stacked.
    This is the signature visual: bar widths ARE the probabilities.
    """
    hw = result.home_win_prob
    d  = result.draw_prob
    aw = result.away_win_prob

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[hw], y=[""], orientation="h",
        marker_color=CLR_HOME,
        name=result.home_team,
        text=f"{hw:.0%}",
        textposition="inside",
        textfont=dict(family="Space Mono", size=13, color=CLR_BG),
        hovertemplate=f"<b>{result.home_team} win</b><br>{hw:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=[d], y=[""], orientation="h",
        marker_color=CLR_DRAW,
        name="Draw",
        text=f"{d:.0%}" if d >= 0.10 else "",
        textposition="inside",
        textfont=dict(family="Space Mono", size=13, color=CLR_TEXT),
        hovertemplate=f"<b>Draw</b><br>{d:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=[aw], y=[""], orientation="h",
        marker_color=CLR_AWAY,
        name=result.away_team,
        text=f"{aw:.0%}",
        textposition="inside",
        textfont=dict(family="Space Mono", size=13, color=CLR_TEXT),
        hovertemplate=f"<b>{result.away_team} win</b><br>{aw:.1%}<extra></extra>",
    ))

    fig.update_layout(
        barmode="stack",
        height=70,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False),
    )
    return fig


def make_scoreline_chart(result: me.MatchResult, top_n: int = 8) -> go.Figure:
    """
    Horizontal bar chart of the top N most likely exact scorelines.
    """
    scorelines = result.scorelines[:top_n]
    labels  = [s[0] for s in scorelines][::-1]
    probs   = [s[1] for s in scorelines][::-1]

    # Colour each bar by outcome
    colors = []
    for lbl in labels:
        parts = lbl.replace("–", "-").split("-")
        try:
            h, a = int(parts[0]), int(parts[1])
        except ValueError:
            colors.append(CLR_DRAW)
            continue
        if h > a:
            colors.append(CLR_HOME)
        elif a > h:
            colors.append(CLR_AWAY)
        else:
            colors.append(CLR_DRAW)

    fig = go.Figure(go.Bar(
        x=probs,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{p:.1%}" for p in probs],
        textposition="outside",
        textfont=dict(family="Space Mono", size=11, color=CLR_TEXT),
        hovertemplate="%{y}  →  %{x:.1%}<extra></extra>",
        cliponaxis=False,
    ))

    fig.update_layout(
        height=max(260, top_n * 38),
        margin=dict(l=0, r=60, t=4, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            visible=True,
            showgrid=True,
            gridcolor=CLR_BORDER,
            tickformat=".0%",
            tickfont=dict(family="Space Mono", size=10, color=CLR_MUTED),
            zeroline=False,
            range=[0, max(probs) * 1.35],
        ),
        yaxis=dict(
            tickfont=dict(family="Space Mono", size=12, color=CLR_TEXT),
            gridcolor="rgba(0,0,0,0)",
        ),
        bargap=0.28,
    )
    return fig


def make_scoreline_heatmap(result: me.MatchResult) -> go.Figure:
    """
    Goals probability heatmap — the raw Poisson matrix, capped at 5×5
    for readability.
    """
    matrix = result.matrix[:6, :6]   # 0–5 goals each side
    home   = result.home_team
    away   = result.away_team

    z_text = [[f"{matrix[i, j]:.1%}" for j in range(6)] for i in range(6)]

    fig = go.Figure(go.Heatmap(
        z=matrix,
        text=z_text,
        texttemplate="%{text}",
        textfont=dict(family="Space Mono", size=10),
        colorscale=[
            [0.0,  "#0D1F17"],
            [0.15, "#1A4B2F"],
            [0.40, "#2ECC71"],
            [0.70, "#9EF53A"],
            [1.0,  "#D4F13A"],
        ],
        showscale=False,
        hovertemplate=(
            f"{home} %{{y}}–%{{x}} {away}<br>Probability: %{{text}}<extra></extra>"
        ),
    ))

    fig.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title=dict(text=away, font=dict(family="Space Grotesk", size=12,
                                            color=CLR_MUTED)),
            tickvals=list(range(6)),
            tickfont=dict(family="Space Mono", size=11, color=CLR_TEXT),
        ),
        yaxis=dict(
            title=dict(text=home, font=dict(family="Space Grotesk", size=12,
                                            color=CLR_MUTED)),
            tickvals=list(range(6)),
            tickfont=dict(family="Space Mono", size=11, color=CLR_TEXT),
            autorange="reversed",
        ),
    )
    return fig


# ---------------------------------------------------------------------------
# Team stat display helper
# ---------------------------------------------------------------------------

def render_team_profile(stats: me.TeamStats, team_name: str,
                        accent_color: str) -> None:
    rec = me.get_team_stats(stats, team_name)
    is_fallback = (rec.name == "__global__")

    if is_fallback:
        st.markdown(
            f'<div class="fallback-warning">⚠ No WC history found for '
            f'<b>{team_name}</b> — using global average</div>',
            unsafe_allow_html=True,
        )

    st.markdown(f"""
    <div class="stat-grid">
      <div class="stat-pill">Atk <span>{rec.attack_strength:.2f}×</span></div>
      <div class="stat-pill">Def <span>{rec.defense_strength:.2f}×</span></div>
      <div class="stat-pill">Avg scored <span>{rec.goals_scored:.2f}</span></div>
      <div class="stat-pill">Avg conceded <span>{rec.goals_conceded:.2f}</span></div>
      <div class="stat-pill">W% <span>{rec.win_rate:.0%}</span></div>
      <div class="stat-pill">D% <span>{rec.draw_rate:.0%}</span></div>
      <div class="stat-pill">L% <span>{rec.loss_rate:.0%}</span></div>
      <div class="stat-pill">GP <span>{rec.matches}</span></div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():

    # ── Masthead ────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="masthead">
      <div class="masthead-title">World Cup <span class="masthead-accent">2026</span></div>
    </div>
    <div class="masthead-sub">Match probability engine  ·  Poisson model  ·  WC 1930–2022 data</div>
    """, unsafe_allow_html=True)

    # ── Load data ───────────────────────────────────────────────────────────
    with st.spinner("Loading team stats…"):
        try:
            stats = load_stats()
        except FileNotFoundError:
            st.error(
                f"**Database not found:** `{DB_PATH}`\n\n"
                "Run `py ingest_api.py --mode full` and `py ingest_csv.py` first."
            )
            st.stop()
        except ValueError as e:
            st.error(f"**Stats error:** {e}")
            st.stop()

    fixtures    = load_fixtures()
    all_teams   = me.available_teams(stats)
    has_fixtures = bool(fixtures)

    # ── Fixture / team selection ─────────────────────────────────────────────
    st.markdown('<div class="section-label">Select match</div>', unsafe_allow_html=True)

    if has_fixtures:
        # Build display labels for the selectbox
        def fixture_label(f: dict) -> str:
            h = f["home_team_name"] or "TBD"
            a = f["away_team_name"] or "TBD"
            date_str = _format_date(f["utc_date"])
            return f"{h}  vs  {a}    [{date_str}]"

        fixture_options  = fixtures
        fixture_labels   = [fixture_label(f) for f in fixture_options]

        selected_label = st.selectbox(
            "Upcoming WC 2026 fixture",
            options=fixture_labels,
            index=0,
            label_visibility="collapsed",
        )
        selected_idx  = fixture_labels.index(selected_label)
        selected_fix  = fixture_options[selected_idx]

        home_team = selected_fix["home_team_name"] or "TBD"
        away_team = selected_fix["away_team_name"] or "TBD"
        fix_date  = _format_date(selected_fix["utc_date"])
        fix_stage = _format_stage(selected_fix.get("stage"),
                                  selected_fix.get("group"))

        # Fixture card
        st.markdown(f"""
        <div class="fixture-card">
          <div class="fixture-date">{fix_date}</div>
          <div class="fixture-matchup">
            {home_team}
            <span class="fixture-vs">vs</span>
            {away_team}
          </div>
          {'<div class="fixture-stage">' + fix_stage + '</div>' if fix_stage else ''}
        </div>
        """, unsafe_allow_html=True)

    else:
        # Fallback: manual team picker (no upcoming_fixtures table yet)
        st.info(
            "No 2026 fixture schedule found in the database. "
            "Pick teams manually below, or run `py ingest_api.py --mode upcoming` "
            "to load the schedule."
        )
        col_h, col_vs, col_a = st.columns([5, 1, 5])
        with col_h:
            home_team = st.selectbox(
                "Home team", all_teams,
                index=all_teams.index("Argentina") if "Argentina" in all_teams else 0,
                key="manual_home",
            )
        with col_vs:
            st.markdown(
                "<div style='text-align:center;padding-top:1.8rem;"
                f"color:{CLR_MUTED};font-size:1.1rem'>vs</div>",
                unsafe_allow_html=True,
            )
        with col_a:
            away_default = (all_teams.index("Brazil")
                            if "Brazil" in all_teams else 1)
            away_team = st.selectbox(
                "Away team", all_teams,
                index=away_default,
                key="manual_away",
            )
        fix_date  = ""
        fix_stage = ""

    # ── Guard: same team selected ────────────────────────────────────────────
    if home_team == away_team:
        st.warning("Select two different teams.")
        st.stop()

    # ── Prediction ──────────────────────────────────────────────────────────
    result = me.predict_match(stats, home_team, away_team)

    # ── Outcome probability bar ──────────────────────────────────────────────
    st.markdown('<div class="section-label">Win probability</div>',
                unsafe_allow_html=True)
    st.plotly_chart(make_outcome_bar(result),
                    use_container_width=True, config={"displayModeBar": False})

    # ── Metric cards ─────────────────────────────────────────────────────────
    st.markdown("""
    <div class="metric-row">
      <div class="metric-card home">
        <div class="metric-label">Home win</div>
        <div class="metric-team">{home}</div>
        <div class="metric-pct">{hw}</div>
        <div class="metric-xg">xG {lh:.2f}</div>
      </div>
      <div class="metric-card draw">
        <div class="metric-label">Draw</div>
        <div class="metric-team">&nbsp;</div>
        <div class="metric-pct">{d}</div>
        <div class="metric-xg">&nbsp;</div>
      </div>
      <div class="metric-card away">
        <div class="metric-label">Away win</div>
        <div class="metric-team">{away}</div>
        <div class="metric-pct">{aw}</div>
        <div class="metric-xg">xG {la:.2f}</div>
      </div>
    </div>
    """.format(
        home=result.home_team,
        away=result.away_team,
        hw=f"{result.home_win_prob:.0%}",
        d=f"{result.draw_prob:.0%}",
        aw=f"{result.away_win_prob:.0%}",
        lh=result.lambda_home,
        la=result.lambda_away,
    ), unsafe_allow_html=True)

    # ── Team profiles ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Team profiles</div>',
                unsafe_allow_html=True)
    col_hp, col_ap = st.columns(2)
    with col_hp:
        st.markdown(
            f"<div style='font-size:0.9rem;font-weight:600;"
            f"color:{CLR_HOME};margin-bottom:6px'>{result.home_team}</div>",
            unsafe_allow_html=True,
        )
        render_team_profile(stats, home_team, CLR_HOME)
    with col_ap:
        st.markdown(
            f"<div style='font-size:0.9rem;font-weight:600;"
            f"color:{CLR_MUTED};margin-bottom:6px'>{result.away_team}</div>",
            unsafe_allow_html=True,
        )
        render_team_profile(stats, away_team, CLR_AWAY)

    # ── Scoreline charts ──────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Most likely scorelines</div>',
                unsafe_allow_html=True)

    tab_bar, tab_heat = st.tabs(["Top scorelines", "Goal matrix"])

    with tab_bar:
        n_scorelines = st.slider(
            "Number of scorelines to show",
            min_value=5, max_value=15, value=8, step=1,
            label_visibility="collapsed",
        )
        st.plotly_chart(
            make_scoreline_chart(result, top_n=n_scorelines),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        # Legend
        st.markdown(
            f"<div style='display:flex;gap:16px;margin-top:4px'>"
            f"<span style='font-size:0.72rem;color:{CLR_HOME};"
            f"font-family:monospace'>■ {result.home_team} win</span>"
            f"<span style='font-size:0.72rem;color:{CLR_DRAW};"
            f"font-family:monospace'>■ Draw</span>"
            f"<span style='font-size:0.72rem;color:{CLR_AWAY};"
            f"font-family:monospace'>■ {result.away_team} win</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with tab_heat:
        st.markdown(
            "<div style='font-size:0.78rem;color:" + CLR_MUTED + ";margin-bottom:8px'>"
            "Cell shows the probability of each exact scoreline (0–5 goals each side). "
            "Brighter = more likely.</div>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            make_scoreline_heatmap(result),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    # ── Model details expander ────────────────────────────────────────────────
    with st.expander("Model details", expanded=False):
        st.markdown(f"""
**How the model works**

This is a Poisson distribution model trained on **{len(me.available_teams(stats))} teams**
across **WC 1930–2022** (900+ matches). It uses exponential recency weighting —
WC 2022 data contributes ~3× more signal than WC 1990.

For each team, the model estimates:
- **Attack strength** = team's avg goals scored ÷ global average goals scored
- **Defense strength** = team's avg goals conceded ÷ global average goals conceded

Expected goals for this match:
- **{result.home_team} xG** = {result.lambda_home:.3f} &nbsp;
  (global avg × {result.home_team} attack × {result.away_team} defense)
- **{result.away_team} xG** = {result.lambda_away:.3f} &nbsp;
  (global avg × {result.away_team} attack × {result.home_team} defense)

The full scoreline matrix (P(home=i) × P(away=j)) is computed via `scipy.stats.poisson.pmf`,
then summed across all cells where home > away (win), home = away (draw), home < away (loss).

No home advantage is applied — all World Cup matches are at neutral venues.
Extra-time and penalty results are excluded from training data.

**Known limitations:** Draws are systematically underestimated (base Poisson treats goals as
independent; real teams lower tempo when ahead). The 80–90% confidence bucket shows
overconfidence on large mismatches (e.g. Argentina vs Saudi Arabia). Dixon-Coles correction
is planned for v2.
        """)

    # ── Footer ───────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="footer">WC 2026 Predictor  ·  '
        f'Poisson model  ·  {len(me.available_teams(stats))} teams  ·  '
        f'Data: WC 1930–2022</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()