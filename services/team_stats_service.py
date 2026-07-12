"""
team_stats_service.py

Builds live 2026 World Cup team statistics.
"""

from __future__ import annotations

from services.fixture_service import load_api_fixtures


def build_team_stats() -> dict:
    """
    Build statistics for every team participating
    in the 2026 World Cup.
    """

    fixtures = load_api_fixtures()

    team_stats = {}

    for match in fixtures:

        for team in (
            match["home_team_name"],
            match["away_team_name"],
        ):

            if team == "TBD":
                continue

            if team not in team_stats:

                team_stats[team] = {
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "goal_difference": 0,
                    "points": 0,
                    "clean_sheets": 0,
                    "failed_to_score": 0,
                }
    for match in fixtures:

        if match["status"] != "FINISHED":
            continue

        home = match["home_team_name"]
        away = match["away_team_name"]

        home_goals = match["home_score"] or 0
        away_goals = match["away_score"] or 0

        home_stats = team_stats[home]
        away_stats = team_stats[away]

        # Matches played
        home_stats["played"] += 1
        away_stats["played"] += 1

        # Goals
        home_stats["goals_for"] += home_goals
        home_stats["goals_against"] += away_goals

        away_stats["goals_for"] += away_goals
        away_stats["goals_against"] += home_goals

        # Goal Difference
        home_stats["goal_difference"] = (
            home_stats["goals_for"]
            - home_stats["goals_against"]
        )

        away_stats["goal_difference"] = (
            away_stats["goals_for"]
            - away_stats["goals_against"]
        )

        # Clean Sheets
        if away_goals == 0:
            home_stats["clean_sheets"] += 1

        if home_goals == 0:
            away_stats["clean_sheets"] += 1

        # Failed to Score
        if home_goals == 0:
            home_stats["failed_to_score"] += 1

        if away_goals == 0:
            away_stats["failed_to_score"] += 1

        # Result
        if home_goals > away_goals:

            home_stats["wins"] += 1
            away_stats["losses"] += 1

            home_stats["points"] += 3

        elif away_goals > home_goals:

            away_stats["wins"] += 1
            home_stats["losses"] += 1

            away_stats["points"] += 3

        else:

            home_stats["draws"] += 1
            away_stats["draws"] += 1

            home_stats["points"] += 1
            away_stats["points"] += 1

    for stats in team_stats.values():

        played = stats["played"]

        if played == 0:
            continue

        stats["avg_goals_for"] = (
            stats["goals_for"] / played
        )

        stats["avg_goals_against"] = (
            stats["goals_against"] / played
        )

        stats["points_per_game"] = (
            stats["points"] / played
        )

        stats["goal_difference_per_game"] = (
            stats["goal_difference"] / played
        )

        stats["win_percentage"] = (
            stats["wins"] / played
        )
    return team_stats