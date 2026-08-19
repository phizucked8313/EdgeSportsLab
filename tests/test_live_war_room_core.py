import importlib

import pandas as pd

from fantasy_draft_model.models.league_profile import get_league


def _war_room_module():
    return importlib.import_module("fantasy_draft_model.live_war_room")


def _empty_keepers():
    return pd.DataFrame(
        columns=[
            "league_name",
            "owner_team",
            "player_name",
            "keeper_type",
            "keeper_round",
        ]
    )


def _synthetic_keepers():
    return pd.DataFrame(
        [
            {
                "league_name": "Drunk Sundays",
                "owner_team": "BLKWDW'S",
                "player_name": "Ashton Jeanty",
                "keeper_type": "rookie",
                "keeper_round": 3,
            },
            {
                "league_name": "Drunk Sundays",
                "owner_team": "Parrots",
                "player_name": "Bijan Robinson",
                "keeper_type": "standard",
                "keeper_round": 15,
            },
        ]
    )


def test_canonical_league_profile_contains_user_team():
    drunk = get_league("Drunk Sundays")
    somewhat = get_league("Somewhat Related")

    assert drunk["user_team"] == "BLKWDW'S"
    assert somewhat["user_team"] == "Phizucked"


def test_resolve_league_accepts_league_key():
    war_room = _war_room_module()

    league = war_room.resolve_league("drunk_sundays")

    assert league["name"] == "Drunk Sundays"
    assert league["league_key"] == "drunk_sundays"
    assert league["user_team"] == "BLKWDW'S"


def test_initialize_and_reload_war_room_state(tmp_path, monkeypatch):
    war_room = _war_room_module()
    state_path = tmp_path / "war_room_state.json"
    monkeypatch.setattr(
        war_room,
        "load_keepers",
        lambda league_name=None: _empty_keepers(),
        raising=False,
    )

    state = war_room.initialize_war_room(
        "drunk_sundays",
        state_path=state_path,
    )

    assert state["schema_version"] == 1
    assert state["league_name"] == "Drunk Sundays"
    assert state["league_key"] == "drunk_sundays"
    assert state["user_team"] == "BLKWDW'S"
    assert state["team_count"] == 12
    assert state["draft_rounds"] == 15
    assert state["current_pick"] == 1
    assert state["manual_picks"] == []
    assert state["keeper_reservations"] == []
    assert state["processed_keeper_picks"] == []
    assert state_path.exists()

    reloaded = war_room.load_war_room_state(state_path)
    assert reloaded == state


def test_build_keeper_reservations_uses_snake_math():
    war_room = _war_room_module()
    league = war_room.resolve_league("drunk_sundays")

    reservations = war_room.build_keeper_reservations(
        league,
        _synthetic_keepers(),
    )
    by_name = {
        reservation["player_name"]: reservation
        for reservation in reservations
    }

    jeanty = by_name["Ashton Jeanty"]
    assert jeanty["pick_number"] == 33
    assert jeanty["round"] == 3
    assert jeanty["draft_slot"] == 9
    assert jeanty["fantasy_team"] == "BLKWDW'S"
    assert jeanty["keeper_type"] == "rookie"
    assert jeanty["keeper_round"] == 3

    bijan = by_name["Bijan Robinson"]
    assert bijan["pick_number"] == 169
    assert bijan["round"] == 15
    assert bijan["draft_slot"] == 1
    assert bijan["fantasy_team"] == "Parrots"


def test_initialize_loads_declared_keeper_reservations(tmp_path, monkeypatch):
    war_room = _war_room_module()
    state_path = tmp_path / "war_room_state.json"
    monkeypatch.setattr(
        war_room,
        "load_keepers",
        lambda league_name=None: _synthetic_keepers(),
        raising=False,
    )

    state = war_room.initialize_war_room(
        "drunk_sundays",
        state_path=state_path,
    )

    assert len(state["keeper_reservations"]) == 2
    assert {
        reservation["player_name"]
        for reservation in state["keeper_reservations"]
    } == {"Ashton Jeanty", "Bijan Robinson"}


def test_advance_keeper_slots_processes_reserved_pick_once():
    war_room = _war_room_module()
    league = war_room.resolve_league("drunk_sundays")
    reservation = war_room.build_keeper_reservations(
        league,
        _synthetic_keepers(),
    )[0]

    state = {
        "current_pick": reservation["pick_number"],
        "keeper_reservations": [reservation],
        "processed_keeper_picks": [],
    }

    war_room.advance_keeper_slots(state)

    assert state["current_pick"] == reservation["pick_number"] + 1
    assert state["processed_keeper_picks"] == [reservation["pick_number"]]

    war_room.advance_keeper_slots(state)

    assert state["current_pick"] == reservation["pick_number"] + 1
    assert state["processed_keeper_picks"] == [reservation["pick_number"]]
