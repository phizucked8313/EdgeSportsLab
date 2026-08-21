import pandas as pd
import pytest

from fantasy_draft_model.engines import projection_engine


def _row(*, severity=0.45, expected_games_missed=None, season_ending=False):
    return {
        "player_name_clean": "Test Player",
        "position": "RB",
        "projected_points": 170.0,
        "is_currently_injured": True,
        "current_injury_severity": severity,
        "current_injury_is_stale": False,
        "current_injury_research_override": False,
        "current_injury_expected_games_missed": expected_games_missed,
        "current_injury_season_ending": season_ending,
    }


def _apply(**kwargs):
    return projection_engine.apply_current_injury_projection_penalty(
        pd.DataFrame([_row(**kwargs)])
    ).iloc[0]


def test_week_one_ready_injury_with_zero_regular_season_games_missed_keeps_status_penalty():
    result = _apply(expected_games_missed=0)

    assert result["current_injury_timeline_penalty"] == pytest.approx(0.0)
    assert result["current_injury_projection_penalty"] == pytest.approx(0.054)
    assert result["projected_points"] == pytest.approx(160.82)


def test_known_five_game_absence_overrides_small_status_penalty():
    result = _apply(expected_games_missed=5)

    expected = 5 / projection_engine.PROJECTED_GAMES
    assert result["current_injury_timeline_penalty"] == pytest.approx(expected)
    assert result["current_injury_projection_penalty"] == pytest.approx(expected)
    assert result["projected_points"] == pytest.approx(120.0)


def test_verified_season_ending_injury_reduces_season_projection_to_zero():
    result = _apply(expected_games_missed=17, season_ending=True)

    assert result["current_injury_timeline_penalty"] == pytest.approx(1.0)
    assert result["current_injury_projection_penalty"] == pytest.approx(1.0)
    assert result["current_injury_projection_multiplier"] == pytest.approx(0.0)
    assert result["projected_points"] == pytest.approx(0.0)
