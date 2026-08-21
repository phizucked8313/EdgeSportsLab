import pandas as pd

from fantasy_draft_model.engines.draft_brain_engine import (
    add_draft_brain,
    build_draft_brain_for_player,
)
from fantasy_draft_model.engines.pressure_meter_engine import calculate_pressure_score
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


def _brain_row():
    return {
        "player_name_clean": "RB A",
        "position": "RB",
        "draft_rank": 1,
        "tier": 2,
        "tier_remaining": 1,
        "tier_scarcity_score": 85.0,
        "pressure_score": 50.0,
        "draft_score": 60.0,
        "edgescore": 70.0,
        "vorp": 80.0,
        "vorp_score": 50.0,
        "projection_confidence": 90.0,
        "injury_risk_score": 10.0,
    }


def test_pressure_uses_numeric_tier_scarcity_directly():
    df = pd.DataFrame([{
        "draft_rank": 1,
        "tier_scarcity_score": 42.0,
        "vorp": 0.0,
        "draft_score": 50.0,
    }])

    result = calculate_pressure_score(df)

    assert result.iloc[0]["tier_pressure"] == 42.0


def test_brain_uses_numeric_tier_scarcity_and_numbered_tier_reason():
    high_scarcity = _brain_row() | {
        "tier_scarcity_score": 80.0,
        "tier_status": "DEPTH AVAILABLE",
    }
    low_scarcity = _brain_row() | {
        "tier_scarcity_score": 20.0,
        "tier_status": "ELITE SOLO TIER",
    }
    df = pd.DataFrame([high_scarcity, low_scarcity])

    high_report = build_draft_brain_for_player(
        df,
        df.iloc[0],
        {"picks_until_user": 3},
        wait_report={"survival_score": 50, "projection_drop": 0},
        position_run={"run_score": 0, "run_label": "NORMAL"},
    )
    low_report = build_draft_brain_for_player(
        df,
        df.iloc[1],
        {"picks_until_user": 3},
        wait_report={"survival_score": 50, "projection_drop": 0},
        position_run={"run_score": 0, "run_label": "NORMAL"},
    )

    assert "Last player remaining in RB Tier 2" in high_report["reasons"]
    assert high_report["brain_score"] - low_report["brain_score"] == 9.0


def test_brain_handles_completed_draft_context():
    df = pd.DataFrame([_brain_row()])

    report = build_draft_brain_for_player(
        df,
        df.iloc[0],
        {"picks_until_user": None},
        wait_report={"survival_score": 50, "projection_drop": 0},
        position_run={"run_score": 0, "run_label": "NORMAL"},
    )

    assert report["brain_score"] >= 0


def test_add_brain_handles_completed_draft_context():
    result = add_draft_brain(
        pd.DataFrame([_brain_row()]),
        {"picks_until_user": None},
    )

    assert result.iloc[0]["brain_score"] >= 0


def test_add_brain_handles_completed_draft_with_no_players_remaining():
    result = add_draft_brain(
        pd.DataFrame(),
        {"picks_until_user": None, "draft_complete": True},
    )

    assert result.empty
