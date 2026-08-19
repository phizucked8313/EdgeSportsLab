import inspect

import pandas as pd
import pytest

from fantasy_draft_model.config import load_league_settings
from fantasy_draft_model.engines import projection_engine
from fantasy_draft_model import rankings
from fantasy_draft_model.models import player_profiles
from fantasy_draft_model.models.projections import (
    add_bonus_flags,
    add_custom_fantasy_scoring,
)


def _zero_scoring_row():
    return pd.DataFrame(
        {
            "receptions": [0],
            "rushing_yards": [0],
            "receiving_yards": [0],
            "passing_yards": [0],
            "rushing_tds": [0],
            "receiving_tds": [0],
            "passing_tds": [0],
            "passing_interceptions": [0],
            "fumbles_lost": [0],
            "two_point_conversions": [0],
            "return_tds": [0],
            "offensive_fumble_return_tds": [0],
            "games_300_pass": [0],
            "games_400_pass": [0],
            "games_500_pass": [0],
            "games_100_rush": [0],
            "games_200_rush": [0],
            "games_300_rush": [0],
            "games_100_receive": [0],
            "games_200_receive": [0],
            "games_300_receive": [0],
            "plays_40_pass_completion": [0],
            "plays_40_pass_td": [0],
            "plays_40_rush": [0],
            "plays_40_rush_td": [0],
            "plays_40_reception": [0],
            "plays_40_reception_td": [0],
            "games_played": [1],
        }
    )


def test_league_settings_require_explicit_key():
    with pytest.raises(TypeError):
        load_league_settings()


def test_unknown_league_key_fails_clearly():
    with pytest.raises(ValueError, match="drunk_sundays.*somewhat_related"):
        load_league_settings("not_a_league")


def test_drunk_sundays_profile_matches_yahoo_settings():
    settings = load_league_settings("drunk_sundays")
    offense = settings["scoring"]["offense"]
    defense = settings["scoring"]["defense"]

    assert settings["league_id"] == "390151"
    assert offense["passing_yard"] == 0.04
    assert offense["reception"] == 1.0
    assert offense["bonus_300_passing"] == 2
    assert offense["bonus_400_passing"] == 4
    assert offense["bonus_500_passing"] == 6
    assert offense["play_40_completion"] == 4
    assert offense["play_40_run"] == 0
    assert offense["play_40_reception"] == 0
    assert offense["play_40_passing_td"] == 4
    assert offense["play_40_rushing_td"] == 4
    assert offense["play_40_receiving_td"] == 4
    assert defense["points_allowed"]["0"] == 14
    assert defense["yards_allowed"]["0_99"] == 10
    assert defense["yards_allowed"]["500_plus"] == -2


def test_somewhat_related_profile_matches_yahoo_settings():
    settings = load_league_settings("somewhat_related")
    offense = settings["scoring"]["offense"]
    defense = settings["scoring"]["defense"]

    assert settings["league_id"] == "950841"
    assert offense["play_40_completion"] == 2
    assert offense["play_40_run"] == 2
    assert offense["play_40_reception"] == 2
    assert offense["play_40_passing_td"] == 4
    assert offense["play_40_rushing_td"] == 4
    assert offense["play_40_receiving_td"] == 4
    assert defense["points_allowed"]["0"] == 10
    assert defense["points_allowed"]["28_34"] == 1
    assert defense["yards_allowed"] == {}


def test_bonus_flags_are_cumulative():
    weekly = pd.DataFrame(
        {
            "passing_yards": [500],
            "rushing_yards": [300],
            "receiving_yards": [300],
        }
    )

    result = add_bonus_flags(weekly)

    assert result.loc[0, [
        "game_300_pass",
        "game_400_pass",
        "game_500_pass",
        "game_100_rush",
        "game_200_rush",
        "game_300_rush",
        "game_100_receive",
        "game_200_receive",
        "game_300_receive",
    ]].tolist() == [1] * 9


def test_passing_milestone_bonuses_stack_cumulatively():
    df = _zero_scoring_row()
    df.loc[0, "passing_yards"] = 500
    df.loc[0, ["games_300_pass", "games_400_pass", "games_500_pass"]] = 1

    result = add_custom_fantasy_scoring(
        df,
        load_league_settings("drunk_sundays"),
    )

    assert result.loc[0, "custom_fantasy_points"] == 32.0


def test_rushing_and_receiving_milestone_bonuses_stack_cumulatively():
    df = _zero_scoring_row()
    df.loc[0, "rushing_yards"] = 300
    df.loc[0, "receiving_yards"] = 300
    df.loc[0, ["games_100_rush", "games_200_rush", "games_300_rush"]] = 1
    df.loc[0, [
        "games_100_receive",
        "games_200_receive",
        "games_300_receive",
    ]] = 1

    result = add_custom_fantasy_scoring(
        df,
        load_league_settings("drunk_sundays"),
    )

    # 30 rush yards points + 30 receiving yards points
    # + 12 cumulative rush bonus + 12 cumulative receiving bonus.
    assert result.loc[0, "custom_fantasy_points"] == 84.0


def test_same_long_play_profile_scores_differently_by_league():
    df = _zero_scoring_row()
    df.loc[0, "plays_40_rush"] = 1
    df.loc[0, "plays_40_reception"] = 1
    df.loc[0, "plays_40_rush_td"] = 1
    df.loc[0, "plays_40_reception_td"] = 1

    drunk = add_custom_fantasy_scoring(
        df,
        load_league_settings("drunk_sundays"),
    )
    related = add_custom_fantasy_scoring(
        df,
        load_league_settings("somewhat_related"),
    )

    assert drunk.loc[0, "custom_fantasy_points"] == 8
    assert related.loc[0, "custom_fantasy_points"] == 12


def test_turnovers_conversions_and_return_scores_use_yahoo_values():
    df = _zero_scoring_row()
    df.loc[0, "passing_interceptions"] = 1
    df.loc[0, "fumbles_lost"] = 1
    df.loc[0, "two_point_conversions"] = 1
    df.loc[0, "return_tds"] = 1
    df.loc[0, "offensive_fumble_return_tds"] = 1

    result = add_custom_fantasy_scoring(
        df,
        load_league_settings("drunk_sundays"),
    )

    # -1 interception -2 fumble +2 conversion +6 return TD +6 fumble return TD.
    assert result.loc[0, "custom_fantasy_points"] == 11.0


def test_scoring_sensitive_public_functions_require_league_key_parameter():
    functions = [
        player_profiles.build_player_profiles,
        projection_engine.build_2026_projections,
        rankings.build_draft_rankings,
    ]

    for function in functions:
        parameters = inspect.signature(function).parameters
        assert "league_key" in parameters
        assert parameters["league_key"].default is inspect.Parameter.empty


def test_player_profiles_forwards_explicit_league_key(monkeypatch):
    calls = []

    def fake_create_master_player_table(league_key):
        calls.append(league_key)
        return pd.DataFrame()

    monkeypatch.setattr(
        player_profiles,
        "create_master_player_table",
        fake_create_master_player_table,
    )

    result = player_profiles.build_player_profiles("somewhat_related")

    assert calls == ["somewhat_related"]
    assert result.empty


def test_projection_pipeline_forwards_explicit_league_key_to_profiles(monkeypatch):
    class ReachedProfiles(Exception):
        pass

    def fake_build_player_profiles(league_key):
        assert league_key == "somewhat_related"
        raise ReachedProfiles

    monkeypatch.setattr(
        projection_engine,
        "build_player_profiles",
        fake_build_player_profiles,
    )

    with pytest.raises(ReachedProfiles):
        projection_engine.build_2026_projections("somewhat_related")


def test_rankings_forwards_explicit_league_key_to_projection_pipeline(monkeypatch):
    class ReachedProjectionPipeline(Exception):
        pass

    def fake_build_2026_projections(league_key):
        assert league_key == "drunk_sundays"
        raise ReachedProjectionPipeline

    monkeypatch.setattr(
        rankings,
        "build_2026_projections",
        fake_build_2026_projections,
    )

    with pytest.raises(ReachedProjectionPipeline):
        rankings.build_draft_rankings("drunk_sundays")
