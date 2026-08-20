import pandas as pd

from fantasy_draft_model import audit_war_room_rankings


def _board():
    return pd.DataFrame(
        [
            {
                "player_name_clean": "Trey McBride",
                "position": "TE",
                "draft_rank": 9,
                "position_rank_label": "TE1",
                "custom_points_per_game": 19.2,
                "baseline_projection": 326.4,
                "targets_per_game": 9.0,
                "target_share": 0.28,
                "opportunity_score": 91.0,
                "opportunity_multiplier": 1.082,
                "injury_multiplier": 0.99,
                "projected_points": 350.41,
                "tier": 1,
                "tier_size": 1,
                "tier_drop": 0.0,
                "tier_remaining": 1,
                "tier_scarcity_score": 100.0,
                "tier_next_projection_drop": 18.0,
                "tier_next_vorp_drop": 15.0,
                "brain_score": 83.9,
            },
            {
                "player_name_clean": "Brock Bowers",
                "position": "TE",
                "draft_rank": 18,
                "position_rank_label": "TE3",
                "custom_points_per_game": 15.1,
                "baseline_projection": 256.7,
                "targets_per_game": 7.2,
                "target_share": 0.22,
                "opportunity_score": 78.0,
                "opportunity_multiplier": 1.056,
                "injury_multiplier": 0.99,
                "projected_points": 274.66,
                "tier": 4,
                "tier_size": 3,
                "tier_drop": 4.1,
                "tier_remaining": 3,
                "tier_scarcity_score": 31.17,
                "tier_next_projection_drop": 12.0,
                "tier_next_vorp_drop": 10.0,
                "brain_score": 62.5,
            },
            {
                "player_name_clean": "De'Von Achane",
                "position": "RB",
                "draft_rank": 8,
                "position_rank_label": "RB5",
                "custom_points_per_game": 20.6,
                "baseline_projection": 350.2,
                "targets_per_game": 4.8,
                "target_share": 0.16,
                "opportunity_score": 86.0,
                "opportunity_multiplier": 1.072,
                "injury_multiplier": 0.98,
                "projected_points": 390.93,
                "tier": 4,
                "tier_size": 1,
                "tier_drop": 18.5,
                "tier_remaining": 1,
                "tier_scarcity_score": 55.0,
                "tier_next_projection_drop": 18.5,
                "tier_next_vorp_drop": 17.0,
                "brain_score": 83.4,
            },
            {
                "player_name_clean": "Derrick Henry",
                "position": "RB",
                "draft_rank": 14,
                "position_rank_label": "RB7",
                "custom_points_per_game": 17.4,
                "baseline_projection": 295.8,
                "targets_per_game": 1.6,
                "target_share": 0.05,
                "opportunity_score": 72.0,
                "opportunity_multiplier": 1.044,
                "injury_multiplier": 0.99,
                "projected_points": 326.95,
                "tier": 6,
                "tier_size": 1,
                "tier_drop": 17.2,
                "tier_remaining": 1,
                "tier_scarcity_score": 40.0,
                "tier_next_projection_drop": 17.2,
                "tier_next_vorp_drop": 14.0,
                "brain_score": 74.3,
            },
        ]
    )


def test_projection_component_audit_surfaces_inputs_for_named_players_without_mutation():
    board = _board()
    before = board.copy(deep=True)

    audit = audit_war_room_rankings.build_projection_component_audit(
        board,
        ["Trey McBride", "Brock Bowers", "De'Von Achane"],
    )

    assert audit["player_name_clean"].tolist() == [
        "Trey McBride",
        "Brock Bowers",
        "De'Von Achane",
    ]
    assert audit.columns.tolist() == [
        "player_name_clean",
        "position",
        "draft_rank",
        "position_rank_label",
        "custom_points_per_game",
        "baseline_projection",
        "targets_per_game",
        "target_share",
        "opportunity_score",
        "opportunity_multiplier",
        "injury_multiplier",
        "projected_points",
        "projection_change_from_baseline",
        "tier",
        "tier_size",
        "tier_drop",
        "tier_remaining",
        "tier_scarcity_score",
        "tier_next_projection_drop",
        "tier_next_vorp_drop",
        "late_singleton_tier",
        "brain_score",
    ]
    assert audit.loc[0, "projection_change_from_baseline"] == 24.01
    assert audit.loc[0, "late_singleton_tier"] == False
    pd.testing.assert_frame_equal(board, before)


def test_late_singleton_tier_flag_distinguishes_true_tier_one_from_isolated_later_tiers():
    audit = audit_war_room_rankings.build_projection_component_audit(
        _board(),
        ["Trey McBride", "De'Von Achane", "Derrick Henry"],
    )

    flags = dict(zip(audit["player_name_clean"], audit["late_singleton_tier"]))
    assert flags == {
        "Trey McBride": False,
        "De'Von Achane": True,
        "Derrick Henry": True,
    }
