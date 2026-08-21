"""Complete-draft regression for the immutable production draft-night board."""

from fantasy_draft_model import draft_night_board
from fantasy_draft_model.live_war_room import (
    get_pick_context,
    load_war_room_state,
    record_manual_pick,
)
from fantasy_draft_model.ui.draft_war_room import (
    build_live_draft_context,
    filter_available_players,
)
from fantasy_draft_model.live_war_room import initialize_war_room


def _select_player(board, state, preferred_name=None):
    available = filter_available_players(board, state)
    if preferred_name is not None:
        preferred = available.loc[
            available["player_name_clean"].eq(preferred_name)
        ]
        if not preferred.empty:
            return preferred.iloc[0]

    ranked = available.loc[
        ~available["is_supplemental"].fillna(False).astype(bool)
    ].copy()
    if not ranked.empty:
        return ranked.sort_values("draft_rank", kind="stable").iloc[0]
    return available.iloc[0]


def test_complete_180_slot_draft_uses_frozen_board_and_special_teams(tmp_path):
    state_path = tmp_path / "frozen-full-draft.json"
    state = initialize_war_room("drunk_sundays", state_path=state_path)
    board, status = draft_night_board.load_production_draft_night_board(
        "drunk_sundays"
    )

    assert status.source == "FROZEN/OFFLINE"
    assert len(board) == 324

    drafted_special = []
    preferred_special = ["Brandon Aubrey", "Philadelphia Eagles"]

    while state["status"] != "complete":
        context = get_pick_context(state)
        preferred = preferred_special.pop(0) if preferred_special else None
        player = _select_player(board, state, preferred_name=preferred)
        recorded = record_manual_pick(state, player, state_path=state_path)
        if recorded["position"] in {"K", "DEF"}:
            drafted_special.append(recorded["player_name"])

        state = load_war_room_state(state_path)
        assert state["current_pick"] >= context["pick_number"] + 1

    assert state["current_pick"] == 181
    assert state["status"] == "complete"
    assert len(state["manual_picks"]) + len(state["keeper_reservations"]) == 180
    assert "Brandon Aubrey" in drafted_special
    assert "Philadelphia Eagles" in drafted_special

    accounted_names = [
        pick["player_name"].strip().casefold()
        for pick in state["manual_picks"] + state["keeper_reservations"]
    ]
    assert len(accounted_names) == len(set(accounted_names))

    context = build_live_draft_context(state)
    assert context["draft_complete"] is True
    assert context["current_pick"] == 181
    assert context["next_user_pick"] is None
    assert context["picks_until_user"] is None
