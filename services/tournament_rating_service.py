"""
tournament_rating_service.py

Creates normalized live tournament ratings from
2026 World Cup statistics.
"""

from __future__ import annotations

from services.team_stats_service import build_team_stats
from functools import cache

@cache
def build_tournament_ratings() -> dict[str, dict]:
    """
    Returns normalized ratings for every team.
    """

    stats = build_team_stats()

    ratings = {}

    for team, s in stats.items():

        attack = min(s["avg_goals_for"] / 3.0, 1.0)

        defense = 1.0 - min(s["avg_goals_against"] / 3.0, 1.0)

        form = (
            s["win_percentage"] * 0.60
            + (s["points_per_game"] / 3.0) * 0.40
        )

        overall = (
            attack * 0.40
            + defense * 0.30
            + form * 0.30
        )

        ratings[team] = {
            "attack": attack,
            "defense": defense,
            "form": form,
            "overall": overall,
        }

    return ratings