import pandas as pd
import pytest

from fantasy_draft_model.engines import projection_engine
from fantasy_draft_model.engines.historical_baseline_engine import (
    add_historical_regression_metadata,
    build_multi_year_ppr_summary,
)
from fantasy_draft_model.engines.projection_engine import (
    attach_historical_regression,
    calculate_projection,
)


def _weekly_history():
    rows = []
    # Veteran Down: 10 -> 20 -> 30 PPR/G. Weighted 3-year baseline is 23.
    for season, ppg in [(2023, 10.0), (2024, 20.0), (2025, 30.0)]:
        for week in range(1, 5):
            rows.append(
                {
                    "player_id": "down",
                    "season": season,
                    "week": week,
                    "season_type": "REG",
                    "fantasy_points_ppr": ppg,
                }
            )

    # Veteran Up: 20 -> 20 -> 10 PPR/G. Weighted baseline is 15.
    for season, ppg in [(2023, 20.0), (2024, 20.0), (2025, 10.0)]:
        for week in range(1, 5):
            rows.append(
                {
                    "player_id": "up",
                    "season": season,
                    "week": week,
                    "season_type": "REG",
                    "fantasy_points_ppr": ppg,
                }
            )

    # One-season player should not be regressed from a one-year sample.
    for week in range(1, 5):
        rows.append(
            {
                "player_id": "one",
                "season": 2025,
                "week": week,
                "season_type": "REG",
                "fantasy_points_ppr": 18.0,
            }
        )

    # Postseason must not leak into the baseline.
    rows.append(
        {
            "player_id": "down",
            "season": 2025,
            "week": 19,
            "season_type": "POST",
            "fantasy_points_ppr": 100.0,
        }
    )
    return pd.DataFrame(rows)


def test_build_multi_year_ppr_summary_uses_recency_weights_and_regular_season_only():
    summary = build_multi_year_ppr_summary(_weekly_history()).set_index("player_id")

    assert round(summary.loc["down", "multi_year_ppr_pg"], 3) == 23.0
    assert round(summary.loc["up", "multi_year_ppr_pg"], 3) == 15.0
    assert int(summary.loc["down", "multi_year_seasons_used"]) == 3
    assert int(summary.loc["one", "multi_year_seasons_used"]) == 1


def test_historical_regression_is_bounded_and_requires_two_seasons():
    current = pd.DataFrame(
        [
            {
                "player_id": "down",
                "player_name_clean": "Veteran Down",
                "position": "WR",
                "ppr_points_per_game": 30.0,
                "is_rookie": False,
            },
            {
                "player_id": "up",
                "player_name_clean": "Veteran Up",
                "position": "RB",
                "ppr_points_per_game": 10.0,
                "is_rookie": False,
            },
            {
                "player_id": "one",
                "player_name_clean": "One Year",
                "position": "WR",
                "ppr_points_per_game": 18.0,
                "is_rookie": False,
            },
            {
                "player_id": "rookie",
                "player_name_clean": "True Rookie",
                "position": "RB",
                "ppr_points_per_game": 0.0,
                "is_rookie": True,
            },
        ]
    )
    summary = build_multi_year_ppr_summary(_weekly_history())

    result = add_historical_regression_metadata(current, summary).set_index("player_id")

    # Raw down ratio 23/30 is clipped to 0.80, then blended 50% -> 0.90.
    assert result.loc["down", "historical_regression_multiplier"] == 0.90
    # Raw up ratio 15/10 is clipped to 1.20, then blended 50% -> 1.10.
    assert result.loc["up", "historical_regression_multiplier"] == 1.10
    # One-season samples and rookies remain neutral.
    assert result.loc["one", "historical_regression_multiplier"] == 1.00
    assert result.loc["rookie", "historical_regression_multiplier"] == 1.00


def test_projection_baseline_can_consume_regression_multiplier_without_name_overrides():
    current = pd.DataFrame(
        [
            {
                "player_id": "up",
                "player_name_clean": "Veteran Up",
                "position": "RB",
                "ppr_points_per_game": 10.0,
                "is_rookie": False,
                "custom_points_per_game": 12.0,
            }
        ]
    )
    summary = build_multi_year_ppr_summary(_weekly_history())
    result = add_historical_regression_metadata(current, summary)

    regressed_baseline = (
        result.loc[0, "custom_points_per_game"]
        * 17
        * result.loc[0, "historical_regression_multiplier"]
    )
    assert round(regressed_baseline, 2) == 224.40


def test_calculate_projection_applies_historical_regression_to_veteran_baseline():
    current = pd.DataFrame(
        [
            {
                "player_name_clean": "Veteran Up",
                "position": "RB",
                "custom_points_per_game": 12.0,
                "historical_regression_multiplier": 1.10,
                "is_rookie": False,
                "opportunity_score": 50.0,
                "target_regression_factor": 1.0,
                "injury_risk_score": 0.0,
                "manual_adjustment": 1.0,
            }
        ]
    )

    result = calculate_projection(current)

    assert round(result.loc[0, "baseline_projection"], 2) == 224.40
    assert round(result.loc[0, "projected_points"], 2) == 224.40


def test_attach_historical_regression_uses_loaded_summary():
    current = pd.DataFrame(
        [
            {
                "player_id": "up",
                "player_name_clean": "Veteran Up",
                "position": "RB",
                "ppr_points_per_game": 10.0,
                "is_rookie": False,
            }
        ]
    )
    summary = build_multi_year_ppr_summary(_weekly_history())

    result = attach_historical_regression(
        current,
        loader=lambda: summary,
    )

    assert result.loc[0, "historical_regression_multiplier"] == 1.10
    assert result.loc[0, "historical_regression_data_status"] == "LIVE"
    assert result.loc[0, "historical_regression_failure_reason"] == ""


def test_attach_historical_regression_falls_back_neutral_when_loader_fails():
    current = pd.DataFrame(
        [
            {
                "player_id": "up",
                "player_name_clean": "Veteran Up",
                "position": "RB",
                "ppr_points_per_game": 10.0,
                "is_rookie": False,
            }
        ]
    )

    def failing_loader():
        raise RuntimeError("historical source unavailable")

    result = attach_historical_regression(current, loader=failing_loader)

    assert result.loc[0, "historical_regression_multiplier"] == 1.00
    assert result.loc[0, "historical_regression_data_status"] == "FALLBACK_NEUTRAL"
    assert "historical source unavailable" in result.loc[0, "historical_regression_failure_reason"]


def test_build_2026_projections_attaches_historical_context_before_projection(monkeypatch):
    source = pd.DataFrame(
        [
            {
                "player_id": "up",
                "player_name_clean": "Veteran Up",
                "position": "RB",
                "is_fantasy_draftable": True,
            }
        ]
    )
    monkeypatch.setattr(projection_engine, "load_league_settings", lambda _league_key: {})
    monkeypatch.setattr(projection_engine, "build_player_profiles", lambda _league_key: source.copy())

    identity_stages = [
        "add_rookie_projection_components",
        "add_rookie_baseline_projection",
        "add_per_game_metrics",
        "add_rushing_usage_scores",
        "add_qb_contact_exposure",
        "calculate_opportunity_score",
        "add_target_regression",
        "add_manual_adjustments",
    ]
    for stage_name in identity_stages:
        monkeypatch.setattr(
            projection_engine,
            stage_name,
            lambda df: df.copy(),
        )

    def fake_injury_scores(df):
        result = df.copy()
        result["injury_risk_score"] = 0.0
        return result

    monkeypatch.setattr(projection_engine, "add_injury_scores", fake_injury_scores)

    calls = {"historical": False}

    def fake_historical(df):
        calls["historical"] = True
        result = df.copy()
        result["historical_regression_multiplier"] = 1.10
        return result

    def stop_at_projection(df):
        assert calls["historical"] is True
        assert df.loc[0, "historical_regression_multiplier"] == 1.10
        raise RuntimeError("stop after historical ordering check")

    monkeypatch.setattr(projection_engine, "attach_historical_regression", fake_historical)
    monkeypatch.setattr(projection_engine, "calculate_projection", stop_at_projection)

    with pytest.raises(RuntimeError, match="stop after historical ordering check"):
        projection_engine.build_2026_projections("drunk_sundays")
