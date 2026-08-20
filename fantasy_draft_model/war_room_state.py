"""Versioned EdgeIQ War Room state metadata and validation."""

import copy
from datetime import datetime, timezone
from uuid import uuid4


class StateValidationError(ValueError):
    """Raised when a War Room state fails one or more integrity checks."""

    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__("Invalid War Room state: " + "; ".join(self.issues))


class DraftCompleteError(ValueError):
    """Raised when a draft-advancing operation is attempted after completion."""


def utc_now_iso():
    """Return the current UTC time as an offset-aware ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def new_draft_id():
    """Return a locally generated identifier for one draft lifecycle."""
    return str(uuid4())


def total_picks_for(league):
    """Return the canonical number of slots in a league's draft."""
    return int(league["team_count"]) * int(league["draft_rounds"])


def derive_draft_status(state):
    """Derive lifecycle status from the draft's canonical completion boundary."""
    return "complete" if int(state["current_pick"]) > int(state["total_picks"]) else "active"


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _normalized_player_name(value):
    return str(value).strip().casefold()


def _snake_metadata(league, pick_number):
    team_count = int(league["team_count"])
    round_number = ((pick_number - 1) // team_count) + 1
    pick_in_round = ((pick_number - 1) % team_count) + 1
    draft_slot = pick_in_round if round_number % 2 else team_count - pick_in_round + 1
    return {
        "round": round_number,
        "draft_slot": draft_slot,
        "fantasy_team": list(league["draft_order"])[draft_slot - 1],
    }


def _resolve_state_league(state, issues):
    from fantasy_draft_model.live_war_room import resolve_league

    for field in ("league_key", "league_name"):
        identifier = state.get(field)
        if not identifier:
            continue
        try:
            return resolve_league(identifier)
        except ValueError:
            continue
    issues.append("league_name/league_key does not identify a canonical league")
    return None


def _validate_timestamp(state, field, issues):
    value = state.get(field)
    if not isinstance(value, str):
        issues.append(f"{field} must be an ISO-8601 UTC timestamp")
        return
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        issues.append(f"{field} must be an ISO-8601 UTC timestamp")
        return
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        issues.append(f"{field} must use the UTC offset")


def validate_war_room_state(state, *, keeper_reservations=None):
    """Return *state* unchanged when it is canonical, otherwise raise."""
    if not isinstance(state, dict):
        raise StateValidationError(["state must be a dictionary"])

    required_fields = (
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
    )
    issues = [f"missing required field: {field}" for field in required_fields if field not in state]
    if issues:
        raise StateValidationError(issues)

    if state["schema_version"] != 2:
        issues.append("schema_version must be 2")
    if not isinstance(state["draft_id"], str) or not state["draft_id"].strip():
        issues.append("draft_id must be a non-empty string")
    _validate_timestamp(state, "created_at", issues)
    _validate_timestamp(state, "updated_at", issues)

    league = _resolve_state_league(state, issues)
    canonical_total = None
    if league is not None:
        canonical_fields = {
            "league_name": league["name"],
            "league_key": league["league_key"],
            "user_team": league["user_team"],
            "team_count": int(league["team_count"]),
            "draft_rounds": int(league["draft_rounds"]),
        }
        for field, expected in canonical_fields.items():
            if state[field] != expected:
                issues.append(f"{field} must equal canonical value {expected!r}")
        canonical_total = total_picks_for(league)
        if state["total_picks"] != canonical_total:
            issues.append(f"total_picks must equal canonical value {canonical_total}")

    current_pick = state["current_pick"]
    if not _is_int(current_pick) or canonical_total is None or not 1 <= current_pick <= canonical_total + 1:
        upper = (canonical_total + 1) if canonical_total is not None else "the completion boundary"
        issues.append(f"current_pick must be an integer from 1 through {upper}")

    if state["status"] not in {"active", "complete"}:
        issues.append("status must be 'active' or 'complete'")
    elif canonical_total is not None and _is_int(current_pick):
        expected_status = "complete" if current_pick == canonical_total + 1 else "active"
        if state["status"] != expected_status:
            issues.append(f"status must be {expected_status!r} at current_pick {current_pick}")

    manual_picks = state["manual_picks"]
    reservations = state["keeper_reservations"]
    processed = state["processed_keeper_picks"]
    if not isinstance(manual_picks, list):
        issues.append("manual_picks must be a list")
        manual_picks = []
    if not isinstance(reservations, list):
        issues.append("keeper_reservations must be a list")
        reservations = []
    if not isinstance(processed, list):
        issues.append("processed_keeper_picks must be a list")
        processed = []

    if keeper_reservations is not None and reservations != keeper_reservations:
        issues.append("keeper_reservations do not match canonical keeper declarations")

    reservation_numbers = []
    player_names = []
    for index, reservation in enumerate(reservations):
        if not isinstance(reservation, dict):
            issues.append(f"keeper_reservations[{index}] must be a dictionary")
            continue
        pick_number = reservation.get("pick_number")
        if not _is_int(pick_number) or canonical_total is None or not 1 <= pick_number <= canonical_total:
            issues.append(f"keeper_reservations[{index}].pick_number is outside the draft")
            continue
        reservation_numbers.append(pick_number)
        player_name = reservation.get("player_name")
        if not isinstance(player_name, str) or not player_name.strip():
            issues.append(f"keeper_reservations[{index}].player_name must be non-empty")
        else:
            player_names.append(_normalized_player_name(player_name))
        if league is not None:
            expected = _snake_metadata(league, pick_number)
            for field, value in expected.items():
                if reservation.get(field) != value:
                    issues.append(f"keeper_reservations[{index}].{field} must equal {value!r}")
            if reservation.get("keeper_round") != expected["round"]:
                issues.append(
                    f"keeper_reservations[{index}].keeper_round must equal {expected['round']}"
                )

    if len(reservation_numbers) != len(set(reservation_numbers)):
        issues.append("duplicate keeper reservation pick numbers")

    manual_numbers = []
    for index, pick in enumerate(manual_picks):
        if not isinstance(pick, dict):
            issues.append(f"manual_picks[{index}] must be a dictionary")
            continue
        pick_number = pick.get("pick_number")
        if not _is_int(pick_number) or canonical_total is None or not 1 <= pick_number <= canonical_total:
            issues.append(f"manual_picks[{index}].pick_number is outside the draft")
            continue
        manual_numbers.append(pick_number)
        player_name = pick.get("player_name")
        if not isinstance(player_name, str) or not player_name.strip():
            issues.append(f"manual_picks[{index}].player_name must be non-empty")
        else:
            player_names.append(_normalized_player_name(player_name))
        if league is not None:
            expected = _snake_metadata(league, pick_number)
            for field, value in expected.items():
                if pick.get(field) != value:
                    issues.append(f"manual_picks[{index}].{field} must equal {value!r}")

    if len(manual_numbers) != len(set(manual_numbers)):
        issues.append("duplicate manual pick numbers")
    if len(player_names) != len(set(player_names)):
        issues.append("duplicate player names across manual picks and keeper reservations")

    reservation_set = set(reservation_numbers)
    manual_set = set(manual_numbers)
    if manual_set & reservation_set:
        issues.append("manual pick occupies a keeper slot")

    valid_processed = [pick for pick in processed if _is_int(pick)]
    if len(valid_processed) != len(processed):
        issues.append("processed_keeper_picks must contain only integers")
    if len(valid_processed) != len(set(valid_processed)):
        issues.append("duplicate processed keeper picks")
    for pick_number in valid_processed:
        if pick_number not in reservation_set:
            issues.append(f"processed keeper pick {pick_number} is not a declared reservation")
        if _is_int(current_pick) and pick_number >= current_pick:
            issues.append(f"processed keeper pick {pick_number} is at or after current_pick")

    if _is_int(current_pick) and canonical_total is not None and 1 <= current_pick <= canonical_total + 1:
        future_manual = sorted(pick for pick in manual_set if pick >= current_pick)
        if future_manual:
            issues.append(f"manual picks {future_manual} are at or after current_pick")
        expected_accounted = set(range(1, current_pick))
        accounted = manual_set | set(valid_processed)
        if accounted != expected_accounted:
            missing = sorted(expected_accounted - accounted)
            extra = sorted(accounted - expected_accounted)
            issues.append(
                f"accounted picks before current_pick are inconsistent; missing={missing}, extra={extra}"
            )

    if issues:
        raise StateValidationError(issues)
    return state


def migrate_legacy_state(state):
    """Build and validate an in-memory schema-2 copy of schema-1 state."""
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise StateValidationError(["legacy state must use schema_version 1"])

    migrated = copy.deepcopy(state)
    from fantasy_draft_model.live_war_room import resolve_league

    league = resolve_league(migrated.get("league_key") or migrated.get("league_name"))
    timestamp = utc_now_iso()
    migrated.update(
        {
            "schema_version": 2,
            "draft_id": new_draft_id(),
            "created_at": timestamp,
            "updated_at": timestamp,
            "total_picks": total_picks_for(league),
        }
    )
    migrated["status"] = derive_draft_status(migrated)
    return validate_war_room_state(migrated)
