import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import math_engine as me

def test_probabilities_sum_to_one():
    stats = me.load_team_stats("predictor.db")
    result = me.predict_match(stats, "Brazil", "Argentina")
    total = result.home_win_prob + result.draw_prob + result.away_win_prob
    assert abs(total - 1.0) < 0.001

def test_stronger_team_favoured():
    stats = me.load_team_stats("predictor.db")
    result = me.predict_match(stats, "Brazil", "South Africa")
    assert result.home_win_prob > result.away_win_prob

def test_unknown_team_uses_global_fallback():
    stats = me.load_team_stats("predictor.db")
    rec = me.get_team_stats(stats, "Atlantis FC")
    assert rec.name == "__global__"

