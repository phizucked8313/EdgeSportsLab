import pandas as pd

from fantasy_draft_model.draft_assistant import build_draft_assistant_from_rankings
from fantasy_draft_model.ui.draft_war_room import filter_available_players


def test_unavailable_players_are_removed_before_live_tier_scarcity_and_brain():
    rankings = pd.DataFrame([
        {"player_name_clean": "RB A", "position": "RB", "tier": 2, "tier_size": 2,
         "tier_threshold": 17.5, "tier_next_projection_drop": 17.5, "tier_next_vorp_drop": 0.0,
         "draft_rank": 5, "vorp": 100.0, "edgescore": 80.0, "projection_score": 80.0,
         "projection_confidence": 90.0, "injury_risk_score": 10.0},
        {"player_name_clean": "RB B", "position": "RB", "tier": 2, "tier_size": 2,
         "tier_threshold": 17.5, "tier_next_projection_drop": 17.5, "tier_next_vorp_drop": 0.0,
         "draft_rank": 6, "vorp": 95.0, "edgescore": 79.0, "projection_score": 79.0,
         "projection_confidence": 90.0, "injury_risk_score": 10.0},
    ])
    state = {
        "manual_picks": [{"player_name": "RB A"}],
        "keeper_reservations": [],
    }
    available = filter_available_players(rankings, state)
    board = build_draft_assistant_from_rankings(
        available,
        draft_context={"picks_until_user": 3, "drafted_picks": state["manual_picks"]},
    )
    assert board["player_name_clean"].tolist() == ["RB B"]
    assert board.iloc[0]["tier_remaining"] == 1
