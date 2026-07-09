"""
match_card.py

Handles fixture selection and renders the selected match card.
"""

from __future__ import annotations


import streamlit as st

from components.layout import section
from components.utils import _format_date, _format_stage
from assets.theme import CLR_MUTED


def _fixture_label(fixture: dict) -> str:
    """Create the selectbox label for a fixture."""

    home = fixture["home_team_name"] or "TBD"
    away = fixture["away_team_name"] or "TBD"

    return (
        f"{home}  vs  {away}"
        f"    [{_format_date(fixture['utc_date'])}]"
    )


def render_match_selector(
    fixtures: list[dict],
    all_teams: list[str],
) -> tuple[str, str, str, str]:
    """
    Render fixture selector.

    Returns
    -------
    home_team
    away_team
    fixture_date
    fixture_stage
    """

    
    section("Select Match")

    if fixtures:

        labels = [_fixture_label(f) for f in fixtures]

        selected_label = st.selectbox(
            "Upcoming WC 2026 fixture",
            options=labels,
            index=0,
            label_visibility="collapsed",
        )

        selected_fixture = fixtures[labels.index(selected_label)]

        home_team = selected_fixture["home_team_name"] or "TBD"
        away_team = selected_fixture["away_team_name"] or "TBD"

        fixture_date = _format_date(selected_fixture["utc_date"])

        fixture_stage = _format_stage(
            selected_fixture.get("stage"),
            selected_fixture.get("group"),
        )
        
        html = f"""
        <div class="fixture-card">
        <div class="fixture-date">
        {fixture_date}
        </div>

        <div class="fixture-matchup">
        {home_team}
        <span class="fixture-vs">vs</span>
        {away_team}
        </div>
        """

        if fixture_stage:
            html += f"""
        <div class="fixture-stage">
        {fixture_stage}
        </div>
        """

        html += """
        </div>
        """

        st.markdown(html, unsafe_allow_html=True)

    else:

        st.info(
            "No 2026 fixtures found in the database. "
            "Select teams manually."
        )

        col_home, col_vs, col_away = st.columns([5, 1, 5])

        with col_home:

            home_team = st.selectbox(
                "Home Team",
                all_teams,
                index=(
                    all_teams.index("Argentina")
                    if "Argentina" in all_teams
                    else 0
                ),
            )

        with col_vs:

            st.markdown(
                (
                    "<div style='text-align:center;"
                    "padding-top:1.8rem;"
                    f"color:{CLR_MUTED};"
                    "font-size:1.1rem'>"
                    "vs"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

        with col_away:

            away_team = st.selectbox(
                "Away Team",
                all_teams,
                index=(
                    all_teams.index("Brazil")
                    if "Brazil" in all_teams
                    else 1
                ),
            )

        fixture_date = ""
        fixture_stage = ""

    if home_team == away_team:

        st.warning("Select two different teams.")

        st.stop()
    
    

    return (
        home_team,
        away_team,
        fixture_date,
        fixture_stage,
    )