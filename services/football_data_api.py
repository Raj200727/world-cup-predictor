"""
football_data_api.py

Wrapper around the Football Data API.
"""

from __future__ import annotations

import os
import requests

from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.football-data.org/v4"

API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")

HEADERS = {
    "X-Auth-Token": API_KEY
}

session = requests.Session()
session.headers.update(HEADERS)

def get_world_cup_matches() -> list[dict]:
    """
    Returns every FIFA World Cup match.
    """

    response = session.get(
        f"{BASE_URL}/competitions/WC/matches",
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    return data["matches"]

def get_match(match_id: int) -> dict:
    """
    Returns a single match.
    """

    response = session.get(
        f"{BASE_URL}/matches/{match_id}",
        timeout=20,
    )

    response.raise_for_status()

    return response.json()

def get_team(team_id: int) -> dict:
    """
    Returns team information.
    """

    response = session.get(
        f"{BASE_URL}/teams/{team_id}",
        timeout=20,
    )

    response.raise_for_status()

    return response.json()

if __name__ == "__main__":

    matches = get_world_cup_matches()

    print(f"Loaded {len(matches)} matches.")