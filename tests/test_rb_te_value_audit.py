import pandas as pd

from fantasy_draft_model import audit_war_room_rankings


def _board():
    return pd.DataFrame(
        [
            {
                "player_name_clean": "RB Alpha",
                "position": "RB",
                "draft_rank": 5,
                "position_rank_label": "RB1",
                "projected_points": 330.0,
                "replacement_points": 210.0,
                "vorp": 120.0,
                "vorp_score": 75.0,
                "vorp_pressure": 80.0,
                "tier_status": "SMALL TIER",
                "tier_scarcity_score": 80.0,
                "tier_pressure": 85.0,
                "draft_score": 82.0,
                "pressure_score": 83.0,
                "brain_score": 84.0,
                "brain_recommendation": "DRAFT NOW",
            },
            {
                "player_name_clean": "RB Beta",
                "position": "RB",
                "draft_rank": 11,
                "position_rank_label": "RB2",
                "projected_points": 300.0,
                "replacement_points": 210.0,
                "vorp": 90.0,
                "vorp_score": 56.25,
                "vorp_pressure": 60.0,
                "tier_status": "LIMITED TIER",
                "tier_scarcity_score": 60.0,
                "tier_pressure": 60.0,
                "draft_score": 72.0,
                "pressure_score": 68.0,
                "brain_score": 73.0,
                "brain_recommendation": "STRONG TARGET",
            },
            {
                "player_name_clean": "RB Replacement",
                "position": "RB",
                "draft_rank": 40,
                "position_rank_label": "RB3",
                "projected_points": 210.0,
                "replacement_points": 210.0,
                "vorp": 0.0,
                "vorp_score": 0.0,
                "vorp_pressure": 0.0,
                "tier_status": "DEPTH AVAILABLE",
                "tier_scarcity_score": 35.0,
                "tier_pressure": 30.0,
                "draft_score": 45.0,
                "pressure_score": 30.0,
                "brain_score": 44.0,
                "brain_recommendation": "WAIT",
            },
            {
                "player_name_clean": "TE Alpha",
                "position": "TE",
                "draft_rank": 9,
                "position_rank_label": "TE1",
                "projected_points": 350.0,
                "replacement_points": 200.0,
                "vorp": 150.0,
                "vorp_score": 93.75,
                "vorp_pressure": 100.0,
                "tier_status": "ELITE SOLO TIER",
                "tier_scarcity_score": 100.0,
                "tier_pressure": 100.0,
                "draft_score": 84.0,
                "pressure_score": 80.0,
                "brain_score": 85.0,
                "brain_recommendation": "DRAFT NOW",
            },
            {
                "player_name_clean": "TE Replacement",
                "position": "TE",
                "draft_rank": 60,
                "position_rank_label": "TE2",
                "projected_points": 200.0,
                "replacement_points": 200.0,
                "vorp": 0.0,
                "vorp_score": 0.0,
                "vorp_pressure": 0.0,
                "tier_status": "DEPTH AVAILABLE",
                "tier_scarcity_score": 35.0,
                "tier_pressure": 30.0,
                "draft_score": 42.0,
                "pressure_score": 25.0,
                "brain_score": 40.0,
                "brain_recommendation": "WAIT",
            },
        ]
    )


def test_position_value_audit_exposes_replacement_demand_and_multipath_value():
    audit = audit_war_room_rankings.build_position_value_audit(
        _board(),
        "RB",
        replacement_rank=3,
    )

    assert audit["player_name_clean"].tolist() == [
        "RB Alpha",
        "RB Beta",
        "RB Replacement",
    ]
    assert set(audit["position_replacement_rank"]) == {3}
    assert set(audit["players_at_or_above_replacement"]) == {3}

    top = audit.iloc[0]
    assert top["brain_vorp_total"] == 15.65
    assert top["brain_scarcity_total"] == 18.7
    assert top["brain_vorp_and_scarcity_total"] == 34.35


def test_rb_te_comparison_places_both_positions_side_by_side_with_demand_context():
    comparison = audit_war_room_rankings.build_rb_te_value_comparison(
        _board(),
        replacement_ranks={"RB": 3, "TE": 2},
        top_n=2,
    )

    assert comparison["position"].tolist() == ["TE", "RB", "RB", "TE"]
    assert comparison["player_name_clean"].tolist() == [
        "TE Alpha",
        "RB Alpha",
        "RB Beta",
        "TE Replacement",
    ]

    rb_rows = comparison[comparison["position"] == "RB"]
    te_rows = comparison[comparison["position"] == "TE"]
    assert set(rb_rows["position_replacement_rank"]) == {3}
    assert set(te_rows["position_replacement_rank"]) == {2}
    assert set(rb_rows["players_at_or_above_replacement"]) == {3}
    assert set(te_rows["players_at_or_above_replacement"]) == {2}
