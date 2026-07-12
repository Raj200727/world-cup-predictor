"""
bracket.py

Quarter Final bracket component.
"""

from __future__ import annotations

import streamlit as st
from datetime import datetime
from components.clickable_card import set_selected_match
from assets.flags import FLAGS

def render_match(match: dict) -> None:
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

    card_class = "bracket-card"

    if selected:
        card_class += " bracket-card-selected"
    if played and home_score is not None and away_score is not None:
        home_display = f"{home_flag} {match['home_team_name']} <span class='score'>{home_score}</span>"
        away_display = f"{away_flag} {match['away_team_name']} <span class='score'>{away_score}</span>"
    else:
        home_display = f"{home_flag} {match['home_team_name']}"
        away_display = f"{away_flag} {match['away_team_name']}"
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
    st.markdown(
        '<div class="bracket-title">Tournament Bracket</div>',
        unsafe_allow_html=True,
    )

    left_matches = quarterfinals[:2]
    right_matches = quarterfinals[2:]

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
    
    # Five columns: QF | left SF | Final | right SF | QF
    # Ratios are symmetric around the center Final column so the bracket
    # mirrors correctly. The spacer-large div and top_sf/bottom_sf container
    # pattern are no longer needed — each SF now owns its own column.
    col1, col2, col3, col4, col5 = st.columns(
        [4.5, 2.4, 1.3, 2.4, 4.5],
        vertical_alignment="center",
    )


    with col1:
        for match in left_matches:
            render_match(match)

    with col2:

        st.markdown(
            '<div class="bracket-stage">Semi Finals</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="bracket-connector-left"></div>',
            unsafe_allow_html=True,
        )
        if left_semifinal:
            render_match(left_semifinal)

        elif left_qf_winner and right_qf_winner:

            render_placeholder(
    f'{FLAGS.get(left_qf_winner,"🏳")} {left_qf_winner}',
    f'{FLAGS.get(right_qf_winner,"🏳")} {right_qf_winner}',
)

        else:

            render_placeholder("TBD")

    with col4:

        st.markdown(
            '<div class="bracket-stage">Semi Finals</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="bracket-connector-right"></div>',
            unsafe_allow_html=True,
        )
        if right_semifinal:
            render_match(right_semifinal)

        elif left_qf2_winner and right_qf2_winner:

            render_placeholder(
    f'{FLAGS.get(left_qf2_winner,"🏳")} {left_qf2_winner}',
    f'{FLAGS.get(right_qf2_winner,"🏳")} {right_qf2_winner}',
)

        else:

            render_placeholder("TBD")
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
    with col3:

        st.markdown(
            '<div class="bracket-stage">Final</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="bracket-spacer-final"></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="bracket-connector-final"></div>',
            unsafe_allow_html=True,
        )
        if final_match:
            render_match(final_match)

        elif left_sf_winner and right_sf_winner:

            render_placeholder(
    f'{FLAGS.get(left_sf_winner,"🏳")} {left_sf_winner}',
    f'{FLAGS.get(right_sf_winner,"🏳")} {right_sf_winner}',
)
        else:
            render_placeholder("🏆 TBD")
   
    with col5:
        for match in right_matches:
            render_match(match)