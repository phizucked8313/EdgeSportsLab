import pandas as pd

from fantasy_draft_model.engines.tier_engine import (
    assign_position_tiers,
    get_tier_threshold,
)


def test_tier_threshold_progression_uses_position_base_and_depth_multiplier():
    assert get_tier_threshold("RB", 1) == 14.0
    assert get_tier_threshold("RB", 2) == 17.5
    assert get_tier_threshold("RB", 3) == 21.0
    assert get_tier_threshold("RB", 4) == 24.5
    assert get_tier_threshold("RB", 8) == 24.5
    assert get_tier_threshold("TE", 1) == 12.0
    assert get_tier_threshold("QB", 2) == 22.5


def test_position_tiers_restart_at_one_and_use_progressive_boundary():
    df = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "projected_points": 300.0, "vorp": 140.0},
        {"player_name_clean": "RB B", "position": "RB", "projected_points": 287.0, "vorp": 127.0},
        {"player_name_clean": "RB C", "position": "RB", "projected_points": 273.0, "vorp": 113.0},
        {"player_name_clean": "RB D", "position": "RB", "projected_points": 256.0, "vorp": 96.0},
        {"player_name_clean": "RB E", "position": "RB", "projected_points": 238.5, "vorp": 78.5},
        {"player_name_clean": "WR A", "position": "WR", "projected_points": 320.0, "vorp": 150.0},
        {"player_name_clean": "WR B", "position": "WR", "projected_points": 306.0, "vorp": 136.0},
    ])

    result = assign_position_tiers(df)
    tiers = dict(zip(result["player_name_clean"], result["tier"]))

    assert tiers["RB A"] == 1
    assert tiers["RB B"] == 1
    assert tiers["RB C"] == 2
    assert tiers["RB D"] == 2
    assert tiers["RB E"] == 3
    assert tiers["WR A"] == 1
    assert tiers["WR B"] == 2


def test_vorp_gap_can_create_tier_even_when_projection_gap_does_not():
    df = pd.DataFrame([
        {"player_name_clean": "TE A", "position": "TE", "projected_points": 280.0, "vorp": 120.0},
        {"player_name_clean": "TE B", "position": "TE", "projected_points": 271.0, "vorp": 107.0},
    ])
    result = assign_position_tiers(df)
    te_b = result[result["player_name_clean"] == "TE B"].iloc[0]
    assert te_b["tier"] == 2
    assert te_b["tier_drop"] == 9.0
    assert te_b["tier_vorp_drop"] == 13.0
    assert te_b["tier_threshold"] == 12.0
