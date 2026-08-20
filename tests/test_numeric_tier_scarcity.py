import pandas as pd

from fantasy_draft_model.engines.tier_engine import (
    add_live_tier_scarcity,
    add_tier_boundary_metadata,
    calculate_tiers,
)


def test_boundary_metadata_uses_next_tier_drop_and_zeros_final_tier():
    df = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "tier": 1,
         "projected_points": 300.0, "vorp": 140.0, "tier_drop": 0.0,
         "tier_vorp_drop": 0.0, "tier_threshold": 14.0},
        {"player_name_clean": "RB B", "position": "RB", "tier": 1,
         "projected_points": 290.0, "vorp": 130.0, "tier_drop": 10.0,
         "tier_vorp_drop": 10.0, "tier_threshold": 14.0},
        {"player_name_clean": "RB C", "position": "RB", "tier": 2,
         "projected_points": 270.0, "vorp": 110.0, "tier_drop": 20.0,
         "tier_vorp_drop": 20.0, "tier_threshold": 14.0},
        {"player_name_clean": "RB D", "position": "RB", "tier": 2,
         "projected_points": 265.0, "vorp": 105.0, "tier_drop": 5.0,
         "tier_vorp_drop": 5.0, "tier_threshold": 17.5},
        {"player_name_clean": "RB E", "position": "RB", "tier": 3,
         "projected_points": 240.0, "vorp": 80.0, "tier_drop": 25.0,
         "tier_vorp_drop": 25.0, "tier_threshold": 17.5},
    ])

    result = add_tier_boundary_metadata(df).set_index("player_name_clean")

    assert result.loc["RB A", "tier_next_projection_drop"] == 20.0
    assert result.loc["RB B", "tier_next_vorp_drop"] == 20.0
    assert result.loc["RB C", "tier_next_projection_drop"] == 25.0
    assert result.loc["RB D", "tier_next_vorp_drop"] == 25.0
    assert result.loc["RB E", "tier_next_projection_drop"] == 0.0
    assert result.loc["RB E", "tier_next_vorp_drop"] == 0.0
    assert result.loc["RB A", "tier_next_threshold"] == 14.0
    assert result.loc["RB C", "tier_next_threshold"] == 17.5
    assert result.loc["RB D", "tier_next_threshold"] == 17.5
    assert result.loc["RB E", "tier_next_threshold"] == 21.0


def test_calculate_tiers_includes_boundary_metadata_for_each_tier():
    df = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "projected_points": 300.0, "vorp": 140.0},
        {"player_name_clean": "RB B", "position": "RB", "projected_points": 280.0, "vorp": 120.0},
        {"player_name_clean": "RB C", "position": "RB", "projected_points": 250.0, "vorp": 90.0},
    ])

    result = calculate_tiers(df).set_index("player_name_clean")

    assert result.loc["RB A", "tier_next_projection_drop"] == 20.0
    assert result.loc["RB B", "tier_next_vorp_drop"] == 30.0
    assert result.loc["RB C", "tier_next_projection_drop"] == 0.0
    assert result.loc["RB C", "tier_next_vorp_drop"] == 0.0
    assert result.loc["RB A", "tier_next_threshold"] == 14.0
    assert result.loc["RB B", "tier_next_threshold"] == 17.5
    assert result.loc["RB C", "tier_next_threshold"] == 21.0
    assert "tier_status" not in result.columns


def test_full_tier_pipeline_keeps_unsupported_positions_tierless_and_neutral():
    df = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "projected_points": 300.0, "vorp": 140.0},
        {"player_name_clean": "RB B", "position": "RB", "projected_points": 280.0, "vorp": 120.0},
        {"player_name_clean": "K A", "position": "K", "projected_points": 130.0, "vorp": 0.0},
        {"player_name_clean": "DEF A", "position": "DEF", "projected_points": 120.0, "vorp": 0.0},
    ])

    result = calculate_tiers(df).set_index("player_name_clean")
    unsupported = result.loc[["K A", "DEF A"]]

    assert result.loc["RB A", "tier"] == 1
    assert unsupported["tier"].isna().all()
    assert unsupported["tier_remaining"].eq(0).all()
    assert unsupported["tier_scarcity_score"].eq(0.0).all()


def test_live_scarcity_normalizes_invalid_tiers_to_nullable_integer_and_neutral():
    df = pd.DataFrame([
        {
            "player_name_clean": "RB Valid",
            "position": "RB",
            "tier": 1,
            "tier_size": 1,
            "tier_next_threshold": 14.0,
            "tier_next_projection_drop": 14.0,
            "tier_next_vorp_drop": 0.0,
        },
        {
            "player_name_clean": "K Legacy",
            "position": "K",
            "tier": 0,
            "tier_size": 1,
            "tier_next_threshold": 15.0,
            "tier_next_projection_drop": 30.0,
            "tier_next_vorp_drop": 30.0,
        },
        {
            "player_name_clean": "DEF Negative",
            "position": "DEF",
            "tier": -1,
            "tier_size": 1,
            "tier_next_threshold": 15.0,
            "tier_next_projection_drop": 30.0,
            "tier_next_vorp_drop": 30.0,
        },
        {
            "player_name_clean": "RB Invalid Zero",
            "position": "RB",
            "tier": 0,
            "tier_size": 1,
            "tier_next_threshold": 14.0,
            "tier_next_projection_drop": 28.0,
            "tier_next_vorp_drop": 28.0,
        },
        {
            "player_name_clean": "TE Invalid Negative",
            "position": "TE",
            "tier": -2,
            "tier_size": 1,
            "tier_next_threshold": 12.0,
            "tier_next_projection_drop": 24.0,
            "tier_next_vorp_drop": 24.0,
        },
        {
            "player_name_clean": "K Invalid Positive",
            "position": "K",
            "tier": 3,
            "tier_size": 1,
            "tier_next_threshold": 15.0,
            "tier_next_projection_drop": 30.0,
            "tier_next_vorp_drop": 30.0,
        },
    ])

    result = add_live_tier_scarcity(df).set_index("player_name_clean")
    invalid_names = [
        "K Legacy",
        "DEF Negative",
        "RB Invalid Zero",
        "TE Invalid Negative",
        "K Invalid Positive",
    ]

    assert result["tier"].dtype == pd.Int64Dtype()
    assert result.loc["RB Valid", "tier"] == 1
    assert result.loc[invalid_names, "tier"].isna().all()
    assert result.loc[invalid_names, "tier_remaining"].eq(0).all()
    assert result.loc[invalid_names, "tier_scarcity_score"].eq(0.0).all()


def test_live_scarcity_handles_empty_board_with_nullable_tier_dtype():
    result = add_live_tier_scarcity(pd.DataFrame(columns=["position", "tier"]))

    assert result.empty
    assert result["tier"].dtype == pd.Int64Dtype()
    assert "tier_remaining" in result.columns
    assert "tier_scarcity_score" in result.columns


def test_late_singleton_is_capped_by_tier_depth():
    df = pd.DataFrame([
        {"player_name_clean": "RB Tier1", "position": "RB", "tier": 1, "tier_size": 1,
         "tier_next_threshold": 14.0, "tier_next_projection_drop": 14.0,
         "tier_next_vorp_drop": 10.0},
        {"player_name_clean": "RB Tier5", "position": "RB", "tier": 5, "tier_size": 1,
         "tier_next_threshold": 24.5, "tier_next_projection_drop": 24.5,
         "tier_next_vorp_drop": 20.0},
    ])
    result = add_live_tier_scarcity(df)
    scores = dict(zip(result["player_name_clean"], result["tier_scarcity_score"]))
    assert scores["RB Tier1"] == 80.0
    assert scores["RB Tier5"] == 32.0


def test_tier_remaining_uses_only_rows_still_on_available_board():
    df = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "tier": 2, "tier_size": 3,
         "tier_next_threshold": 17.5, "tier_next_projection_drop": 17.5,
         "tier_next_vorp_drop": 0.0},
        {"player_name_clean": "RB B", "position": "RB", "tier": 2, "tier_size": 3,
         "tier_next_threshold": 17.5, "tier_next_projection_drop": 17.5,
         "tier_next_vorp_drop": 0.0},
    ])
    result = add_live_tier_scarcity(df.iloc[[0]].copy())
    row = result.iloc[0]
    assert row["tier_remaining"] == 1
    assert row["tier"] == 2
    assert row["tier_scarcity_score"] == 68.0


def test_drop_pressure_uses_larger_of_projection_and_vorp_signal():
    df = pd.DataFrame([
        {"player_name_clean": "TE A", "position": "TE", "tier": 2, "tier_size": 2,
         "tier_next_threshold": 15.0, "tier_next_projection_drop": 6.0,
         "tier_next_vorp_drop": 15.0},
        {"player_name_clean": "TE B", "position": "TE", "tier": 2, "tier_size": 2,
         "tier_next_threshold": 15.0, "tier_next_projection_drop": 6.0,
         "tier_next_vorp_drop": 15.0},
    ])
    result = add_live_tier_scarcity(df)
    assert set(result["tier_remaining"]) == {2}
    assert set(result["tier_scarcity_score"]) == {42.5}


def test_drop_pressure_increases_from_threshold_to_double_threshold():
    df = pd.DataFrame([
        {"player_name_clean": "RB Threshold", "position": "RB", "tier": 1,
         "tier_size": 1, "tier_next_threshold": 14.0,
         "tier_next_projection_drop": 14.0, "tier_next_vorp_drop": 0.0},
        {"player_name_clean": "WR Double", "position": "WR", "tier": 1,
         "tier_size": 1, "tier_next_threshold": 14.0,
         "tier_next_projection_drop": 28.0, "tier_next_vorp_drop": 0.0},
    ])

    result = add_live_tier_scarcity(df).set_index("player_name_clean")

    assert result.loc["RB Threshold", "tier_scarcity_score"] == 80.0
    assert result.loc["WR Double", "tier_scarcity_score"] == 100.0


def test_negative_boundary_gaps_are_clipped_to_neutral_drop_pressure():
    df = pd.DataFrame([{
        "player_name_clean": "RB A",
        "position": "RB",
        "tier": 1,
        "tier_size": 1,
        "tier_next_threshold": 14.0,
        "tier_next_projection_drop": -140.0,
        "tier_next_vorp_drop": -70.0,
    }])

    result = add_live_tier_scarcity(df).iloc[0]

    assert result["tier_scarcity_score"] == 60.0
    assert 0.0 <= result["tier_scarcity_score"] <= 100.0


def test_non_finite_boundary_gap_is_neutral():
    df = pd.DataFrame([{
        "player_name_clean": "RB A",
        "position": "RB",
        "tier": 1,
        "tier_size": 1,
        "tier_next_threshold": 14.0,
        "tier_next_projection_drop": float("inf"),
        "tier_next_vorp_drop": float("nan"),
    }])

    result = add_live_tier_scarcity(df).iloc[0]

    assert result["tier_scarcity_score"] == 60.0
