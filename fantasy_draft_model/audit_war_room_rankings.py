"""Diagnostic: compare live EdgeIQ ranking components for named players."""

from fantasy_draft_model.draft_assistant import build_draft_assistant_from_rankings
from fantasy_draft_model.live_war_room import load_war_room_state
from fantasy_draft_model.rankings import build_draft_rankings
from fantasy_draft_model.ui.draft_war_room import build_live_draft_context


PLAYERS = [
    "Chris Olave",
    "Ja'Marr Chase",
    "Amon-Ra St. Brown",
    "Drake London",
    "George Pickens",
]

COLUMNS = [
    "player_name_clean",
    "position",
    "team",
    "draft_rank",
    "position_rank_label",
    "tier",
    "tier_status",
    "projected_points",
    "replacement_points",
    "vorp",
    "vorp_score",
    "projection_score",
    "edgescore",
    "projection_confidence",
    "injury_risk_score",
    "draft_score",
    "pressure_score",
    "brain_score",
    "brain_recommendation",
    "brain_reasons",
    "brain_warnings",
]


def main():
    state = load_war_room_state()
    context = build_live_draft_context(state)
    rankings = build_draft_rankings(state["league_key"])
    board = build_draft_assistant_from_rankings(rankings, draft_context=context)

    mask = board["player_name_clean"].isin(PLAYERS)
    audit = board.loc[mask].copy()
    columns = [column for column in COLUMNS if column in audit.columns]

    print("\n============================================")
    print("EDGEIQ LIVE WAR ROOM RANKING AUDIT")
    print("============================================")
    print(f"Current pick: {context.get('current_pick')}")
    print(f"Picks until BLKWDW'S: {context.get('picks_until_user')}")
    print("\nPlayers sorted by LIVE brain_score:\n")

    if audit.empty:
        print("No requested players were found in the current board.")
        return

    audit = audit.sort_values("brain_score", ascending=False)
    print(audit[columns].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
