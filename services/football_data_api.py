from __future__ import annotations

import os
import requests
import streamlit as st

# 1. Attempt to load local environment variables (for your laptop)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = "https://api.football-data.org/v4"

def get_api_key():
    # 2. Priority: Streamlit Cloud Secrets (Production)
    if "FOOTBALL_DATA_API_KEY" in st.secrets:
        return st.secrets["FOOTBALL_DATA_API_KEY"]
    
    # 3. Fallback: Local Environment Variable (Development)
    return os.getenv("FOOTBALL_DATA_API_KEY")

API_KEY = get_api_key()

# 4. Create session only if key exists, otherwise let it fail gracefully later
session = requests.Session()
if API_KEY:
    session.headers.update({"X-Auth-Token": API_KEY})

def get_world_cup_matches() -> list[dict]:
    if not API_KEY:
        st.warning("API Key not found. Please check Streamlit Secrets.")
        return []

    try:
        response = session.get(f"{BASE_URL}/competitions/WC/matches", timeout=10)
        response.raise_for_status()
        return response.json().get("matches", [])
    except Exception as e:
        st.error(f"API Error: {e}")
        return []

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