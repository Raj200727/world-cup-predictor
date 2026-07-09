"""
prediction_service.py

Service layer between the Streamlit UI and math_engine.py.
No Streamlit rendering should exist in this module.
"""

from __future__ import annotations

from pathlib import Path

import math_engine as me

DB_PATH = Path("predictor.db")

TRAIN_SEASONS = list(range(1930, 2023, 4))


def load_team_stats(
    model: str = me.DEFAULT_MODEL,
) -> me.TeamStats:
    """
    Load team statistics for the selected model.
    """

    return me.get_stats(
        model=model,
        db_path=DB_PATH,
        seasons=TRAIN_SEASONS,
    )


def available_teams(
    stats: me.TeamStats,
) -> list[str]:
    """
    Return every available team.
    """

    return me.available_teams(stats)


def predict_match(
    stats: me.TeamStats,
    home_team: str,
    away_team: str,
)-> me.MatchResult:
    """
    Run the prediction engine.
    """

    return me.predict_match(
        stats,
        home_team,
        away_team,
    )


def get_model_info():
    """
    Return metadata describing every prediction model.
    """

    return me.MODEL_INFO


def get_default_model() -> str:
    """
    Return the project's default prediction model.
    """

    return me.DEFAULT_MODEL