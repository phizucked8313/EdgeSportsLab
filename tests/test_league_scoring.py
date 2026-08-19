import pandas as pd
import pytest

from fantasy_draft_model.config import load_league_settings
from fantasy_draft_model.models.projections import add_custom_fantasy_scoring


def _scoring_row():
    return pd.DataFrame(
        {
            "receptions": [1],
            "rushing_yards": [10],
            "receiving_yards": [20],
            "passing_yards": [25],
            "rushing_tds": [1],
            "receiving_tds": [1],
            "passing_tds": [1],
            "games_300_pass": [1],
            "games_100_rush": [1],
            "games_100_receive": [1],
            "games_played": [1],
        }
    )


def test_custom_fantasy_scoring_uses_supplied_league_settings():
    settings = {
        "scoring": {
            "reception": 2.0,
            "rushing_yard": 0.2,
            "receiving_yard": 0.3,
            "passing_yard": 0.1,
            "rushing_td": 5,
            "receiving_td": 7,
            "passing_td": 6,
            "bonus_300_passing": 4,
            "bonus_100_rushing": 5,
            "bonus_100_receiving": 6,
        }
    }

    result = add_custom_fantasy_scoring(
        _scoring_row(),
        league_settings=settings,
    )

    assert result.loc[0, "custom_fantasy_points"] == 45.5
    assert result.loc[0, "custom_points_per_game"] == 45.5


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
