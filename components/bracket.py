"""
bracket.py

Quarter Final bracket component.
"""

from __future__ import annotations

import streamlit as st
from datetime import datetime
from components.clickable_card import set_selected_match
from assets.flags import FLAGS

def render_match(
    match: dict,
    size: str = "normal",
) -> None:
    winner = get_winner(match)
    played = match["status"] == "FINISHED"
    selected = (st.session_state.selected_match_id == match["match_id"])
    home_class = "bracket-team"
    away_class = "bracket-team"

    if winner == match["home_team_name"]:
        home_class += " winner"

    if winner == match["away_team_name"]:
        away_class += " winner"

    if selected:
        home_class += " selected"
        away_class += " selected"

    
    match_time = None

    if match.get("utc_date"):
        match_time = datetime.fromisoformat(
            match["utc_date"].replace("Z", "")
        )
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    home_flag = FLAGS.get(match["home_team_name"], "🏳")
    away_flag = FLAGS.get(match["away_team_name"], "🏳")

    if played:

        status = (
            '<span class="bracket-status complete">'
            'FINAL'
            '</span>'
        )

    elif match_time:

        status = (
            f'<span class="bracket-status upcoming">'
            f'{match_time.strftime("%b %d • %I:%M %p")}'
            '</span>'
        )

    else:

        status = (
            '<span class="bracket-status upcoming">'
            'UPCOMING'
            '</span>'
        )

    card_class = f"bracket-card bracket-{size}"

    if selected:
        card_class += " bracket-card-selected"

    if played and home_score is not None and away_score is not None:

        home_display = f"""
    <div class="bracket-team-name">
        <span class="bracket-flag">{home_flag}</span>
        <span>{match['home_team_name']}</span>
    </div>

    <span class="score">{home_score}</span>
    """

        away_display = f"""
    <div class="bracket-team-name">
        <span class="bracket-flag">{away_flag}</span>
        <span>{match['away_team_name']}</span>
    </div>

    <span class="score">{away_score}</span>
    """

    else:

        home_display = f"""
    <div class="bracket-team-name">
        <span class="bracket-flag">{home_flag}</span>
        <span>{match['home_team_name']}</span>
    </div>
    """

        away_display = f"""
    <div class="bracket-team-name">
        <span class="bracket-flag">{away_flag}</span>
        <span>{match['away_team_name']}</span>
    </div>
    """
    st.markdown(
                f"""
    <div class="{card_class}">

    <div class="bracket-header">
    {status}
    </div>

    <div class="{home_class}">
    {home_display}
    </div>

    <div class="bracket-vs">
    VS
    </div>

    <div class="{away_class}">
    {away_display}
    </div>

    </div>
    """,
                unsafe_allow_html=True,
            ) 
    if st.button(
        f'{match["home_team_name"]} vs {match["away_team_name"]}',
        key=f'bracket_{match["match_id"]}',
        use_container_width=True,):
        set_selected_match(match["match_id"])
        
def render_placeholder(
    team1: str,
    team2: str | None = None,
) -> None:

    html = f"""
<div class="bracket-card">

<div class="bracket-team">
{team1}
</div>
"""

    if team2:

        html += f"""
<div class="bracket-vs">
VS
</div>

<div class="bracket-team">
{team2}
</div>
"""

    html += """
</div>
"""

    st.markdown(
        html,
        unsafe_allow_html=True,
    )

def get_winner(match: dict) -> str | None:
    """
    Returns the winner of a completed match.
    """

    if match["status"] != "FINISHED":
        return None

    home = match.get("home_score")
    away = match.get("away_score")

    if home is None or away is None:
        return None

    if home > away:
        return match["home_team_name"]

    if away > home:
        return match["away_team_name"]

    return None
def _svg_bridge_final_to_semi() -> str:
    """
    SVG connector between the Final row (top) and the Semi-Final row (below).

    Coordinate system: viewBox "0 0 1000 90"
      x=0 is left edge of the container, x=1000 is right edge.
      y=0 is the bottom of the Final row, y=90 is the top of the Semi row.

    Column positions (derived from st.columns proportions):
      Final card center:  x = 500  (50% — it's in a [1.5, 6, 1.5] layout, center col)
      Left SF center:     x = 222  (22.2% — [1, 0.25, 1] layout, left col center)
      Right SF center:    x = 778  (77.8% — [1, 0.25, 1] layout, right col center)

    Each path is an orthogonal elbow: straight down, then horizontal.
    The horizontal joint sits at y=45 (midpoint of the 90px gap).
    """
    return """
<div class="bracket-bridge">
<svg viewBox="0 0 1000 90" preserveAspectRatio="none"
     xmlns="http://www.w3.org/2000/svg">

  <!-- Final center → Left SF: down from 500, elbow at y=45, across to 222, then down -->
  <path class="connector-path accent"
        d="M 500,0 L 500,45 L 222,45 L 222,90" />

  <!-- Final center → Right SF: down from 500, elbow at y=45, across to 778, then down -->
  <path class="connector-path accent"
        d="M 500,0 L 500,45 L 778,45 L 778,90" />

</svg>
</div>
"""


def _svg_bridge_final_to_semi() -> str:
    # Accent gold lines for final stages
    return """
    <div style="width: 100%; height: 50px; margin: -15px 0;">
        <svg viewBox="0 0 1000 60" preserveAspectRatio="none" style="width: 100%; height: 100%; display: block; overflow: visible;">
            <path d="M 500,0 L 500,30 L 222,30 L 222,60" fill="none" stroke="#D4AF37" stroke-width="3" stroke-opacity="0.6" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M 500,0 L 500,30 L 778,30 L 778,60" fill="none" stroke="#D4AF37" stroke-width="3" stroke-opacity="0.6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
    </div>
    """

def _svg_bridge_semi_to_qf() -> str:
    # Set margin-bottom to a negative number to pull the next row UP
    return """
    <div style="width: 100%; height: 50px; margin: -20px 0 -40px 0; position: relative; z-index: 5;">
        <svg viewBox="0 0 1000 50" preserveAspectRatio="none" style="width: 100%; height: 100%; display: block; overflow: visible;">
            <path d="M 222,0 L 222,25 L 110,25 L 110,50" fill="none" stroke="#9CA3AF" stroke-width="3" stroke-dasharray="6,6" />
            <path d="M 222,0 L 222,25 L 370,25 L 370,50" fill="none" stroke="#9CA3AF" stroke-width="3" stroke-dasharray="6,6" />
            <path d="M 778,0 L 778,25 L 630,25 L 630,50" fill="none" stroke="#9CA3AF" stroke-width="3" stroke-dasharray="6,6" />
            <path d="M 778,0 L 778,25 L 890,25 L 890,50" fill="none" stroke="#9CA3AF" stroke-width="3" stroke-dasharray="6,6" />
        </svg>
    </div>
    """
def render(
    bracket: dict[str, list[dict]],
) -> None:

    quarterfinals = bracket["quarterfinals"]
    semifinals = bracket["semifinals"]
    left_semifinal = (
        semifinals[0]
        if len(semifinals) > 0
        else None
    )

    right_semifinal = (
        semifinals[1]
        if len(semifinals) > 1
        else None
    )
    final = bracket["final"]
    final_match = (
        final[0]
        if final
        else None
    )
    third_place = bracket["third_place"]

    third_place_match = (
        third_place[0]
        if third_place
        else None
    )
    st.markdown(
        '<div class="bracket-title">Tournament Bracket</div>',
        unsafe_allow_html=True,
    )

    left_qf_winner = (
        get_winner(quarterfinals[0])
        if len(quarterfinals) > 0
        else None
    )

    right_qf_winner = (
        get_winner(quarterfinals[1])
        if len(quarterfinals) > 1
        else None
    )

    left_qf2_winner = (
        get_winner(quarterfinals[2])
        if len(quarterfinals) > 2
        else None
    )

    right_qf2_winner = (
        get_winner(quarterfinals[3])
        if len(quarterfinals) > 3
        else None
    )
    left_sf_winner = (
        get_winner(semifinals[0])
        if len(semifinals) > 0
        else None
    )

    right_sf_winner = (
        get_winner(semifinals[1])
        if len(semifinals) > 1
        else None
    )

    left_sf_loser = None
    right_sf_loser = None

    if len(semifinals) > 0:

        winner = get_winner(semifinals[0])

        if winner == semifinals[0]["home_team_name"]:
            left_sf_loser = semifinals[0]["away_team_name"]

        elif winner == semifinals[0]["away_team_name"]:
            left_sf_loser = semifinals[0]["home_team_name"]

    if len(semifinals) > 1:

        winner = get_winner(semifinals[1])

        if winner == semifinals[1]["home_team_name"]:
            right_sf_loser = semifinals[1]["away_team_name"]

        elif winner == semifinals[1]["away_team_name"]:
            right_sf_loser = semifinals[1]["home_team_name"]
    bracket_container = st.container()

    with bracket_container:
        st.markdown(
    '<div class="bracket-final-row">',
    unsafe_allow_html=True,
)
        # ── 1. FINAL ROW ──
        _, final_col, _ = st.columns([1.5, 6, 1.5])
        with final_col:

            st.markdown(
                '<div class="bracket-stage">Final</div>',
                unsafe_allow_html=True,
            )

            if final_match:
                render_match(final_match, "final")

            elif left_sf_winner and right_sf_winner:

                render_placeholder(
        f'{FLAGS.get(left_sf_winner,"🏳")} {left_sf_winner}',
        f'{FLAGS.get(right_sf_winner,"🏳")} {right_sf_winner}',
    )
            else:
                render_placeholder("🏆 TBD")
        st.markdown(_svg_bridge_final_to_semi(), unsafe_allow_html=True)

        st.markdown(
    '<div class="bracket-semi-row">',
    unsafe_allow_html=True,
)
        # ── 2. SEMI FINALS ROW ──
        sf_left_col, spacer, sf_right_col = st.columns([1, 0.25, 1])
        with sf_left_col:

            st.markdown(
                '<div class="bracket-stage">Semi Finals</div>',
                unsafe_allow_html=True,
            )
            if left_semifinal:
                render_match(left_semifinal, "semi")

            elif left_qf_winner and right_qf_winner:

                render_placeholder(
        f'{FLAGS.get(left_qf_winner,"🏳")} {left_qf_winner}',
        f'{FLAGS.get(right_qf_winner,"🏳")} {right_qf_winner}',
    )

            else:

                render_placeholder("⚽ TBD")
        with sf_right_col:

            st.markdown(
                '<div class="bracket-stage">Semi Finals</div>',
                unsafe_allow_html=True,
            )
            if right_semifinal:
                render_match(right_semifinal, "semi")

            elif left_qf2_winner and right_qf2_winner:

                render_placeholder(
        f'{FLAGS.get(left_qf2_winner,"🏳")} {left_qf2_winner}',
        f'{FLAGS.get(right_qf2_winner,"🏳")} {right_qf2_winner}',
    )

            else:

                render_placeholder("⚽ TBD")
        st.markdown(_svg_bridge_semi_to_qf(), unsafe_allow_html=True)

        st.markdown(
    '<div class="bracket-quarter-row">',
    unsafe_allow_html=True,
)
        qf1, qf2, qf3, qf4 = st.columns(4)
        with qf1:

            if len(quarterfinals) > 0:

                render_match(
                    quarterfinals[0],
                    "quarter",
                )
        with qf2:

            if len(quarterfinals) > 1:

                render_match(
                    quarterfinals[1],
                    "quarter",
                )
        with qf3:

            if len(quarterfinals) > 2:

                render_match(
                    quarterfinals[2],
                    "quarter",
                )
        with qf4:

            if len(quarterfinals) > 3:

                render_match(
                    quarterfinals[3],
                    "quarter",
                )
        st.markdown(
    "<div style='height:50px'></div>",
    unsafe_allow_html=True,
)
        st.markdown(
    "</div>",
    unsafe_allow_html=True,
)
        st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
        st.markdown(
    '<div class="bracket-third-row">',
    unsafe_allow_html=True,
)
        # ── 4. THIRD PLACE ROW ──
        _, third_col, _ = st.columns([2, 5, 2])

        with third_col:

            st.markdown(
                '<div class="bracket-stage">Third Place Match</div>',
                unsafe_allow_html=True,
            )

            if third_place_match:

                render_match(
                    third_place_match,
                    "third",
                )

            elif left_sf_loser and right_sf_loser:

                render_placeholder(
                    f'{FLAGS.get(left_sf_loser,"🏳")} {left_sf_loser}',
                    f'{FLAGS.get(right_sf_loser,"🏳")} {right_sf_loser}',
                )

            else:

                render_placeholder("🥉 TBD")
        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )