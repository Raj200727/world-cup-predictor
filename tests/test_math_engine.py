import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from unittest.mock import patch
import math_engine as me

@patch("services.fixture_service.get_world_cup_matches")
def test_probabilities_sum_to_one(mock_get_matches):
    # CHANGED: Return an empty list instead of a dict
    mock_get_matches.return_value = [] 
    
    stats = me.load_team_stats("predictor.db")
    result = me.predict_match(stats, "Brazil", "Argentina")
    total = result.home_win_prob + result.draw_prob + result.away_win_prob
    assert abs(total - 1.0) < 0.001

@patch("services.fixture_service.get_world_cup_matches")
def test_stronger_team_favoured(mock_get_matches):
    # CHANGED: Return an empty list instead of a dict
    mock_get_matches.return_value = []
    
    stats = me.load_team_stats("predictor.db")
    result = me.predict_match(stats, "Brazil", "South Africa")
    assert result.home_win_prob > result.away_win_prob

def test_unknown_team_uses_global_fallback():
    stats = me.load_team_stats("predictor.db")
    rec = me.get_team_stats(stats, "Atlantis FC")
    assert rec.name == "__global__"

