import pandas as pd

from fantasy_draft_model.engines.tier_engine import add_live_tier_scarcity


def test_late_singleton_is_capped_by_tier_depth():
    df = pd.DataFrame([
        {"player_name_clean": "RB Tier1", "position": "RB", "tier": 1, "tier_size": 1,
         "tier_threshold": 14.0, "tier_next_projection_drop": 14.0, "tier_next_vorp_drop": 10.0},
        {"player_name_clean": "RB Tier5", "position": "RB", "tier": 5, "tier_size": 1,
         "tier_threshold": 24.5, "tier_next_projection_drop": 24.5, "tier_next_vorp_drop": 20.0},
    ])
    result = add_live_tier_scarcity(df)
    scores = dict(zip(result["player_name_clean"], result["tier_scarcity_score"]))
    assert scores["RB Tier1"] == 100.0
    assert scores["RB Tier5"] == 40.0


def test_tier_remaining_uses_only_rows_still_on_available_board():
    df = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "tier": 2, "tier_size": 3,
         "tier_threshold": 17.5, "tier_next_projection_drop": 17.5, "tier_next_vorp_drop": 0.0},
        {"player_name_clean": "RB B", "position": "RB", "tier": 2, "tier_size": 3,
         "tier_threshold": 17.5, "tier_next_projection_drop": 17.5, "tier_next_vorp_drop": 0.0},
    ])
    result = add_live_tier_scarcity(df.iloc[[0]].copy())
    row = result.iloc[0]
    assert row["tier_remaining"] == 1
    assert row["tier"] == 2
    assert row["tier_scarcity_score"] == 85.0


def test_drop_pressure_uses_larger_of_projection_and_vorp_signal():
    df = pd.DataFrame([
        {"player_name_clean": "TE A", "position": "TE", "tier": 2, "tier_size": 2,
         "tier_threshold": 15.0, "tier_next_projection_drop": 6.0, "tier_next_vorp_drop": 15.0},
        {"player_name_clean": "TE B", "position": "TE", "tier": 2, "tier_size": 2,
         "tier_threshold": 15.0, "tier_next_projection_drop": 6.0, "tier_next_vorp_drop": 15.0},
    ])
    result = add_live_tier_scarcity(df)
    assert set(result["tier_remaining"]) == {2}
    assert set(result["tier_scarcity_score"]) == {59.5}
