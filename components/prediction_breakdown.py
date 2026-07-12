"""
prediction_breakdown.py

Renders the primary prediction summary cards.
"""

from __future__ import annotations

import streamlit as st
import math_engine as me

def render(
    result: me.MatchResult,
) -> None:
    """
    Render the prediction summary.

    Parameters
    ----------
    result
        PredictionResult returned by math_engine.predict_match().
    """
    st.markdown(
        f"""
<div class="prediction-header">

<div class="prediction-title">
{result.home_team} vs {result.away_team}
</div>

<div class="prediction-subtitle">
Prediction Summary
</div>

</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="metric-row">

<div class="metric-card home">
<div class="metric-label">Win Probability</div>
<div class="metric-team">{home}</div>
<div class="metric-pct">{home_win}</div>
<div class="metric-xg">
Expected Goals
<br>
<strong>{home_xg}</strong>
</div>
</div>

<div class="metric-card draw">
<div class="metric-label">Draw</div>
<div class="metric-team">&nbsp;</div>
<div class="metric-pct">{draw}</div>
<div class="metric-xg">&nbsp;</div>
</div>

<div class="metric-card away">
<div class="metric-label">Win Probability</div>
<div class="metric-team">{away}</div>
<div class="metric-pct">{away_win}</div>
<div class="metric-xg">
Expected Goals
<br>
<strong>{away_xg}</strong>
</div>
</div>

</div>
        """.format(
            home=result.home_team,
            away=result.away_team,
            home_win=f"{result.home_win_prob:.0%}",
            draw=f"{result.draw_prob:.0%}",
            away_win=f"{result.away_win_prob:.0%}",
            home_xg=f"{result.lambda_home:.2f}",
            away_xg=f"{result.lambda_away:.2f}",
        ),
        unsafe_allow_html=True,
    )

    favorite = max(
        [
            (result.home_team, result.home_win_prob),
            ("Draw", result.draw_prob),
            (result.away_team, result.away_win_prob),
        ],
        key=lambda x: x[1],
    )
    st.markdown(
        f"""
<div class="prediction-callout">

Prediction

<strong>{favorite[0]}</strong>

{favorite[1]:.0%} confidence

</div>
""",
        unsafe_allow_html=True,
    )