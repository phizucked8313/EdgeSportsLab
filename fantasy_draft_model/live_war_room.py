"""EdgeIQ live War Room state foundation."""

import json
from pathlib import Path

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


def initialize_war_room(league_identifier, state_path=DEFAULT_STATE_PATH):
    """Create and persist a fresh War Room state for one league."""
    league = resolve_league(league_identifier)

    state = {
        "schema_version": 1,
        "league_name": league["name"],
        "league_key": league["league_key"],
        "user_team": league["user_team"],
        "team_count": int(league["team_count"]),
        "draft_rounds": int(league["draft_rounds"]),
        "current_pick": 1,
        "manual_picks": [],
        "keeper_reservations": [],
        "processed_keeper_picks": [],
    }

    save_war_room_state(state, state_path)
    return state
