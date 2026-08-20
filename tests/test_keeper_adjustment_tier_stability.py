import pandas as pd

from fantasy_draft_model.engines import keeper_adjustment_engine
from fantasy_draft_model.engines.tier_engine import calculate_tiers


def test_keeper_removal_preserves_base_tiers_boundaries_and_draft_rank(
    monkeypatch,
):
    base = calculate_tiers(pd.DataFrame([
        {
            "player_name_clean": "RB A",
            "position": "RB",
            "projected_points": 300.0,
            "vorp": 120.0,
            "edgescore": 90.0,
            "projection_confidence": 90.0,
        },
        {
            "player_name_clean": "RB B",
            "position": "RB",
            "projected_points": 280.0,
            "vorp": 100.0,
            "edgescore": 80.0,
            "projection_confidence": 90.0,
        },
        {
            "player_name_clean": "RB C",
            "position": "RB",
            "projected_points": 275.0,
            "vorp": 95.0,
            "edgescore": 75.0,
            "projection_confidence": 90.0,
        },
        {
            "player_name_clean": "RB D",
            "position": "RB",
            "projected_points": 270.0,
            "vorp": 90.0,
            "edgescore": 70.0,
            "projection_confidence": 90.0,
        },
        {
            "player_name_clean": "RB E",
            "position": "RB",
            "projected_points": 240.0,
            "vorp": 60.0,
            "edgescore": 60.0,
            "projection_confidence": 90.0,
        },
    ]))
    base["draft_rank"] = [1, 2, 3, 4, 5]
    expected = base.set_index("player_name_clean").loc[
        ["RB B", "RB D", "RB E"],
        [
            "tier",
            "tier_size",
            "tier_threshold",
            "tier_next_threshold",
            "tier_next_projection_drop",
            "tier_next_vorp_drop",
            "draft_rank",
        ],
    ]

    monkeypatch.setattr(
        keeper_adjustment_engine,
        "get_keeper_player_names",
        lambda league_name: ["RB A", "RB C"],
    )
    result = keeper_adjustment_engine.recalculate_after_keepers(
        base,
        "Test League",
    ).set_index("player_name_clean")

    pd.testing.assert_frame_equal(result[expected.columns], expected)
    assert result.loc["RB B", "tier_remaining"] == 2
    assert result.loc["RB D", "tier_remaining"] == 2
    assert result.loc["RB E", "tier_remaining"] == 1
    assert result.loc["RB B", "tier_scarcity_score"] == 54.64
    assert result.loc["RB E", "tier_scarcity_score"] == 42.0
