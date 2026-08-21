import pandas as pd

from fantasy_draft_model import audit_war_room_rankings


def _board():
    return pd.DataFrame(
        [
            {
                "player_name_clean": "QB Alpha",
                "position": "QB",
                "draft_rank": 1,
                "brain_score": 90.0,
                "tier_scarcity_score": 100.0,
                "tier_pressure": 100.0,
                "vorp_score": 80.0,
                "vorp_pressure": 80.0,
            },
            {
                "player_name_clean": "RB Alpha",
                "position": "RB",
                "draft_rank": 2,
                "brain_score": 89.0,
                "tier_scarcity_score": 100.0,
                "tier_pressure": 100.0,
                "vorp_score": 80.0,
                "vorp_pressure": 80.0,
            },
            {
                "player_name_clean": "WR Alpha",
                "position": "WR",
                "draft_rank": 3,
                "brain_score": 88.0,
                "tier_scarcity_score": 100.0,
                "tier_pressure": 100.0,
                "vorp_score": 80.0,
                "vorp_pressure": 80.0,
            },
            {
                "player_name_clean": "TE Alpha",
                "position": "TE",
                "draft_rank": 4,
                "brain_score": 87.0,
                "tier_scarcity_score": 100.0,
                "tier_pressure": 100.0,
                "vorp_score": 80.0,
                "vorp_pressure": 80.0,
            },
            {
                "player_name_clean": "RB Beta",
                "position": "RB",
                "draft_rank": 5,
                "brain_score": 80.0,
                "tier_scarcity_score": 60.0,
                "tier_pressure": 60.0,
                "vorp_score": 60.0,
                "vorp_pressure": 60.0,
            },
        ]
    )


def test_position_demand_scarcity_audit_compares_top_board_share_to_lineup_demand():
    audit = audit_war_room_rankings.build_position_demand_scarcity_audit(
        _board(),
        replacement_ranks={"QB": 1, "RB": 3, "WR": 3, "TE": 1},
        top_n=4,
    )

    assert audit["position"].tolist() == ["QB", "RB", "WR", "TE"]
    assert audit["replacement_rank"].tolist() == [1, 3, 3, 1]
    assert audit["top_n_players"].tolist() == [1, 1, 1, 1]
    assert audit["demand_share"].round(3).tolist() == [0.125, 0.375, 0.375, 0.125]
    assert audit["top_n_share"].round(3).tolist() == [0.25, 0.25, 0.25, 0.25]
    assert audit["top_n_vs_demand_ratio"].round(3).tolist() == [2.0, 0.667, 0.667, 2.0]


def test_position_demand_scarcity_audit_exposes_scarcity_points_per_demand_slot():
    audit = audit_war_room_rankings.build_position_demand_scarcity_audit(
        _board(),
        replacement_ranks={"QB": 1, "RB": 3, "WR": 3, "TE": 1},
        top_n=4,
    ).set_index("position")

    assert audit.loc["QB", "top_n_brain_scarcity_points"] == 23.0
    assert audit.loc["TE", "top_n_brain_scarcity_points"] == 23.0
    assert audit.loc["RB", "top_n_brain_scarcity_points"] == 23.0
    assert audit.loc["WR", "top_n_brain_scarcity_points"] == 23.0

    assert audit.loc["QB", "scarcity_points_per_demand_slot"] == 23.0
    assert audit.loc["TE", "scarcity_points_per_demand_slot"] == 23.0
    assert round(audit.loc["RB", "scarcity_points_per_demand_slot"], 3) == 7.667
    assert round(audit.loc["WR", "scarcity_points_per_demand_slot"], 3) == 7.667
