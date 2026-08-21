import pandas as pd
import pytest

from fantasy_draft_model.engines import projection_engine


def _apply(df):
    return projection_engine.apply_current_injury_projection_penalty(df)


def _player_row(
    *,
    projected_points=100.0,
    severity=0.0,
    injured=True,
    stale=False,
    research_override=False,
):
    return {
        "player_name_clean": "Test Player",
        "position": "WR",
        "projected_points": projected_points,
        "is_currently_injured": injured,
        "current_injury_severity": severity,
        "current_injury_is_stale": stale,
        "current_injury_research_override": research_override,
    }


@pytest.mark.parametrize(
    ("severity", "expected_penalty", "expected_projection"),
    [
        (1.00, 0.120, 88.0),   # Out / IR / PUP
        (0.85, 0.102, 89.8),   # Doubtful
        (0.45, 0.054, 94.6),   # Questionable
        (0.35, 0.042, 95.8),   # Limited practice only
        (0.05, 0.006, 99.4),   # Full practice only
    ],
)
def test_current_injury_severity_applies_exact_capped_projection_penalty(
    severity,
    expected_penalty,
    expected_projection,
):
    result = _apply(pd.DataFrame([_player_row(severity=severity)])).iloc[0]

    assert result["pre_current_injury_projected_points"] == pytest.approx(100.0)
    assert result["current_injury_projection_penalty"] == pytest.approx(
        expected_penalty
    )
    assert result["current_injury_projection_multiplier"] == pytest.approx(
        1.0 - expected_penalty
    )
    assert result["projected_points"] == pytest.approx(expected_projection)


def test_projection_penalty_is_capped_at_twelve_percent():
    result = _apply(pd.DataFrame([_player_row(severity=4.0)])).iloc[0]

    assert result["current_injury_projection_penalty"] == pytest.approx(0.12)
    assert result["current_injury_projection_multiplier"] == pytest.approx(0.88)
    assert result["projected_points"] == pytest.approx(88.0)


def test_healthy_player_projection_does_not_move():
    result = _apply(
        pd.DataFrame([
            _player_row(severity=1.0, injured=False),
        ])
    ).iloc[0]

    assert result["current_injury_projection_penalty"] == pytest.approx(0.0)
    assert result["current_injury_projection_multiplier"] == pytest.approx(1.0)
    assert result["projected_points"] == pytest.approx(100.0)


def test_stale_current_injury_does_not_auto_penalize_projection():
    result = _apply(
        pd.DataFrame([
            _player_row(severity=1.0, stale=True, research_override=False),
        ])
    ).iloc[0]

    assert result["current_injury_projection_penalty"] == pytest.approx(0.0)
    assert result["current_injury_projection_multiplier"] == pytest.approx(1.0)
    assert result["projected_points"] == pytest.approx(100.0)


def test_research_override_allows_stale_injury_penalty():
    result = _apply(
        pd.DataFrame([
            _player_row(severity=0.85, stale=True, research_override=True),
        ])
    ).iloc[0]

    assert result["current_injury_projection_penalty"] == pytest.approx(0.102)
    assert result["current_injury_projection_multiplier"] == pytest.approx(0.898)
    assert result["projected_points"] == pytest.approx(89.8)


def test_missing_current_injury_severity_is_neutral():
    row = _player_row(severity=0.0)
    row["current_injury_severity"] = None

    result = _apply(pd.DataFrame([row])).iloc[0]

    assert result["current_injury_projection_penalty"] == pytest.approx(0.0)
    assert result["current_injury_projection_multiplier"] == pytest.approx(1.0)
    assert result["projected_points"] == pytest.approx(100.0)
