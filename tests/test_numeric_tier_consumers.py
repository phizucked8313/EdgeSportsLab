import pandas as pd

from fantasy_draft_model.rankings import calculate_draft_score, recalculate_live_draft_score


def _row(scarcity):
    return {
        "player_name_clean": "Player A",
        "position": "RB",
        "vorp": 100.0,
        "vorp_score": 50.0,
        "edgescore": 80.0,
        "projection_score": 70.0,
        "projection_confidence": 90.0,
        "tier_scarcity_score": scarcity,
        "draft_rank": 7,
    }


def test_draft_score_consumes_existing_numeric_scarcity():
    low = calculate_draft_score(pd.DataFrame([_row(20.0)])).iloc[0]
    high = calculate_draft_score(pd.DataFrame([_row(80.0)])).iloc[0]
    assert round(high["draft_score"] - low["draft_score"], 2) == 6.0


def test_live_draft_score_recompute_preserves_baseline_rank():
    result = recalculate_live_draft_score(pd.DataFrame([_row(75.0)]))
    assert result.iloc[0]["draft_rank"] == 7
