import pandas as pd

from fantasy_draft_model.ui import draft_war_room


def _rankings():
    return pd.DataFrame(
        [
            {
                "player_name_clean": "Ashton Jeanty",
                "position": "RB",
                "team": "LV",
                "draft_rank": 5,
            },
            {
                "player_name_clean": "TreVeyon Henderson",
                "position": "RB",
                "team": "NE",
                "draft_rank": 28,
            },
        ]
    )


def _state():
    return {
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": 1,
        "manual_picks": [],
        "keeper_reservations": [
            {
                "pick_number": 33,
                "round": 3,
                "fantasy_team": "BLKWDW'S",
                "player_name": "Ashton Jeanty",
                "position": None,
                "nfl_team": None,
            },
            {
                "pick_number": 177,
                "round": 15,
                "fantasy_team": "BLKWDW'S",
                "player_name": "TreVeyon Henderson",
                "position": None,
                "nfl_team": None,
            },
        ],
    }


def test_enrich_user_roster_metadata_fills_missing_keeper_position_and_team():
    roster = draft_war_room.build_user_roster(_state())

    enriched = draft_war_room.enrich_user_roster_metadata(roster, _rankings())

    assert enriched["player_name"].tolist() == [
        "Ashton Jeanty",
        "TreVeyon Henderson",
    ]
    assert enriched["position"].tolist() == ["RB", "RB"]
    assert enriched["nfl_team"].tolist() == ["LV", "NE"]


def test_build_war_room_snapshot_uses_enriched_keeper_metadata_without_mutating_state():
    state = _state()

    snapshot = draft_war_room.build_war_room_snapshot(_rankings(), state)

    assert snapshot["roster"]["position"].tolist() == ["RB", "RB"]
    assert snapshot["roster"]["nfl_team"].tolist() == ["LV", "NE"]
    assert state["keeper_reservations"][0]["position"] is None
    assert state["keeper_reservations"][0]["nfl_team"] is None
