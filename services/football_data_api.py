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
    # 1. Try Streamlit Cloud Production Secrets first
    try:
        if "FOOTBALL_DATA_API_KEY" in st.secrets:
            return st.secrets["FOOTBALL_DATA_API_KEY"]
    except Exception:
        # If st.secrets crashes (like in GitHub Actions where no file exists), 
        # just ignore it and fall back to os.getenv
        pass
    
    # 2. Fall back to local environment variables
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
    try:
        response = session.get(
            f"{BASE_URL}/matches/{match_id}",
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching match {match_id}: {e}")
        return {} # Return empty dict instead of crashing

def get_team(team_id: int) -> dict:
    """
    Returns team information.
    """
    try:
        response = session.get(
            f"{BASE_URL}/teams/{team_id}",
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching team {team_id}: {e}")
        return {} # Return empty dict instead of crashing