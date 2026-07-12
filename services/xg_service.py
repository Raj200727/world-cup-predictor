"""
xg_service.py

Provides tournament xG statistics for every team.

Currently uses placeholder values until an xG data provider
is connected.
"""

from __future__ import annotations

def build_xg_stats() -> dict[str, dict]:
    """
    Returns

    {
        "France":
        {
            "xg_for": ...,
            "xg_against": ...,
            "xg_difference": ...
        }
    }
    """

    return {}

def get_team_xg(
    team: str,
    stats: dict[str, dict],
) -> dict:
    return stats.get(
        team,
        {
            "xg_for": 1.0,
            "xg_against": 1.0,
            "xg_difference": 0.0,
        },
    )