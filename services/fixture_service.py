"""
fixture_service.py

Loads World Cup fixtures from predictor.db.

This module is responsible only for database access.
No Streamlit rendering or UI logic belongs here.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("predictor.db")

UPCOMING_SEASON = 2026


def load_fixtures() -> list[dict]:
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