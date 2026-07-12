"""
fixture_service.py

Loads World Cup fixtures from predictor.db.

This module is responsible only for database access.
No Streamlit rendering or UI logic belongs here.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from services.football_data_api import get_world_cup_matches

DB_PATH = Path("predictor.db")

UPCOMING_SEASON = 2026

def load_api_fixtures() -> list[dict]:
    """
    Loads and normalizes World Cup fixtures.
    """

    matches = get_world_cup_matches()
    
    return [normalize_match(match)for match in matches]

def load_db_fixtures() -> list[dict]:
    """
    Load World Cup fixtures for the configured tournament.

    Returns
    -------
    list[dict]
        Fixtures sorted by kickoff time.
    """

    try:

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                match_id,
                utc_date,
                home_team_name,
                away_team_name,
                stage,
                "group",
                status
            FROM upcoming_fixtures
            WHERE competition = 'WC'
              AND season = ?
            ORDER BY utc_date
            """,
            (UPCOMING_SEASON,),
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    except sqlite3.Error:

        return []


def has_fixtures() -> bool:
    """
    Return True if fixtures exist.
    """

    return len(load_fixtures()) > 0


def get_fixture(match_id: int) -> dict | None:
    """
    Return a single fixture by match id.
    """

    fixtures = load_fixtures()

    for fixture in fixtures:

        if fixture["match_id"] == match_id:

            return fixture

    return None

def load_stage(stage_name: str) -> list[dict]:

    fixtures = load_fixtures()

    return [
        f
        for f in fixtures
        if (f.get("stage") or "").lower() == stage_name.lower()
    ]

def normalize_match(match: dict) -> dict:
    """
    Converts a Football Data API match into the
    application's internal fixture format.
    """
    stage_map = {
    "LAST_32": "ROUND_OF_32",
    "LAST_16": "ROUND_OF_16",
    "QUARTER_FINALS": "QUARTERFINAL",
    "SEMI_FINALS": "SEMIFINAL",
    "FINAL": "FINAL",
    "THIRD_PLACE": "THIRD_PLACE",
    }

    stage = stage_map.get(
        match.get("stage"),
        match.get("stage"),
    )
    return {
        "match_id": match["id"],

        "utc_date": match["utcDate"],

        "status": match["status"],

        "stage": stage,

        "group": None,

        "home_team_name":
    (
        match["homeTeam"]["name"]
        if match.get("homeTeam")
        and match["homeTeam"].get("name")
        else "TBD"
    ),

        "away_team_name":
(
    match["awayTeam"]["name"]
    if match.get("awayTeam")
    and match["awayTeam"].get("name")
    else "TBD"
),

        "home_score":
            match["score"]["fullTime"]["home"],

        "away_score":
            match["score"]["fullTime"]["away"],
    }    
def load_fixtures() -> list[dict]:
    """
    Returns fixtures from the API.
    Falls back to the database if the API fails.
    """

    try:
        return load_api_fixtures()

    except Exception:
        return load_db_fixtures()