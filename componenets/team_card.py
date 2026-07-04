"""
team_card.py

Renders team comparison cards.
"""

from __future__ import annotations

import streamlit as st

import math_engine as me

from assets.theme import (
    CLR_HOME,
    CLR_AWAY,
    CLR_MUTED,
)


def render_team_profile(
    stats: me.TeamStats,
    team_name: str,
) -> None:
    """
    Render a single team's statistics.
    """

    rec = me.get_team_stats(stats, team_name)

    is_fallback = rec.name == "__global__"

    if is_fallback:

        st.markdown(
            (
                f'<div class="fallback-warning">'
                f'⚠ No World Cup history found for '
                f'<b>{team_name}</b> — using global average'
                f'</div>'
            ),
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="stat-grid">

            <div class="stat-pill">
                Atk <span>{rec.attack_strength:.2f}×</span>
            </div>

            <div class="stat-pill">
                Def <span>{rec.defense_strength:.2f}×</span>
            </div>

            <div class="stat-pill">
                Avg scored <span>{rec.goals_scored:.2f}</span>
            </div>

            <div class="stat-pill">
                Avg conceded <span>{rec.goals_conceded:.2f}</span>
            </div>

            <div class="stat-pill">
                W% <span>{rec.win_rate:.0%}</span>
            </div>

            <div class="stat-pill">
                D% <span>{rec.draw_rate:.0%}</span>
            </div>

            <div class="stat-pill">
                L% <span>{rec.loss_rate:.0%}</span>
            </div>

            <div class="stat-pill">
                GP <span>{rec.matches}</span>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


def render(
    stats: me.TeamStats,
    result,
) -> None:
    """
    Render both team profile cards.
    """

    st.markdown(
        '<div class="section-label">Team Profiles</div>',
        unsafe_allow_html=True,
    )

    home_col, away_col = st.columns(2)

    with home_col:

        st.markdown(
            (
                f"<div style='font-size:0.9rem;"
                f"font-weight:600;"
                f"color:{CLR_HOME};"
                f"margin-bottom:6px'>"
                f"{result.home_team}"
                f"</div>"
            ),
            unsafe_allow_html=True,
        )

        render_team_profile(
            stats,
            result.home_team,
        )

    with away_col:

        st.markdown(
            (
                f"<div style='font-size:0.9rem;"
                f"font-weight:600;"
                f"color:{CLR_AWAY};"
                f"margin-bottom:6px'>"
                f"{result.away_team}"
                f"</div>"
            ),
            unsafe_allow_html=True,
        )

        render_team_profile(
            stats,
            result.away_team,
        )