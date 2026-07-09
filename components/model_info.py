from __future__ import annotations

import streamlit as st

import math_engine as me



def render(
    model_metadata: dict,
    result: me.MatchResult,
    team_count: int,
) -> None:
    """
    Render model information and methodology.
    """

    st.markdown(
        f'<div class="model-badge">'
        f'Prediction generated using '
        f'<b>{model_metadata["label"]}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Model Details", expanded=False):

        st.markdown(
            f"""
**Prediction generated using**

**{model_metadata["label"]}**

{model_metadata["description"]}

---

### How the model works

Every model variant feeds the same Poisson engine.

Attack Strength
= average goals scored ÷ tournament average

Defense Strength
= average goals conceded ÷ tournament average

Expected goals:

- **{result.home_team}**
  xG = **{result.lambda_home:.3f}**

- **{result.away_team}**
  xG = **{result.lambda_away:.3f}**

The complete scoreline probability matrix is generated using
`scipy.stats.poisson.pmf`.

Win, draw and loss probabilities are calculated by summing
the corresponding scoreline probabilities.

World Cup matches are treated as neutral venues.

Extra time and penalty shootouts are excluded.

---

Currently the selected model contains
**{team_count} teams**.
"""
        )