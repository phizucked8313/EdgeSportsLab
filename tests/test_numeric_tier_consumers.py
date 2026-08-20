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


def test_draft_score_ignores_tier_status_when_numeric_scarcity_exists():
    elite_status = _row(55.0) | {"tier_status": "ELITE SOLO TIER"}
    depth_status = _row(55.0) | {"tier_status": "DEPTH AVAILABLE"}

    elite_result = calculate_draft_score(pd.DataFrame([elite_status])).iloc[0]
    depth_result = calculate_draft_score(pd.DataFrame([depth_status])).iloc[0]

    assert elite_result["tier_scarcity_score"] == 55.0
    assert depth_result["tier_scarcity_score"] == 55.0
    assert elite_result["draft_score"] == depth_result["draft_score"]


def test_live_draft_score_recompute_preserves_baseline_rank():
    result = recalculate_live_draft_score(pd.DataFrame([_row(75.0)]))
    assert result.iloc[0]["draft_rank"] == 7
