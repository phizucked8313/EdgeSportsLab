import importlib

from fantasy_draft_model.models.league_profile import get_league


def _war_room_module():
    return importlib.import_module("fantasy_draft_model.live_war_room")


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


def test_initialize_and_reload_war_room_state(tmp_path):
    war_room = _war_room_module()
    state_path = tmp_path / "war_room_state.json"

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
