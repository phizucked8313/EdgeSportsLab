import pandas as pd

from fantasy_draft_model.engines.tier_engine import add_live_tier_scarcity


def _broad_rb_tier(*, remaining_replacement_demand):
    return pd.DataFrame(
        [
            {
                "player_name_clean": f"RB {index}",
                "position": "RB",
                "tier": 4,
                "projected_points": 260.0 - index,
                "vorp": 80.0 - index,
                "tier_next_threshold": 24.5,
                "tier_next_projection_drop": 0.0,
                "tier_next_vorp_drop": 0.0,
                "position_replacement_rank": 14,
                "position_remaining_replacement_demand": remaining_replacement_demand,
            }
            for index in range(1, 5)
        ]
    )


def test_depleted_replacement_pool_increases_live_scarcity_even_inside_same_broad_tier():
    full_pool = add_live_tier_scarcity(
        _broad_rb_tier(remaining_replacement_demand=14)
    )
    depleted_pool = add_live_tier_scarcity(
        _broad_rb_tier(remaining_replacement_demand=2)
    )

    assert depleted_pool["tier_scarcity_score"].iloc[0] > full_pool[
        "tier_scarcity_score"
    ].iloc[0]
