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

import streamlit as st

from assets.css import inject_css
from services import bracket_service
from components import (
    hero,
    sidebar,
    bracket,
    match_card,
    prediction_breakdown,
    team_card,
    charts,
    model_info,
    layout,
)

from services import (
    prediction_service,
    fixture_service,
)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="WC 2026 Predictor",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

inject_css()

# ------------------------------------------------------------------
# Session State
# ------------------------------------------------------------------

if "selected_match_id" not in st.session_state:
    st.session_state.selected_match_id = None

def main():

    
    st.write(f"Secret detected: {st.secrets.get('FOOTBALL_DATA_API_KEY') is not None}")
    # ------------------------------------------------------------------
    # Hero
    # ------------------------------------------------------------------

    hero.render()
    
    # ------------------------------------------------------------------
    # Sidebar / Model Selection
    # ------------------------------------------------------------------
    
    selected_model, model_metadata = sidebar.render()

    # ------------------------------------------------------------------
    # Load statistics
    # ------------------------------------------------------------------

    stats = prediction_service.load_team_stats(selected_model)

    fixtures = fixture_service.load_fixtures()
    bracket_data = bracket_service.build_bracket(fixtures)
    all_teams = prediction_service.available_teams(stats)
    team_count = len(all_teams)

    # ------------------------------------------------------------------
    # Tournament Bracket
    # ------------------------------------------------------------------
    if bracket_data:
        bracket.render(bracket_data)
    # ------------------------------------------------------------------
    # Match Selection
    # ------------------------------------------------------------------
    
    (
        home_team,
        away_team,
        fixture_date,
        fixture_stage,
    ) = match_card.render_match_selector(
        fixtures,
        all_teams,
    )
    
    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    result = prediction_service.predict_match(
        stats,
        home_team,
        away_team,
    )

    # ------------------------------------------------------------------
    # Prediction Summary
    # ------------------------------------------------------------------
    st.markdown("<div id='prediction-section'></div>", unsafe_allow_html=True)
    prediction_breakdown.render(result)

    # ------------------------------------------------------------------
    # Team Profiles
    # ------------------------------------------------------------------

    team_card.render(
        stats,
        result,
    )

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    charts.render(result)

    # ------------------------------------------------------------------
    # Model Information
    # ------------------------------------------------------------------

    model_info.render(
        model_metadata,
        result,
        team_count,
    )

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    layout.render_footer(
        model_metadata,
        team_count,
    )


if __name__ == "__main__":
    main()