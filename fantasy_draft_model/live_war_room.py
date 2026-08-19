"""EdgeIQ live War Room state foundation."""

import json
from pathlib import Path

from fantasy_draft_model.keepers import load_keepers
from fantasy_draft_model.models.league_profile import LEAGUES


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
        if current_pick not in reservations_by_pick or current_pick in processed:
            break

        state.setdefault("processed_keeper_picks", []).append(current_pick)
        processed.add(current_pick)
        state["current_pick"] = current_pick + 1

    return state


def initialize_war_room(league_identifier, state_path=DEFAULT_STATE_PATH):
    """Create and persist a fresh War Room state for one league."""
    league = resolve_league(league_identifier)
    keepers = load_keepers(league["name"])
    keeper_reservations = build_keeper_reservations(league, keepers)

    state = {
        "schema_version": 1,
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
    save_war_room_state(state, state_path)
    return state
