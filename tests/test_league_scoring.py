import pandas as pd

from fantasy_draft_model.models.projections import add_custom_fantasy_scoring


def test_custom_fantasy_scoring_uses_supplied_league_settings():
    df = pd.DataFrame(
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
        df,
        league_settings=settings,
    )

    assert result.loc[0, "custom_fantasy_points"] == 45.5
    assert result.loc[0, "custom_points_per_game"] == 45.5
