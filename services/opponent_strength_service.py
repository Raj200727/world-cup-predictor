from __future__ import annotations

from services.tournament_rating_service import (
    build_tournament_ratings,
)

def build_opponent_strength() -> dict[str, float]:
    """
    Converts normalized tournament ratings into
    opponent-strength coefficients.

    Returns
    -------
    {
        "France": 1.18,
        "Spain": 1.15,
        ...
    }
    """
    ratings = build_tournament_ratings()

    strengths = {}
    for team, rating in ratings.items():
        overall = rating["overall"]

        strength = 0.90 + overall * 0.20

        strengths[team] = round(strength, 3)

    return strengths

def get_opponent_strength(
    team: str,
    strengths: dict[str, float],
) -> float:
    return strengths.get(team, 1.0)