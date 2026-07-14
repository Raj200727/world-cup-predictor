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
    size: str = "normal"
) -> None:

    html = f"""
<div class="bracket-card bracket-{size}">

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

def _svg_bridge_final_to_semi(sf1_won: bool = False, sf2_won: bool = False) -> str:
    """
    SVG connector dropping from Final to Semifinals, stretched to touch cards.
    """
    s1_cls = "winner-path" if sf1_won else ""
    s2_cls = "winner-path" if sf2_won else ""
    
    return f"""
    <div class="bracket-bridge">
    <svg viewBox="0 0 1000 100" preserveAspectRatio="none" style="width: 100%; height: 100px; overflow: visible;">
        <path class="connector-line {s1_cls}" d="M 500,0 L 500,50 L 228,50 L 228,100" fill="none" stroke="#263238" stroke-width="3" />
        <path class="connector-line {s2_cls}" d="M 500,0 L 500,50 L 772,50 L 772,100" fill="none" stroke="#263238" stroke-width="3" />
    </svg>
    </div>
    """

def _svg_bridge_semi_to_qf(qf1_won: bool = False, qf2_won: bool = False, qf3_won: bool = False, qf4_won: bool = False) -> str:
    """
    SVG connectors dropping from Semis to Quarterfinals, stretched to touch cards.
    """
    q1_cls = "winner-path" if qf1_won else ""
    q2_cls = "winner-path" if qf2_won else ""
    q3_cls = "winner-path" if qf3_won else ""
    q4_cls = "winner-path" if qf4_won else ""

    return f"""
    <div class="bracket-bridge">
    <svg viewBox="0 0 1000 100" preserveAspectRatio="none" style="width: 100%; height: 100px; overflow: visible;">
        <path class="connector-line {q1_cls}" d="M 228,0 L 228,50 L 109,50 L 109,100" fill="none" stroke="#263238" stroke-width="3" />
        <path class="connector-line {q2_cls}" d="M 228,0 L 228,50 L 348,50 L 348,100" fill="none" stroke="#263238" stroke-width="3" />
        <path class="connector-line {q3_cls}" d="M 772,0 L 772,50 L 652,50 L 652,100" fill="none" stroke="#263238" stroke-width="3" />
        <path class="connector-line {q4_cls}" d="M 772,0 L 772,50 L 891,50 L 891,100" fill="none" stroke="#263238" stroke-width="3" />
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
    st.markdown("""
        <style>
        div[data-testid="stVerticalBlock"] > div:has(div.bracket-bridge) {
            margin-top: -10px !important;
            margin-bottom: -10px !important;
        }
        </style>
    """, unsafe_allow_html=True)
    with bracket_container:
        st.markdown(
    '<div class="bracket-final-row">',
    unsafe_allow_html=True,
)
        # ── 1. FINAL ROW ──
        _, final_col, _ = st.columns([1.55, 1.5, 1.55])
        with final_col:
            if final_match:
                render_match(final_match, "final")
            elif left_sf_winner and right_sf_winner:
                render_placeholder(
                    f'{FLAGS.get(left_sf_winner,"🏳")} {left_sf_winner}',
                    f'{FLAGS.get(right_sf_winner,"🏳")} {right_sf_winner}',
                    size="final"
                )
            else:
                render_placeholder("🏆 TBD", size="final")
        st.markdown(
            _svg_bridge_final_to_semi(
                sf1_won=bool(left_sf_winner), 
                sf2_won=bool(right_sf_winner)
            ), 
            unsafe_allow_html=True
        )
        st.markdown(
    '<div class="bracket-semi-row">',
    unsafe_allow_html=True,
)
        # ── 2. SEMI FINALS ROW ──
        sf_left_col, _, sf_right_col = st.columns([2.1, 0.4, 2.1])
        with sf_left_col:
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
            if right_semifinal:
                render_match(right_semifinal, "semi")

            elif left_qf2_winner and right_qf2_winner:

                render_placeholder(
        f'{FLAGS.get(left_qf2_winner,"🏳")} {left_qf2_winner}',
        f'{FLAGS.get(right_qf2_winner,"🏳")} {right_qf2_winner}',
    )

            else:

                render_placeholder("⚽ TBD")
        st.markdown(
            _svg_bridge_semi_to_qf(
                qf1_won=bool(left_qf_winner),
                qf2_won=bool(right_qf_winner),
                qf3_won=bool(left_qf2_winner),
                qf4_won=bool(right_qf2_winner)
            ), 
            unsafe_allow_html=True
        )
        st.markdown(
    '<div class="bracket-quarter-row">',
    unsafe_allow_html=True,
)
        qf1, _, qf2, _, qf3, _, qf4 = st.columns([1, 0.1, 1, 0.4, 1, 0.1, 1])
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
    "</div>",
    unsafe_allow_html=True,
)
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