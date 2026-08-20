import pandas as pd

from fantasy_draft_model import rankings
from fantasy_draft_model.engines import (
    draft_brain_engine,
    pressure_meter_engine,
    what_if_i_wait_engine,
)
from fantasy_draft_model.models import football_intelligence


def _base_row(**overrides):
    row = {
        "player_name_clean": "Test WR",
        "position": "WR",
        "draft_rank": 1,
        "tier": 1,
        "tier_remaining": 1,
        "tier_scarcity_score": 60.0,
        "tier_next_projection_drop": 14.0,
        "tier_next_vorp_drop": 14.0,
        "projected_points": 300.0,
        "replacement_points": 200.0,
        "vorp": 120.0,
        "vorp_score": 60.0,
        "projection_score": 70.0,
        "edgescore": 80.0,
        "projection_confidence": 90.0,
        "injury_risk_score": 10.0,
        "draft_score": 70.0,
        "pressure_score": 50.0,
    }
    row.update(overrides)
    return row


def test_rankings_preserve_numeric_tier_scarcity_order():
    df = pd.DataFrame(
        [
            _base_row(player_name_clean="Solo", tier_scarcity_score=100.0),
            _base_row(player_name_clean="Small", tier_scarcity_score=80.0),
            _base_row(player_name_clean="Limited", tier_scarcity_score=60.0),
            _base_row(player_name_clean="Depth", tier_scarcity_score=35.0),
        ]
    )

    result = rankings.calculate_draft_score(df).set_index("player_name_clean")

    assert result.loc["Solo", "tier_scarcity_score"] == 100
    assert result.loc["Small", "tier_scarcity_score"] == 80
    assert result.loc["Limited", "tier_scarcity_score"] == 60
    assert result.loc["Depth", "tier_scarcity_score"] == 35
    assert result["draft_score"].tolist() == sorted(
        result["draft_score"],
        reverse=True,
    )
    assert result.loc["Solo", "draft_score"] - result.loc["Depth", "draft_score"] == 6.5


def test_pressure_meter_preserves_numeric_tier_scarcity_order():
    df = pd.DataFrame(
        [
            _base_row(player_name_clean="Solo", draft_rank=1, tier_scarcity_score=100.0),
            _base_row(player_name_clean="Small", draft_rank=2, tier_scarcity_score=80.0),
            _base_row(player_name_clean="Limited", draft_rank=3, tier_scarcity_score=60.0),
            _base_row(player_name_clean="Depth", draft_rank=4, tier_scarcity_score=35.0),
        ]
    )

    result = pressure_meter_engine.calculate_pressure_score(df).set_index("player_name_clean")

    assert result.loc["Solo", "tier_pressure"] == 100
    assert result.loc["Small", "tier_pressure"] == 80
    assert result.loc["Limited", "tier_pressure"] == 60
    assert result.loc["Depth", "tier_pressure"] == 35


def test_draft_brain_scores_higher_numeric_tier_scarcity_above_lower_scarcity():
    solo = pd.Series(_base_row(player_name_clean="Solo", tier_scarcity_score=100.0))
    limited = pd.Series(_base_row(player_name_clean="Limited", tier_scarcity_score=60.0))
    board = pd.DataFrame([solo, limited])
    wait_report = {"survival_score": 50.0, "projection_drop": 0.0}
    position_run = {"run_score": 0.0, "run_label": "NORMAL"}
    context = {"picks_until_user": 5}

    solo_report = draft_brain_engine.build_draft_brain_for_player(
        board,
        solo,
        context,
        wait_report=wait_report,
        position_run=position_run,
    )
    limited_report = draft_brain_engine.build_draft_brain_for_player(
        board,
        limited,
        context,
        wait_report=wait_report,
        position_run=position_run,
    )

    assert solo_report["brain_score"] - limited_report["brain_score"] == 6.0
    assert "tier_status" not in solo_report


def test_football_intelligence_uses_numeric_tier_remaining():
    last_player_pros, _ = football_intelligence.draft_intelligence(
        pd.Series(_base_row(tier=2, tier_remaining=1))
    )
    nearly_gone_pros, _ = football_intelligence.draft_intelligence(
        pd.Series(_base_row(tier=2, tier_remaining=2))
    )

    assert "Last player remaining in current tier" in last_player_pros
    assert "Position tier is nearly exhausted" in nearly_gone_pros


def test_wait_recommendation_uses_numeric_tier_remaining_for_last_player():
    recommendation, reason = what_if_i_wait_engine.create_wait_recommendation(
        pd.Series(_base_row(tier=2, tier_remaining=1, pressure_score=0.0)),
        survival_score=100.0,
        value_drop={"projection_drop": 0.0, "vorp_drop": 0.0},
    )

    assert recommendation == "DO NOT WAIT"
    assert reason == "Last player remaining in the current tier."


def test_draft_brain_uses_normalized_vorp_score_not_raw_vorp_clamp():
    high = pd.Series(
        _base_row(
            player_name_clean="High VORP",
            vorp=180.0,
            vorp_score=80.0,
            tier_scarcity_score=35.0,
        )
    )
    low = pd.Series(
        _base_row(
            player_name_clean="Low VORP",
            vorp=120.0,
            vorp_score=60.0,
            tier_scarcity_score=35.0,
        )
    )
    board = pd.DataFrame([high, low])
    wait_report = {"survival_score": 50.0, "projection_drop": 0.0}
    position_run = {"run_score": 0.0, "run_label": "NORMAL"}
    context = {"picks_until_user": 5}

    high_report = draft_brain_engine.build_draft_brain_for_player(
        board,
        high,
        context,
        wait_report=wait_report,
        position_run=position_run,
    )
    low_report = draft_brain_engine.build_draft_brain_for_player(
        board,
        low,
        context,
        wait_report=wait_report,
        position_run=position_run,
    )

    assert high_report["brain_score"] > low_report["brain_score"]
