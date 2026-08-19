import pandas as pd

from fantasy_draft_model import rankings


def test_vorp_normalization_treats_replacement_level_as_zero_value():
    df = pd.DataFrame(
        {
            "player_name_clean": [
                "Elite Player",
                "Mid Value",
                "Replacement QB",
                "Below Replacement QB",
            ],
            "position": ["RB", "WR", "QB", "QB"],
            "vorp": [200.0, 100.0, 0.0, -50.0],
        }
    )

    helper = getattr(rankings, "add_zero_based_vorp_score", None)
    assert helper is not None, "add_zero_based_vorp_score helper is not implemented yet"

    result = helper(df).set_index("player_name_clean")

    assert result.loc["Elite Player", "vorp_score"] == 100.0
    assert result.loc["Mid Value", "vorp_score"] == 50.0
    assert result.loc["Replacement QB", "vorp_score"] == 0.0
    assert result.loc["Below Replacement QB", "vorp_score"] == 0.0


def test_qb_projection_score_uses_points_above_replacement():
    df = pd.DataFrame(
        {
            "player_name_clean": [
                "Elite QB",
                "Mid QB",
                "Replacement QB",
                "Below Replacement QB",
            ],
            "position": ["QB", "QB", "QB", "QB"],
            "projected_points": [430.0, 390.0, 350.0, 330.0],
            "replacement_points": [350.0, 350.0, 350.0, 350.0],
        }
    )

    helper = getattr(rankings, "add_position_projection_score", None)
    assert helper is not None, "add_position_projection_score helper is not implemented yet"

    result = helper(df).set_index("player_name_clean")

    assert result.loc["Elite QB", "projection_score"] == 100.0
    assert result.loc["Mid QB", "projection_score"] == 50.0
    assert result.loc["Replacement QB", "projection_score"] == 0.0
    assert result.loc["Below Replacement QB", "projection_score"] == 0.0
