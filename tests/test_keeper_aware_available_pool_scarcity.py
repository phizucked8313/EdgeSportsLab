import pandas as pd

import fantasy_draft_model.draft_assistant as draft_assistant
import fantasy_draft_model.rankings as rankings
from fantasy_draft_model.engines.tier_engine import add_live_tier_scarcity


def _broad_rb_tier(*, remaining_replacement_demand):
    return pd.DataFrame(
        [
            {
                "player_name_clean": f"RB {index}",
                "position": "RB",
                "tier": 4,
                "projected_points": 260.0 - index,
                "vorp": 80.0 - index,
                "tier_next_threshold": 24.5,
                "tier_next_projection_drop": 0.0,
                "tier_next_vorp_drop": 0.0,
                "position_replacement_rank": 14,
                "position_remaining_replacement_demand": remaining_replacement_demand,
            }
            for index in range(1, 5)
        ]
    )


def test_depleted_replacement_pool_increases_live_scarcity_even_inside_same_broad_tier():
    full_pool = add_live_tier_scarcity(
        _broad_rb_tier(remaining_replacement_demand=14)
    )
    depleted_pool = add_live_tier_scarcity(
        _broad_rb_tier(remaining_replacement_demand=2)
    )

    assert depleted_pool["tier_scarcity_score"].iloc[0] > full_pool[
        "tier_scarcity_score"
    ].iloc[0]


def test_missing_replacement_level_ranks_reduce_remaining_position_demand():
    board = pd.DataFrame(
        [
            {"player_name_clean": "RB 3", "position": "RB", "position_rank": 3},
            {"player_name_clean": "RB 4", "position": "RB", "position_rank": 4},
            {"player_name_clean": "WR 2", "position": "WR", "position_rank": 2},
            {"player_name_clean": "WR 3", "position": "WR", "position_rank": 3},
            {"player_name_clean": "QB 1", "position": "QB", "position_rank": 1},
            {"player_name_clean": "TE 1", "position": "TE", "position_rank": 1},
        ]
    )
    replacement_ranks = {"QB": 1, "RB": 4, "WR": 3, "TE": 1}

    board = rankings.add_position_replacement_metadata(board, replacement_ranks)
    unavailable = rankings.infer_unavailable_position_counts(board)
    depleted = rankings.add_available_pool_depletion_metadata(
        board,
        unavailable,
    ).set_index("position")

    assert unavailable == {"QB": 0, "RB": 2, "WR": 1, "TE": 0}
    assert depleted.loc["RB", "position_remaining_replacement_demand"].iloc[0] == 2
    assert depleted.loc["WR", "position_remaining_replacement_demand"].iloc[0] == 2
    assert depleted.loc["QB", "position_remaining_replacement_demand"] == 1
    assert depleted.loc["TE", "position_remaining_replacement_demand"] == 1


def test_live_assistant_applies_available_pool_depletion_before_scarcity(monkeypatch):
    board = pd.DataFrame(
        [
            {
                "player_name_clean": "RB 3",
                "position": "RB",
                "position_rank": 3,
                "position_replacement_rank": 4,
                "position_remaining_replacement_demand": 4,
                "draft_rank": 3,
                "projected_points": 250.0,
            },
            {
                "player_name_clean": "RB 4",
                "position": "RB",
                "position_rank": 4,
                "position_replacement_rank": 4,
                "position_remaining_replacement_demand": 4,
                "draft_rank": 4,
                "projected_points": 240.0,
            },
            {
                "player_name_clean": "QB 1",
                "position": "QB",
                "position_rank": 1,
                "position_replacement_rank": 1,
                "position_remaining_replacement_demand": 1,
                "draft_rank": 1,
                "projected_points": 400.0,
            },
        ]
    )
    observed = {}

    def inspect_scarcity(frame):
        rb = frame.loc[frame["position"] == "RB"].iloc[0]
        observed["rb_remaining"] = rb["position_remaining_replacement_demand"]
        observed["rb_unavailable"] = rb.get("position_unavailable_demand_count")
        result = frame.copy()
        result["tier_scarcity_score"] = 0.0
        return result

    def add_brain_identity(frame, _context):
        result = frame.copy()
        result["brain_score"] = range(len(result), 0, -1)
        result["brain_recommendation"] = "WAIT"
        result["brain_reasons"] = [[] for _ in range(len(result))]
        result["brain_warnings"] = [[] for _ in range(len(result))]
        return result

    monkeypatch.setattr(draft_assistant, "add_live_tier_scarcity", inspect_scarcity)
    monkeypatch.setattr(
        draft_assistant,
        "recalculate_live_draft_score",
        lambda frame: frame.copy(),
    )
    monkeypatch.setattr(
        draft_assistant,
        "add_pressure_meter",
        lambda frame: frame.copy(),
    )
    monkeypatch.setattr(draft_assistant, "add_draft_brain", add_brain_identity)

    draft_assistant.build_draft_assistant_from_rankings(board, draft_context={})

    assert observed["rb_remaining"] == 2
    assert observed["rb_unavailable"] == 2
