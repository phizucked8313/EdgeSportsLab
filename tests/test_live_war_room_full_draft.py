"""End-to-end reliability proof for a complete Drunk Sundays draft."""

import copy

import pytest

from fantasy_draft_model.draft_lifecycle import (
    inspect_draft_lifecycle,
    recover_existing_draft,
    resume_existing_draft,
    start_new_draft,
)
from fantasy_draft_model.keepers import load_keepers
from fantasy_draft_model.live_war_room import (
    get_pick_context,
    load_war_room_state,
    record_manual_pick,
    resolve_league,
    undo_last_manual_pick,
)
from fantasy_draft_model.state_persistence import state_backup_path
from fantasy_draft_model.war_room_state import (
    DraftCompleteError,
    validate_war_room_state,
)


def expected_snake_owner(pick_number, canonical_order):
    """Independently derive the owner of a 1-indexed snake-draft pick."""
    team_count = len(canonical_order)
    round_number = ((pick_number - 1) // team_count) + 1
    pick_in_round = ((pick_number - 1) % team_count) + 1
    slot = pick_in_round if round_number % 2 else team_count - pick_in_round + 1
    return canonical_order[slot - 1]


def expected_snake_slot(pick_number, team_count):
    round_number = ((pick_number - 1) // team_count) + 1
    pick_in_round = ((pick_number - 1) % team_count) + 1
    return pick_in_round if round_number % 2 else team_count - pick_in_round + 1


def synthetic_non_keeper_players(keeper_names, count):
    """Materialize a deterministic, finite non-keeper pool for the simulation."""
    keeper_keys = {str(name).strip().casefold() for name in keeper_names}
    players = []
    for index in range(1, count + 1):
        name = f"Simulation Non-Keeper {index:03d}"
        if name.casefold() in keeper_keys:
            continue
        players.append(
            {
                "player_name_clean": name,
                "position": "WR",
                "team": "SIM",
                "bye_week": 10,
                "draft_rank": index,
            }
        )
    return iter(players)


def next_synthetic_player(players):
    """Fail with simulation context instead of leaking a bare StopIteration."""
    try:
        return next(players)
    except StopIteration as error:
        raise AssertionError("Synthetic non-keeper player pool exhausted") from error


def test_synthetic_non_keeper_pool_is_finite_and_fails_clearly_when_exhausted():
    players = synthetic_non_keeper_players([], count=1)

    assert next_synthetic_player(players)["player_name_clean"] == "Simulation Non-Keeper 001"
    with pytest.raises(AssertionError, match="pool exhausted"):
        next_synthetic_player(players)


def test_full_drunk_sundays_draft_restarts_recovers_and_recompletes(tmp_path):
    """Catch lifecycle regressions that only surface across all 180 draft slots."""
    league = resolve_league("drunk_sundays")
    canonical_order = list(league["draft_order"])
    real_keepers = load_keepers("Drunk Sundays")
    state_path = tmp_path / "drunk-sundays-state.json"
    archive_root = tmp_path / "archives"
    state = start_new_draft("drunk_sundays", state_path, archive_root)

    expected_keeper_costs = {}
    for _, keeper in real_keepers.iterrows():
        owner = str(keeper["owner_team"]).strip()
        canonical_owner = next(
            team for team in canonical_order if team.casefold() == owner.casefold()
        )
        keeper_round = int(keeper["keeper_round"])
        slot = canonical_order.index(canonical_owner) + 1
        pick_number = (
            (keeper_round - 1) * len(canonical_order)
            + (slot if keeper_round % 2 else len(canonical_order) - slot + 1)
        )
        expected_keeper_costs[str(keeper["player_name"])] = {
            "keeper_round": keeper_round,
            "pick_number": pick_number,
            "fantasy_team": canonical_owner,
        }

    assert len(state["keeper_reservations"]) == len(expected_keeper_costs)
    for reservation in state["keeper_reservations"]:
        expected = expected_keeper_costs[reservation["player_name"]]
        assert reservation["keeper_round"] == expected["keeper_round"]
        assert reservation["round"] == expected["keeper_round"]
        assert reservation["pick_number"] == expected["pick_number"]
        assert reservation["fantasy_team"] == expected["fantasy_team"]

    players = synthetic_non_keeper_players(
        expected_keeper_costs,
        count=int(league["team_count"]) * int(league["draft_rounds"]) + 24,
    )
    checkpoints = {24, 84, 168}
    recovered = False
    boundary_cycle_completed = False

    while state["status"] != "complete":
        context = get_pick_context(state)
        assert context["fantasy_team"] == expected_snake_owner(
            context["pick_number"], canonical_order
        )

        if context["pick_number"] == 32 and not boundary_cycle_completed:
            boundary_player = next_synthetic_player(players)
            recorded = record_manual_pick(state, boundary_player, state_path)
            assert recorded["pick_number"] == 32
            assert state["current_pick"] == 34
            assert 33 in state["processed_keeper_picks"]

            undone = undo_last_manual_pick(state, state_path)
            assert undone == recorded
            assert state["current_pick"] == 32
            assert 33 not in state["processed_keeper_picks"]

            rerecorded = record_manual_pick(state, boundary_player, state_path)
            assert rerecorded == recorded
            assert state["current_pick"] == 34
            assert 33 in state["processed_keeper_picks"]
            boundary_cycle_completed = True
        else:
            recorded = record_manual_pick(
                state,
                next_synthetic_player(players),
                state_path,
            )

        if recorded["pick_number"] in checkpoints:
            state = resume_existing_draft(state_path, archive_root=archive_root)
            assert load_war_room_state(state_path) == state
            validate_war_room_state(
                state,
                keeper_reservations=state["keeper_reservations"],
            )

        if recorded["pick_number"] == 84 and not recovered:
            backup_path = state_backup_path(state_path)
            backup_before = backup_path.read_bytes()
            state_path.write_bytes(b"{malformed temporary authoritative draft state")

            inspection = inspect_draft_lifecycle(state_path)
            assert inspection.can_resume is False
            assert inspection.can_recover is True
            assert state_path.read_bytes().startswith(b"{malformed")

            state = recover_existing_draft(state_path, archive_root)
            assert state_path.read_bytes() != b"{malformed temporary authoritative draft state"
            assert backup_path.read_bytes() == backup_before
            assert any(
                path.read_bytes().startswith(b"{malformed")
                for path in archive_root.rglob("*")
                if path.is_file()
            )
            recovered = True

        state = load_war_room_state(state_path)

    assert boundary_cycle_completed is True
    assert recovered is True
    assert state["current_pick"] == 181
    assert state["status"] == "complete"
    assert len(state["manual_picks"]) + len(state["keeper_reservations"]) == 180

    accounted = state["manual_picks"] + state["keeper_reservations"]
    accounted_by_pick = {pick["pick_number"]: pick for pick in accounted}
    assert set(accounted_by_pick) == set(range(1, 181))

    for pick_number, pick in accounted_by_pick.items():
        assert pick["fantasy_team"] == expected_snake_owner(
            pick_number, canonical_order
        )
        assert pick["draft_slot"] == expected_snake_slot(
            pick_number, len(canonical_order)
        )

    for round_end in range(12, 169, 12):
        for pick_number in (round_end, round_end + 1):
            assert accounted_by_pick[pick_number]["fantasy_team"] == expected_snake_owner(
                pick_number, canonical_order
            )

    rosters = {team: [] for team in canonical_order}
    for pick in accounted:
        rosters[pick["fantasy_team"]].append(pick)
    assert all(len(rosters[team]) == 15 for team in canonical_order)

    all_player_keys = [pick["player_name"].strip().casefold() for pick in accounted]
    assert len(all_player_keys) == len(set(all_player_keys))

    before_pick_181 = copy.deepcopy(state)
    before_pick_181_bytes = state_path.read_bytes()
    with pytest.raises(DraftCompleteError, match="180"):
        record_manual_pick(state, next_synthetic_player(players), state_path)
    assert state == before_pick_181
    assert state_path.read_bytes() == before_pick_181_bytes

    final_manual = state["manual_picks"][-1]
    removed = undo_last_manual_pick(state, state_path)
    assert removed == final_manual
    assert state["current_pick"] == final_manual["pick_number"]
    assert state["status"] == "active"
    assert not any(pick >= 169 for pick in state["processed_keeper_picks"])

    record_manual_pick(state, next_synthetic_player(players), state_path)
    state = load_war_room_state(state_path)
    assert state["current_pick"] == 181
    assert state["status"] == "complete"
    assert len(state["manual_picks"]) + len(state["keeper_reservations"]) == 180
