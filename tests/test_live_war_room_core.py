import importlib

import pandas as pd
import pytest

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


def _player_row(name="Test Player"):
    return pd.Series(
        {
            "player_name_clean": name,
            "position": "WR",
            "team": "CLE",
            "bye_week": 10,
            "draft_rank": 42,
        }
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


def test_pick_context_uses_canonical_snake_order():
    war_room = _war_room_module()
    league = war_room.resolve_league("drunk_sundays")
    state = {
        "league_name": league["name"],
        "league_key": league["league_key"],
        "user_team": league["user_team"],
        "team_count": league["team_count"],
        "draft_rounds": league["draft_rounds"],
        "current_pick": 1,
    }

    context = war_room.get_pick_context(state)
    assert context["pick_number"] == 1
    assert context["round"] == 1
    assert context["draft_slot"] == 1
    assert context["fantasy_team"] == "Parrots"

    state["current_pick"] = 12
    context = war_room.get_pick_context(state)
    assert context["round"] == 1
    assert context["draft_slot"] == 12
    assert context["fantasy_team"] == "Hawk Tua"

    state["current_pick"] = 13
    context = war_room.get_pick_context(state)
    assert context["round"] == 2
    assert context["draft_slot"] == 12
    assert context["fantasy_team"] == "Hawk Tua"

    state["current_pick"] = 16
    context = war_room.get_pick_context(state)
    assert context["round"] == 2
    assert context["draft_slot"] == 9
    assert context["fantasy_team"] == "BLKWDW'S"


def test_record_manual_pick_assigns_team_metadata_and_persists(
    tmp_path,
    monkeypatch,
):
    war_room = _war_room_module()
    state_path = tmp_path / "war_room_state.json"
    monkeypatch.setattr(
        war_room,
        "load_keepers",
        lambda league_name=None: _empty_keepers(),
    )
    state = war_room.initialize_war_room(
        "drunk_sundays",
        state_path=state_path,
    )
    state["current_pick"] = 16

    war_room.record_manual_pick(
        state,
        _player_row("Manual Test WR"),
        state_path=state_path,
    )

    assert state["current_pick"] == 17
    assert len(state["manual_picks"]) == 1
    pick = state["manual_picks"][0]
    assert pick["player_name"] == "Manual Test WR"
    assert pick["position"] == "WR"
    assert pick["nfl_team"] == "CLE"
    assert pick["bye_week"] == 10
    assert pick["draft_rank"] == 42
    assert pick["fantasy_team"] == "BLKWDW'S"
    assert pick["pick_number"] == 16
    assert pick["round"] == 2
    assert pick["draft_slot"] == 9

    assert war_room.load_war_room_state(state_path) == state


def test_record_manual_pick_rejects_duplicate_without_advancing(
    tmp_path,
    monkeypatch,
):
    war_room = _war_room_module()
    state_path = tmp_path / "war_room_state.json"
    monkeypatch.setattr(
        war_room,
        "load_keepers",
        lambda league_name=None: _empty_keepers(),
    )
    state = war_room.initialize_war_room(
        "drunk_sundays",
        state_path=state_path,
    )
    player = _player_row("Duplicate Test WR")

    war_room.record_manual_pick(
        state,
        player,
        state_path=state_path,
    )
    current_pick = state["current_pick"]

    with pytest.raises(ValueError, match="already drafted"):
        war_room.record_manual_pick(
            state,
            player,
            state_path=state_path,
        )

    assert state["current_pick"] == current_pick
    assert len(state["manual_picks"]) == 1


def test_undo_last_manual_pick_restores_pick_and_persists(
    tmp_path,
    monkeypatch,
):
    war_room = _war_room_module()
    state_path = tmp_path / "war_room_state.json"
    monkeypatch.setattr(
        war_room,
        "load_keepers",
        lambda league_name=None: _empty_keepers(),
    )
    state = war_room.initialize_war_room(
        "drunk_sundays",
        state_path=state_path,
    )
    state["current_pick"] = 16
    war_room.record_manual_pick(
        state,
        _player_row("Undo Test WR"),
        state_path=state_path,
    )

    removed = war_room.undo_last_manual_pick(
        state,
        state_path=state_path,
    )

    assert removed["player_name"] == "Undo Test WR"
    assert state["manual_picks"] == []
    assert state["current_pick"] == 16
    assert war_room.load_war_room_state(state_path) == state


def test_undo_last_manual_pick_reopens_crossed_keeper_slot(
    tmp_path,
    monkeypatch,
):
    war_room = _war_room_module()
    state_path = tmp_path / "war_room_state.json"
    monkeypatch.setattr(
        war_room,
        "load_keepers",
        lambda league_name=None: _synthetic_keepers(),
    )
    state = war_room.initialize_war_room(
        "drunk_sundays",
        state_path=state_path,
    )
    state["current_pick"] = 32

    war_room.record_manual_pick(
        state,
        _player_row("Before Keeper WR"),
        state_path=state_path,
    )

    assert state["current_pick"] == 34
    assert 33 in state["processed_keeper_picks"]
    reservations_before = list(state["keeper_reservations"])

    war_room.undo_last_manual_pick(
        state,
        state_path=state_path,
    )

    assert state["current_pick"] == 32
    assert 33 not in state["processed_keeper_picks"]
    assert state["keeper_reservations"] == reservations_before


def test_undo_last_manual_pick_rejects_empty_history_without_mutation(
    tmp_path,
    monkeypatch,
):
    war_room = _war_room_module()
    state_path = tmp_path / "war_room_state.json"
    monkeypatch.setattr(
        war_room,
        "load_keepers",
        lambda league_name=None: _empty_keepers(),
    )
    state = war_room.initialize_war_room(
        "drunk_sundays",
        state_path=state_path,
    )
    before = dict(state)

    with pytest.raises(ValueError, match="No manual picks to undo"):
        war_room.undo_last_manual_pick(
            state,
            state_path=state_path,
        )

    assert state == before
    assert war_room.load_war_room_state(state_path) == state
