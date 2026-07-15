from __future__ import annotations

import os
import requests
import streamlit as st

# Try to load local .env file (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = "https://api.football-data.org/v4"

def get_api_key():
    # 1. Try Streamlit Cloud Production Secrets first
    if "FOOTBALL_DATA_API_KEY" in st.secrets:
        return st.secrets["FOOTBALL_DATA_API_KEY"]
    
    # 2. Fall back to local environment variables
    return os.getenv("FOOTBALL_DATA_API_KEY")

API_KEY = get_api_key()

HEADERS = {
    "X-Auth-Token": API_KEY
}

session = requests.Session()
if API_KEY:
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