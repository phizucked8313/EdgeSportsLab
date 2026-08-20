import pandas as pd

from fantasy_draft_model import audit_war_room_rankings
from fantasy_draft_model.live_war_room import get_pick_context
from fantasy_draft_model.models.league_profile import get_league


def _state_at_pick(pick_number):
    return {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": pick_number,
        "manual_picks": [],
        "keeper_reservations": [],
        "processed_keeper_picks": [],
    }


def test_drunk_sundays_only_swaps_slots_seven_and_eight():
    draft_order = get_league("Drunk Sundays")["draft_order"]

    assert draft_order == [
        "Parrots",
        "Go Time",
        "Hashbrownies",
        "The Bird Is The Word",
        "Tez Swagg",
        "Diamonds Forever Inn The House",
        "Long & Deep",
        "Only Here To Beat My Husband",
        "BLKWDW'S",
        "Door Dash At 2AM",
        "It's Geoffrey James Beeitch",
        "Hawk Tua",
    ]


def test_corrected_slots_own_the_right_round_one_and_round_two_picks():
    assert get_pick_context(_state_at_pick(7))["fantasy_team"] == "Long & Deep"
    assert get_pick_context(_state_at_pick(8))["fantasy_team"] == "Only Here To Beat My Husband"

    # Snake reversal: slot 8 picks before slot 7 in round 2.
    assert get_pick_context(_state_at_pick(17))["fantasy_team"] == "Only Here To Beat My Husband"
    assert get_pick_context(_state_at_pick(18))["fantasy_team"] == "Long & Deep"

    assert get_pick_context(_state_at_pick(9))["fantasy_team"] == "BLKWDW'S"


def test_te_audit_exposes_duplicate_vorp_and_scarcity_paths_into_brain_score():
    board = pd.DataFrame(
        [
            {
                "player_name_clean": "Elite TE",
                "position": "TE",
                "draft_rank": 8,
                "position_rank_label": "TE1",
                "projected_points": 300.0,
                "replacement_points": 180.0,
                "vorp": 120.0,
                "vorp_score": 80.0,
                "vorp_pressure": 90.0,
                "projection_score": 95.0,
                "tier_scarcity_score": 100.0,
                "tier_pressure": 100.0,
                "draft_score": 82.0,
                "pressure_score": 88.0,
                "brain_score": 86.0,
                "brain_recommendation": "DRAFT NOW",
            },
            {
                "player_name_clean": "Top WR",
                "position": "WR",
                "draft_rank": 7,
                "position_rank_label": "WR4",
                "projected_points": 340.0,
                "replacement_points": 210.0,
                "vorp": 130.0,
                "vorp_score": 85.0,
                "vorp_pressure": 95.0,
                "projection_score": 90.0,
                "tier_scarcity_score": 80.0,
                "tier_pressure": 85.0,
                "draft_score": 84.0,
                "pressure_score": 86.0,
                "brain_score": 84.0,
                "brain_recommendation": "DRAFT NOW",
            },
        ]
    )

    audit = audit_war_room_rankings.build_te_ranking_audit(board)

    assert audit["player_name_clean"].tolist() == ["Elite TE"]
    row = audit.iloc[0]

    # VORP reaches Brain directly, through Draft Score, and through Pressure.
    assert row["brain_vorp_direct"] == 8.0
    assert row["brain_vorp_via_draft_score"] == 5.6
    assert row["brain_vorp_via_pressure"] == 3.6
    assert row["brain_vorp_total"] == 17.2

    # Tier scarcity also reaches Brain directly, through Draft Score, and through Pressure.
    assert row["brain_scarcity_direct"] == 15.0
    assert row["brain_scarcity_via_draft_score"] == 2.0
    assert row["brain_scarcity_via_pressure"] == 6.0
    assert row["brain_scarcity_total"] == 23.0
