import pandas as pd

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


def test_default_scoring_path_uses_configured_league_values():
    result = add_custom_fantasy_scoring(_scoring_row())

    # 1 PPR + 1 rush yd point + 2 rec yd points + 1 pass yd point
    # + 6 rush TD + 6 rec TD + 4 pass TD + three 3-point bonuses.
    assert result.loc[0, "custom_fantasy_points"] == 30.0
    assert result.loc[0, "custom_points_per_game"] == 30.0


def test_league_settings_match_confirmed_scoring_rules():
    scoring = load_league_settings()["scoring"]

    assert scoring == {
        "reception": 1.0,
        "rushing_yard": 0.1,
        "receiving_yard": 0.1,
        "passing_yard": 0.04,
        "rushing_td": 6,
        "receiving_td": 6,
        "passing_td": 4,
        "bonus_300_passing": 3,
        "bonus_100_rushing": 3,
        "bonus_100_receiving": 3,
    }
