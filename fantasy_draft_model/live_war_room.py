"""EdgeIQ live War Room state foundation."""

import json
from pathlib import Path

from fantasy_draft_model.keepers import load_keepers
from fantasy_draft_model.models.league_profile import LEAGUES
from fantasy_draft_model.war_room_state import (
    DraftCompleteError,
    derive_draft_status,
    new_draft_id,
    total_picks_for,
    utc_now_iso,
    validate_war_room_state,
)


DEFAULT_STATE_PATH = (
    Path(__file__).parent
    / "data"
    / "live_war_room_state.json"
)


def resolve_league(league_identifier):
    """Resolve a league by canonical display name or league key."""
    for league in LEAGUES.values():
        if league_identifier in {league["name"], league["league_key"]}:
            return league

    raise ValueError(f"Unknown league: {league_identifier!r}")


def save_war_room_state(state, state_path=DEFAULT_STATE_PATH):
    """Persist War Room state as JSON."""
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


def load_war_room_state(state_path=DEFAULT_STATE_PATH):
    """Load previously persisted War Room state."""
    path = Path(state_path)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _normalize_team_name(value):
    return str(value).strip().lower().replace("’", "'")


def _normalize_player_name(value):
    return str(value).strip().casefold()


def _json_safe_value(value):
    """Convert common dataframe scalar values into JSON-safe Python values."""
    if value is None:
        return None

    try:
        if value != value:
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass

    return value


def _snake_pick_number(round_number, draft_slot, team_count):
    if round_number % 2 == 1:
        pick_in_round = draft_slot
    else:
        pick_in_round = team_count - draft_slot + 1

    return (round_number - 1) * team_count + pick_in_round


def build_keeper_reservations(league, keepers_df):
    """Convert declared keepers into their reserved snake-draft picks."""
    if keepers_df is None or keepers_df.empty:
        return []

    draft_order = list(league["draft_order"])
    slot_by_team = {
        _normalize_team_name(team): slot
        for slot, team in enumerate(draft_order, start=1)
    }

    reservations = []

    for _, keeper in keepers_df.iterrows():
        fantasy_team = str(keeper["owner_team"]).strip()
        normalized_team = _normalize_team_name(fantasy_team)
        draft_slot = slot_by_team.get(normalized_team)

        if draft_slot is None:
            raise ValueError(
                f"Keeper team {fantasy_team!r} is not in the "
                f"{league['name']} draft order"
            )

        canonical_team = draft_order[draft_slot - 1]
        keeper_round = int(keeper["keeper_round"])
        pick_number = _snake_pick_number(
            keeper_round,
            draft_slot,
            int(league["team_count"]),
        )

        reservations.append(
            {
                "pick_number": pick_number,
                "round": keeper_round,
                "draft_slot": draft_slot,
                "fantasy_team": canonical_team,
                "player_name": str(keeper["player_name"]),
                "keeper_type": str(keeper["keeper_type"]),
                "keeper_round": keeper_round,
            }
        )

    return sorted(
        reservations,
        key=lambda reservation: reservation["pick_number"],
    )


def _draft_total_picks(state):
    if "total_picks" in state:
        return int(state["total_picks"])
    if "team_count" in state and "draft_rounds" in state:
        return int(state["team_count"]) * int(state["draft_rounds"])
    return None


def _raise_if_draft_complete(state):
    total_picks = _draft_total_picks(state)
    if total_picks is not None and int(state["current_pick"]) > total_picks:
        raise DraftCompleteError(
            f"Draft is complete after {total_picks} picks"
        )


def advance_keeper_slots(state):
    """Advance through any keeper-reserved picks without double-processing."""
    reservations_by_pick = {
        int(reservation["pick_number"]): reservation
        for reservation in state.get("keeper_reservations", [])
    }
    processed = {
        int(pick_number)
        for pick_number in state.get("processed_keeper_picks", [])
    }

    while True:
        current_pick = int(state["current_pick"])
        total_picks = _draft_total_picks(state)
        if total_picks is not None and current_pick > total_picks:
            break
        if current_pick not in reservations_by_pick or current_pick in processed:
            break

        state.setdefault("processed_keeper_picks", []).append(current_pick)
        processed.add(current_pick)
        state["current_pick"] = current_pick + 1

    if _draft_total_picks(state) is not None:
        state["status"] = derive_draft_status(state)

    return state


def get_pick_context(state):
    """Return canonical snake-draft metadata for the state's current pick."""
    league_identifier = state.get("league_key") or state["league_name"]
    league = resolve_league(league_identifier)

    _raise_if_draft_complete(state)

    pick_number = int(state["current_pick"])
    team_count = int(state["team_count"])
    round_number = ((pick_number - 1) // team_count) + 1
    pick_in_round = ((pick_number - 1) % team_count) + 1

    if round_number % 2 == 1:
        draft_slot = pick_in_round
    else:
        draft_slot = team_count - pick_in_round + 1

    draft_order = list(league["draft_order"])
    fantasy_team = draft_order[draft_slot - 1]

    return {
        "pick_number": pick_number,
        "round": round_number,
        "draft_slot": draft_slot,
        "fantasy_team": fantasy_team,
    }


def _player_value(player_row, key, default=None):
    if hasattr(player_row, "get"):
        return _json_safe_value(player_row.get(key, default))
    return default


def _already_drafted_player_names(state):
    names = {
        _normalize_player_name(pick.get("player_name", ""))
        for pick in state.get("manual_picks", [])
        if pick.get("player_name")
    }
    names.update(
        _normalize_player_name(reservation.get("player_name", ""))
        for reservation in state.get("keeper_reservations", [])
        if reservation.get("player_name")
    )
    return names


def record_manual_pick(state, player_row, state_path=DEFAULT_STATE_PATH):
    """Record one manual draft selection, advance the board, and persist it."""
    _raise_if_draft_complete(state)
    advance_keeper_slots(state)
    _raise_if_draft_complete(state)
    context = get_pick_context(state)

    player_name = _player_value(player_row, "player_name_clean")
    if player_name is None or not str(player_name).strip():
        raise ValueError("Manual pick is missing player_name_clean")

    player_name = str(player_name).strip()
    normalized_player_name = _normalize_player_name(player_name)

    if normalized_player_name in _already_drafted_player_names(state):
        raise ValueError(f"{player_name} is already drafted")

    pick = {
        "player_name": player_name,
        "position": _player_value(player_row, "position"),
        "nfl_team": _player_value(player_row, "team"),
        "bye_week": _player_value(player_row, "bye_week"),
        "draft_rank": _player_value(player_row, "draft_rank"),
        "fantasy_team": context["fantasy_team"],
        "pick_number": context["pick_number"],
        "round": context["round"],
        "draft_slot": context["draft_slot"],
    }

    state.setdefault("manual_picks", []).append(pick)
    state["current_pick"] = context["pick_number"] + 1
    advance_keeper_slots(state)
    state["status"] = derive_draft_status(state)
    state["updated_at"] = utc_now_iso()
    save_war_room_state(state, state_path)
    return pick


def undo_last_manual_pick(state, state_path=DEFAULT_STATE_PATH):
    """Undo the most recent manual pick and reopen crossed keeper slots."""
    manual_picks = state.get("manual_picks", [])
    if not manual_picks:
        raise ValueError("No manual picks to undo")

    current_pick = int(state["current_pick"])
    removed = manual_picks[-1]
    restored_pick = int(removed["pick_number"])

    state["manual_picks"] = manual_picks[:-1]
    state["processed_keeper_picks"] = [
        int(pick_number)
        for pick_number in state.get("processed_keeper_picks", [])
        if not restored_pick < int(pick_number) < current_pick
    ]
    state["current_pick"] = restored_pick

    state["status"] = derive_draft_status(state)
    state["updated_at"] = utc_now_iso()

    save_war_room_state(state, state_path)
    return removed


def initialize_war_room(league_identifier, state_path=DEFAULT_STATE_PATH):
    """Create and persist a fresh War Room state for one league."""
    league = resolve_league(league_identifier)
    keepers = load_keepers(league["name"])
    keeper_reservations = build_keeper_reservations(league, keepers)

    timestamp = utc_now_iso()
    state = {
        "schema_version": 2,
        "draft_id": new_draft_id(),
        "created_at": timestamp,
        "updated_at": timestamp,
        "status": "active",
        "total_picks": total_picks_for(league),
        "league_name": league["name"],
        "league_key": league["league_key"],
        "user_team": league["user_team"],
        "team_count": int(league["team_count"]),
        "draft_rounds": int(league["draft_rounds"]),
        "current_pick": 1,
        "manual_picks": [],
        "keeper_reservations": keeper_reservations,
        "processed_keeper_picks": [],
    }

    advance_keeper_slots(state)
    state["status"] = derive_draft_status(state)
    validate_war_room_state(state, keeper_reservations=keeper_reservations)
    save_war_room_state(state, state_path)
    return state
