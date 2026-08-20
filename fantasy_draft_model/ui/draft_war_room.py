import pandas as pd

from fantasy_draft_model.models.league_profile import get_league


USER_ROSTER_COLUMNS = [
    "player_name",
    "position",
    "nfl_team",
    "round",
    "pick_number",
    "source",
]

DRAFT_NIGHT_COLUMNS = [
    "draft_rank",
    "player_name_clean",
    "position",
    "team",
    "position_rank_label",
    "tier_label",
    "tier_remaining",
    "tier_scarcity_score",
    "projected_points",
    "vorp",
    "edgescore",
    "draft_score",
    "pressure_score",
    "brain_score",
    "brain_recommendation",
    "injury_risk_score",
]

AVAILABLE_PLAYERS_ONLY_ATTR = "_edgeiq_available_players_only"


def normalize_player_name(value):
    return str(value).strip().casefold()


def get_unavailable_player_names(state):
    names = {
        normalize_player_name(pick.get("player_name", ""))
        for pick in state.get("manual_picks", [])
        if pick.get("player_name")
    }
    names.update(
        normalize_player_name(reservation.get("player_name", ""))
        for reservation in state.get("keeper_reservations", [])
        if reservation.get("player_name")
    )
    return names


def filter_available_players(rankings, state):
    unavailable = get_unavailable_player_names(state)
    if not unavailable:
        return rankings.copy().reset_index(drop=True)

    mask = ~rankings["player_name_clean"].map(normalize_player_name).isin(unavailable)
    return rankings.loc[mask].copy().reset_index(drop=True)


def apply_player_filters(rankings, search_text="", position=None):
    filtered = rankings.copy()

    search_text = str(search_text or "").strip().casefold()
    if search_text:
        name_mask = filtered["player_name_clean"].map(normalize_player_name).str.contains(
            search_text,
            regex=False,
        )
        filtered = filtered.loc[name_mask]

    if position and str(position).strip().upper() != "ALL":
        position_clean = str(position).strip().upper()
        position_mask = filtered["position"].astype(str).str.strip().str.upper() == position_clean
        filtered = filtered.loc[position_mask]

    return filtered.copy().reset_index(drop=True)


def select_display_columns(rankings, preferred_columns):
    return [column for column in preferred_columns if column in rankings.columns]


def format_position_tier(position, tier):
    return f"{str(position).strip().upper()} Tier {int(tier)}"


def get_display_tier_label(player):
    tier = pd.to_numeric(player.get("tier"), errors="coerce")
    if pd.isna(tier):
        return ""
    return format_position_tier(player.get("position", ""), tier)


def build_available_player_display(rankings):
    """Return only the decision columns needed on the draft-night board."""
    columns = select_display_columns(rankings, DRAFT_NIGHT_COLUMNS)
    display = rankings.loc[:, columns].copy().reset_index(drop=True)
    display.insert(
        DRAFT_NIGHT_COLUMNS.index("tier_label"),
        "tier_label",
        rankings.apply(get_display_tier_label, axis=1).to_numpy(),
    )
    return display


def build_static_available_board_html(rankings):
    """Render the available-player board as static scrollable HTML with no row index."""
    display = build_available_player_display(rankings)
    table_html = display.to_html(
        index=False,
        escape=True,
        border=0,
        classes="edgeiq-board-table",
    )
    return (
        '<div class="edgeiq-board-scroll" '
        'style="max-height: 520px; overflow: auto;">'
        f"{table_html}"
        "</div>"
    )


def build_player_ranking_explanation(rankings, player_name):
    """Explain one player's live EdgeIQ rank without mutating the board."""
    board = rankings.copy().reset_index(drop=True)
    player_key = normalize_player_name(player_name)
    matches = board[
        board["player_name_clean"].map(normalize_player_name) == player_key
    ]
    if matches.empty:
        raise ValueError(f"Player not found: {player_name}")

    player_index = int(matches.index[0])
    player = board.loc[player_index]
    tier_remaining = pd.to_numeric(player.get("tier_remaining"), errors="coerce")
    tier_scarcity_score = pd.to_numeric(
        player.get("tier_scarcity_score"),
        errors="coerce",
    )

    key_numbers = {
        "projected_points": float(player.get("projected_points", 0.0)),
        "vorp": float(player.get("vorp", 0.0)),
        "edgescore": float(player.get("edgescore", 0.0)),
        "projection_confidence": float(player.get("projection_confidence", 0.0)),
        "injury_risk_score": float(player.get("injury_risk_score", 0.0)),
    }

    comparison = None
    if player_index + 1 < len(board):
        next_player = board.loc[player_index + 1]
        comparison = {
            "player_name": next_player.get("player_name_clean"),
            "brain_score_delta": round(
                float(player.get("brain_score", 0.0))
                - float(next_player.get("brain_score", 0.0)),
                2,
            ),
            "projected_points_delta": round(
                float(player.get("projected_points", 0.0))
                - float(next_player.get("projected_points", 0.0)),
                2,
            ),
            "vorp_delta": round(
                float(player.get("vorp", 0.0))
                - float(next_player.get("vorp", 0.0)),
                2,
            ),
            "edgescore_delta": round(
                float(player.get("edgescore", 0.0))
                - float(next_player.get("edgescore", 0.0)),
                2,
            ),
        }

    return {
        "player_name": player.get("player_name_clean"),
        "draft_rank": int(player.get("draft_rank", 0)),
        "position_rank_label": player.get("position_rank_label"),
        "tier_label": get_display_tier_label(player),
        "tier_remaining": 0 if pd.isna(tier_remaining) else int(tier_remaining),
        "tier_scarcity_score": (
            0.0 if pd.isna(tier_scarcity_score) else float(tier_scarcity_score)
        ),
        "brain_score": float(player.get("brain_score", 0.0)),
        "recommendation": player.get("brain_recommendation", ""),
        "drivers": list(player.get("brain_reasons", []) or []),
        "warnings": list(player.get("brain_warnings", []) or []),
        "key_numbers": key_numbers,
        "comparison": comparison,
    }


def build_recent_history(state, limit=10):
    history = pd.DataFrame(state.get("manual_picks", []))
    if history.empty:
        return history

    if "pick_number" in history.columns:
        history = history.sort_values("pick_number", ascending=False)
    else:
        history = history.iloc[::-1]

    return history.head(limit).reset_index(drop=True)


def build_live_draft_context(state):
    """Return the user's next snake-draft turn and distance from the current pick."""
    league = get_league(state["league_name"])
    if league is None:
        raise ValueError(f"Unknown league: {state['league_name']}")

    current_pick = int(state["current_pick"])
    team_count = int(state.get("team_count", league["team_count"]))
    draft_rounds = int(state.get("draft_rounds", league["draft_rounds"]))
    user_team = state.get("user_team", league["user_team"])
    draft_order = league["draft_order"]

    if user_team not in draft_order:
        raise ValueError(f"User team not found in draft order: {user_team}")

    user_slot = draft_order.index(user_team) + 1
    total_picks = team_count * draft_rounds
    next_user_pick = None

    for round_number in range(1, draft_rounds + 1):
        if round_number % 2 == 1:
            pick_in_round = user_slot
        else:
            pick_in_round = team_count - user_slot + 1

        pick_number = (round_number - 1) * team_count + pick_in_round
        if pick_number >= current_pick:
            next_user_pick = pick_number
            break

    if next_user_pick is None:
        picks_until_user = None
        user_on_clock = False
    else:
        picks_until_user = next_user_pick - current_pick
        user_on_clock = picks_until_user == 0

    return {
        "current_pick": current_pick,
        "next_user_pick": next_user_pick,
        "picks_until_user": picks_until_user,
        "user_on_clock": user_on_clock,
        "user_draft_slot": user_slot,
        "draft_complete": current_pick > total_picks,
        "drafted_picks": state.get("manual_picks", []),
    }


def build_user_roster(state):
    """Build the user's live roster from manual picks and keeper reservations."""
    user_team = state.get("user_team", "")
    roster_rows = []

    for pick in state.get("manual_picks", []):
        if pick.get("fantasy_team") != user_team:
            continue
        roster_rows.append(
            {
                "player_name": pick.get("player_name"),
                "position": pick.get("position"),
                "nfl_team": pick.get("nfl_team"),
                "round": pick.get("round"),
                "pick_number": pick.get("pick_number"),
                "source": "draft",
            }
        )

    for keeper in state.get("keeper_reservations", []):
        if keeper.get("fantasy_team") != user_team:
            continue
        roster_rows.append(
            {
                "player_name": keeper.get("player_name"),
                "position": keeper.get("position"),
                "nfl_team": keeper.get("nfl_team"),
                "round": keeper.get("round", keeper.get("keeper_round")),
                "pick_number": keeper.get("pick_number"),
                "source": "keeper",
            }
        )

    return pd.DataFrame(roster_rows, columns=USER_ROSTER_COLUMNS)


def enrich_user_roster_metadata(roster, rankings):
    """Fill missing roster position/team metadata from the rankings board."""
    enriched = roster.copy()
    if enriched.empty or rankings.empty:
        return enriched

    lookup = rankings.copy()
    lookup["_player_key"] = lookup["player_name_clean"].map(normalize_player_name)
    lookup = lookup.drop_duplicates("_player_key").set_index("_player_key")

    for index, row in enriched.iterrows():
        player_key = normalize_player_name(row.get("player_name", ""))
        if player_key not in lookup.index:
            continue

        match = lookup.loc[player_key]
        if pd.isna(row.get("position")) or not str(row.get("position") or "").strip():
            enriched.at[index, "position"] = match.get("position")
        if pd.isna(row.get("nfl_team")) or not str(row.get("nfl_team") or "").strip():
            enriched.at[index, "nfl_team"] = match.get("team")

    return enriched


def build_war_room_snapshot(rankings, state, search_text="", position=None, history_limit=10):
    """Compose read-only data for the War Room UI without mutating rankings."""
    if rankings.attrs.get(AVAILABLE_PLAYERS_ONLY_ATTR, False):
        available = rankings.copy().reset_index(drop=True)
    else:
        available = filter_available_players(rankings, state)
    filtered_available = apply_player_filters(
        available,
        search_text=search_text,
        position=position,
    )
    roster = enrich_user_roster_metadata(build_user_roster(state), rankings)

    return {
        "context": build_live_draft_context(state),
        "available": available,
        "filtered_available": filtered_available,
        "roster": roster,
        "recent_history": build_recent_history(state, limit=history_limit),
    }
