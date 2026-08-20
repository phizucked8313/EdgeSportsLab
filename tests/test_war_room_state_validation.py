import copy

import pytest

from fantasy_draft_model.war_room_state import (
    StateValidationError,
    migrate_legacy_state,
    validate_war_room_state,
)


REQUIRED_FIELDS = [
    "schema_version",
    "draft_id",
    "created_at",
    "updated_at",
    "status",
    "total_picks",
    "league_name",
    "league_key",
    "user_team",
    "team_count",
    "draft_rounds",
    "current_pick",
    "manual_picks",
    "keeper_reservations",
    "processed_keeper_picks",
]


def _manual_pick(pick_number, player_name=None):
    round_number = ((pick_number - 1) // 12) + 1
    pick_in_round = ((pick_number - 1) % 12) + 1
    draft_slot = pick_in_round if round_number % 2 else 13 - pick_in_round
    draft_order = [
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
    return {
        "player_name": player_name or f"Player {pick_number}",
        "position": "WR",
        "nfl_team": "CLE",
        "bye_week": 10,
        "draft_rank": pick_number,
        "fantasy_team": draft_order[draft_slot - 1],
        "pick_number": pick_number,
        "round": round_number,
        "draft_slot": draft_slot,
    }


def _keeper_reservation(pick_number=1, player_name="Keeper One"):
    pick = _manual_pick(pick_number, player_name)
    return {
        "pick_number": pick_number,
        "round": pick["round"],
        "draft_slot": pick["draft_slot"],
        "fantasy_team": pick["fantasy_team"],
        "player_name": player_name,
        "keeper_type": "rookie",
        "keeper_round": pick["round"],
    }


def _canonical_state(current_pick=1):
    return {
        "schema_version": 2,
        "draft_id": "draft-test-1",
        "created_at": "2026-08-20T12:00:00+00:00",
        "updated_at": "2026-08-20T12:00:00+00:00",
        "status": "complete" if current_pick == 181 else "active",
        "total_picks": 180,
        "league_name": "Drunk Sundays",
        "league_key": "drunk_sundays",
        "user_team": "BLKWDW'S",
        "team_count": 12,
        "draft_rounds": 15,
        "current_pick": current_pick,
        "manual_picks": [_manual_pick(pick) for pick in range(1, current_pick)],
        "keeper_reservations": [],
        "processed_keeper_picks": [],
    }


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_validation_rejects_each_missing_required_field(field):
    state = _canonical_state()
    del state[field]

    with pytest.raises(StateValidationError, match=field):
        validate_war_room_state(state)


def test_validation_accepts_canonical_state_unchanged():
    state = _canonical_state()

    assert validate_war_room_state(state) is state


def test_validation_rejects_noncanonical_league_metadata():
    state = _canonical_state()
    state["team_count"] = 10

    with pytest.raises(StateValidationError, match="team_count"):
        validate_war_room_state(state)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", ["active"]),
        ("status", {"value": "active"}),
        ("league_key", ["drunk_sundays"]),
        ("league_key", {"value": "drunk_sundays"}),
        ("league_name", ["Drunk Sundays"]),
        ("league_name", {"value": "Drunk Sundays"}),
    ],
)
def test_validation_aggregates_wrong_shaped_json_fields(field, value):
    state = _canonical_state()
    state[field] = value
    if field == "league_name":
        state["league_key"] = None

    with pytest.raises(StateValidationError, match=field):
        validate_war_room_state(state)


def test_validation_rejects_duplicate_manual_pick_numbers():
    state = _canonical_state(current_pick=3)
    state["manual_picks"][1]["pick_number"] = 1

    with pytest.raises(StateValidationError, match="duplicate manual pick"):
        validate_war_room_state(state)


def test_validation_rejects_duplicate_player_names_case_insensitively():
    state = _canonical_state(current_pick=3)
    state["manual_picks"][1]["player_name"] = " PLAYER 1 "

    with pytest.raises(StateValidationError, match="duplicate player"):
        validate_war_room_state(state)


def test_validation_rejects_manual_pick_in_keeper_slot():
    state = _canonical_state(current_pick=2)
    reservation = _keeper_reservation()
    state["keeper_reservations"] = [reservation]

    with pytest.raises(StateValidationError, match="keeper slot"):
        validate_war_room_state(state, keeper_reservations=[reservation])


@pytest.mark.parametrize(
    ("field", "value"),
    [("fantasy_team", "Wrong Team"), ("round", 2), ("draft_slot", 12)],
)
def test_validation_rejects_wrong_manual_snake_metadata(field, value):
    state = _canonical_state(current_pick=2)
    state["manual_picks"][0][field] = value

    with pytest.raises(StateValidationError, match=field):
        validate_war_room_state(state)


def test_validation_rejects_keeper_reservations_different_from_canonical_input():
    reservation = _keeper_reservation()
    state = _canonical_state()
    state["keeper_reservations"] = [copy.deepcopy(reservation)]
    state["keeper_reservations"][0]["fantasy_team"] = "Wrong Team"

    with pytest.raises(StateValidationError, match="keeper_reservations"):
        validate_war_room_state(state, keeper_reservations=[reservation])


def test_validation_rejects_processed_pick_that_is_not_a_declared_keeper():
    state = _canonical_state(current_pick=2)
    state["processed_keeper_picks"] = [1]

    with pytest.raises(StateValidationError, match="processed keeper pick"):
        validate_war_room_state(state)


def test_validation_rejects_gap_before_current_pick():
    state = _canonical_state(current_pick=3)
    state["manual_picks"] = state["manual_picks"][:1]

    with pytest.raises(StateValidationError, match="accounted"):
        validate_war_room_state(state)


def test_validation_rejects_recorded_pick_at_or_after_current_pick():
    state = _canonical_state(current_pick=2)
    state["manual_picks"] = [_manual_pick(2)]

    with pytest.raises(StateValidationError, match="at or after current_pick"):
        validate_war_room_state(state)


@pytest.mark.parametrize("status", ["paused", "complete"])
def test_validation_rejects_invalid_or_inconsistent_status(status):
    state = _canonical_state()
    state["status"] = status

    with pytest.raises(StateValidationError, match="status"):
        validate_war_room_state(state)


@pytest.mark.parametrize("current_pick", [0, 182])
def test_validation_rejects_current_pick_outside_draft_bounds(current_pick):
    state = _canonical_state()
    state["current_pick"] = current_pick

    with pytest.raises(StateValidationError, match="current_pick"):
        validate_war_room_state(state)


def test_migrate_legacy_state_returns_valid_copy_without_mutating_input():
    legacy = _canonical_state()
    for field in (
        "draft_id",
        "created_at",
        "updated_at",
        "status",
        "total_picks",
    ):
        del legacy[field]
    legacy["schema_version"] = 1
    before = copy.deepcopy(legacy)

    migrated = migrate_legacy_state(legacy)

    assert legacy == before
    assert migrated["schema_version"] == 2
    assert migrated["draft_id"]
    assert migrated["created_at"].endswith("+00:00")
    assert migrated["updated_at"].endswith("+00:00")
    assert migrated["status"] == "active"
    assert migrated["total_picks"] == 180
    assert validate_war_room_state(migrated) is migrated
