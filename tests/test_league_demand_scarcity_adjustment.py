import pandas as pd

from fantasy_draft_model.rankings import add_position_demand_metadata
from fantasy_draft_model.engines.tier_engine import add_live_tier_scarcity


def test_position_demand_metadata_uses_replacement_demand_with_damped_scaling():
    board = pd.DataFrame(
        [
            {"player_name_clean": "QB A", "position": "QB", "projected_points": 400.0},
            {"player_name_clean": "RB A", "position": "RB", "projected_points": 300.0},
            {"player_name_clean": "WR A", "position": "WR", "projected_points": 300.0},
            {"player_name_clean": "TE A", "position": "TE", "projected_points": 250.0},
        ]
    )

    result = add_position_demand_metadata(
        board,
        replacement_ranks={"QB": 12, "RB": 34, "WR": 38, "TE": 12},
    ).set_index("position")

    assert result.loc["QB", "position_replacement_rank"] == 12
    assert result.loc["RB", "position_replacement_rank"] == 34
    assert result.loc["WR", "position_replacement_rank"] == 38
    assert result.loc["TE", "position_replacement_rank"] == 12

    assert round(result.loc["QB", "position_demand_multiplier"], 3) == 0.707
    assert round(result.loc["RB", "position_demand_multiplier"], 3) == 1.190
    assert round(result.loc["WR", "position_demand_multiplier"], 3) == 1.250
    assert round(result.loc["TE", "position_demand_multiplier"], 3) == 0.707


def test_live_tier_scarcity_applies_position_demand_multiplier():
    board = pd.DataFrame(
        [
            {
                "player_name_clean": "QB A",
                "position": "QB",
                "tier": 1,
                "tier_next_threshold": 18.0,
                "tier_next_projection_drop": 36.0,
                "tier_next_vorp_drop": 36.0,
                "position_demand_multiplier": 0.70710678,
            },
            {
                "player_name_clean": "RB A",
                "position": "RB",
                "tier": 1,
                "tier_next_threshold": 14.0,
                "tier_next_projection_drop": 28.0,
                "tier_next_vorp_drop": 28.0,
                "position_demand_multiplier": 1.19023807,
            },
            {
                "player_name_clean": "WR A",
                "position": "WR",
                "tier": 1,
                "tier_next_threshold": 14.0,
                "tier_next_projection_drop": 28.0,
                "tier_next_vorp_drop": 28.0,
                "position_demand_multiplier": 1.25,
            },
            {
                "player_name_clean": "TE A",
                "position": "TE",
                "tier": 1,
                "tier_next_threshold": 12.0,
                "tier_next_projection_drop": 24.0,
                "tier_next_vorp_drop": 24.0,
                "position_demand_multiplier": 0.70710678,
            },
        ]
    )

    result = add_live_tier_scarcity(board).set_index("position")

    assert result.loc["QB", "raw_tier_scarcity_score"] == 100.0
    assert result.loc["RB", "raw_tier_scarcity_score"] == 100.0
    assert result.loc["WR", "raw_tier_scarcity_score"] == 100.0
    assert result.loc["TE", "raw_tier_scarcity_score"] == 100.0

    assert round(result.loc["QB", "tier_scarcity_score"], 2) == 70.71
    assert round(result.loc["RB", "tier_scarcity_score"], 2) == 100.0
    assert round(result.loc["WR", "tier_scarcity_score"], 2) == 100.0
    assert round(result.loc["TE", "tier_scarcity_score"], 2) == 70.71
