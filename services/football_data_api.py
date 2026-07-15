import os
import csv
import requests
import streamlit as st

# --- 1. LOCAL ENVIRONMENT SETUP ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = "https://api.football-data.org/v4"
CSV_PATH = "fixtures_2026.csv"

# --- 2. MAPPINGS FOR CSV FALLBACK ---
TEAM_MAPPING = {
    "France": {"tla": "FRA", "crest": "https://crests.thefootballco.com/FRA.png"},
    "Spain": {"tla": "ESP", "crest": "https://crests.thefootballco.com/ESP.png"},
    "England": {"tla": "ENG", "crest": "https://crests.thefootballco.com/ENG.png"},
    "Argentina": {"tla": "ARG", "crest": "https://crests.thefootballco.com/ARG.png"},
    "Morocco": {"tla": "MAR", "crest": "https://crests.thefootballco.com/MAR.png"},
    "Belgium": {"tla": "BEL", "crest": "https://crests.thefootballco.com/BEL.png"},
    "Norway": {"tla": "NOR", "crest": "https://crests.thefootballco.com/NOR.png"},
    "Switzerland": {"tla": "SUI", "crest": "https://crests.thefootballco.com/SUI.png"},
    "Brazil": {"tla": "BRA", "crest": "https://crests.thefootballco.com/BRA.png"},
    "Croatia": {"tla": "CRO", "crest": "https://crests.thefootballco.com/CRO.png"},
    "Portugal": {"tla": "POR", "crest": "https://crests.thefootballco.com/POR.png"},
    "Netherlands": {"tla": "NED", "crest": "https://crests.thefootballco.com/NED.png"},
    "Germany": {"tla": "GER", "crest": "https://crests.thefootballco.com/GER.png"},
    "USA": {"tla": "USA", "crest": "https://crests.thefootballco.com/USA.png"},
    "Mexico": {"tla": "MEX", "crest": "https://crests.thefootballco.com/MEX.png"},
    "Canada": {"tla": "CAN", "crest": "https://crests.thefootballco.com/CAN.png"},
    "Italy": {"tla": "ITA", "crest": "https://crests.thefootballco.com/ITA.png"},
    "Uruguay": {"tla": "URU", "crest": "https://crests.thefootballco.com/URU.png"},
}

STAGE_MAPPING = {
    "QUARTERFINAL": "QUARTER_FINALS",
    "SEMIFINAL": "SEMI_FINALS",
    "THIRD": "THIRD_PLACE",
    "FINAL": "FINAL"
}

# --- 3. HELPER FUNCTIONS ---
def _get_api_key():
    """Safely attempts to fetch the API key from Secrets or Local Env."""
    try:
        return st.secrets.get("FOOTBALL_DATA_API_KEY") or os.getenv("FOOTBALL_DATA_API_KEY")
    except Exception:
        return os.getenv("FOOTBALL_DATA_API_KEY")

def _get_team_info(team_name: str) -> dict:
    if not team_name or team_name.strip() == "":
        return {"name": None, "tla": None, "crest": None}
    name = team_name.strip()
    mapping = TEAM_MAPPING.get(name, {})
    return {
        "name": name,
        "tla": mapping.get("tla", name[:3].upper()),
        "crest": mapping.get("crest", "https://crests.thefootballco.com/default.png")
    }

def _fetch_from_csv() -> list[dict]:
    """Parses local CSV into API-like JSON objects."""
    if not os.path.exists(CSV_PATH):
        st.error(f"Fatal Error: Fallback file '{CSV_PATH}' missing.")
        return []
    
    matches = []
    try:
        with open(CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                home_score_raw = row["home_score"]
                away_score_raw = row["away_score"]
                home_score_val = int(home_score_raw) if home_score_raw else None
                away_score_val = int(away_score_raw) if away_score_raw else None
                
                status = row["status"].strip().upper()
                winner = None
                if status == "FINISHED" and home_score_val is not None and away_score_val is not None:
                    if home_score_val > away_score_val: winner = "HOME_TEAM"
                    elif away_score_val > home_score_val: winner = "AWAY_TEAM"
                    else: winner = "DRAW"

                matches.append({
                    "id": int(row["match_id"]),
                    "utcDate": row["utc_date"],
                    "status": status,
                    "stage": STAGE_MAPPING.get(row["stage"].strip().upper(), row["stage"].strip().upper()),
                    "homeTeam": _get_team_info(row["home_team_name"]),
                    "awayTeam": _get_team_info(row["away_team_name"]),
                    "score": {
                        "winner": winner,
                        "duration": "REGULAR",
                        "fullTime": {"home": home_score_val, "away": away_score_val}
                    }
                })
        return matches
    except Exception as e:
        st.error(f"CSV Parse Error: {e}")
        return []

# --- 4. THE DUAL-ENGINE ENDPOINTS ---

@st.cache_data(ttl=3600)
def get_world_cup_matches() -> list[dict]:
    api_key = _get_api_key()
    
    if not api_key:
        st.sidebar.info("🔌 Running in Offline Mode (No API Key). Loading local data.")
        return _fetch_from_csv()

    try:
        response = requests.get(
            f"{BASE_URL}/competitions/WC/matches",
            headers={"X-Auth-Token": api_key},
            timeout=5 
        )
        response.raise_for_status()
        return response.json().get("matches", [])
        
    except Exception as e:
        st.sidebar.warning(f"⚠️ Live API unavailable. Falling back to local data.")
        return _fetch_from_csv()

def get_match(match_id: int) -> dict:
    """Safely fetches a single match, catching API errors."""
    api_key = _get_api_key()
    if not api_key:
        return {} # No live API connection
        
    try:
        response = requests.get(
            f"{BASE_URL}/matches/{match_id}",
            headers={"X-Auth-Token": api_key},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Silently fail or log to avoid breaking UI
        return {}

def get_team(team_id: int) -> dict:
    """Safely fetches a single team, catching API errors."""
    api_key = _get_api_key()
    if not api_key:
        return {} # No live API connection
        
    try:
        response = requests.get(
            f"{BASE_URL}/teams/{team_id}",
            headers={"X-Auth-Token": api_key},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {}