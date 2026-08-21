import pandas as pd

import fantasy_draft_model.draft_assistant as draft_assistant
from fantasy_draft_model.rankings import (
    add_keeper_depletion_metadata,
    add_position_demand_metadata,
    infer_unavailable_position_counts,
)
from fantasy_draft_model.engines.tier_engine import add_live_tier_scarcity


REPLACEMENT_RANKS = {"QB": 12, "RB": 34, "WR": 38, "TE": 12}
KEEPER_COUNTS = {"QB": 0, "RB": 12, "WR": 2, "TE": 1}


def _row(name, position, position_rank, projected_points, tier=4):
    threshold = {"QB": 18.0, "RB": 24.5, "WR": 24.5, "TE": 12.0}[position]
    return {
        "player_name_clean": name,
        "position": position,
        "position_rank": position_rank,
        "projected_points": projected_points,
        "tier": tier,
        "tier_next_threshold": threshold,
        "tier_next_projection_drop": 36.0 if position == "QB" and position_rank == 1 else (24.0 if position == "TE" and position_rank == 2 else 0.0),
        "tier_next_vorp_drop": 36.0 if position == "QB" and position_rank == 1 else (24.0 if position == "TE" and position_rank == 2 else 0.0),
    }


def _available_board():
    rows = [
        _row("Top RB", "RB", 13, 330.0),
        _row("Next RB", "RB", 14, 310.0),
        _row("Top WR", "WR", 3, 325.0),
        _row("Top QB", "QB", 1, 490.0, tier=1),
        _row("Top TE", "TE", 2, 325.0, tier=1),
    ]
    rows.extend(
        _row(f"RB {rank}", "RB", rank, 300.0 - rank)
        for rank in range(15, 35)
    )
    rows.extend(
        _row(f"WR {rank}", "WR", rank, 300.0 - rank)
        for rank in range(4, 39)
    )
    rows.extend(
        _row(f"QB {rank}", "QB", rank, 480.0 - rank, tier=2)
        for rank in range(2, 13)
    )
    rows.extend(
        _row(f"TE {rank}", "TE", rank, 300.0 - rank, tier=2)
        for rank in range(3, 13)
    )
    return pd.DataFrame(rows)


def test_keeper_depletion_metadata_tracks_remaining_position_supply():
    board = add_position_demand_metadata(_available_board(), REPLACEMENT_RANKS)
    result = add_keeper_depletion_metadata(board, KEEPER_COUNTS).set_index("position")

    assert result.loc["RB", "position_keeper_count"].iloc[0] == 12
    assert result.loc["RB", "position_remaining_replacement_demand"].iloc[0] == 22
    assert result.loc["WR", "position_remaining_replacement_demand"].iloc[0] == 36
    assert result.loc["TE", "position_remaining_replacement_demand"].iloc[0] == 11
    assert result.loc["QB", "position_remaining_replacement_demand"].iloc[0] == 12

    assert result.loc["RB", "keeper_depletion_multiplier"].iloc[0] > 1.20
    assert result.loc["WR", "keeper_depletion_multiplier"].iloc[0] > 1.0
    assert result.loc["QB", "keeper_depletion_multiplier"].iloc[0] == 1.0


def test_available_supply_scarcity_promotes_depleted_rb_wr_over_one_start_qb_te():
    board = add_position_demand_metadata(_available_board(), REPLACEMENT_RANKS)
    board = add_keeper_depletion_metadata(board, KEEPER_COUNTS)
    result = add_live_tier_scarcity(board).set_index("player_name_clean")

    assert result.loc["Top RB", "position_available_rank"] == 1
    assert result.loc["Next RB", "position_available_rank"] == 2
    assert result.loc["Top RB", "position_supply_scarcity_score"] > result.loc[
        "Next RB", "position_supply_scarcity_score"
    ]

    assert result.loc["Top RB", "tier_scarcity_score"] > result.loc[
        "Top QB", "tier_scarcity_score"
    ]
    assert result.loc["Top WR", "tier_scarcity_score"] > result.loc[
        "Top TE", "tier_scarcity_score"
    ]
    assert result.loc["Top RB", "tier_scarcity_score"] >= 80.0
    assert result.loc["Top WR", "tier_scarcity_score"] >= 65.0
    assert result.loc["Top QB", "tier_scarcity_score"] <= 60.0
    assert result.loc["Top TE", "tier_scarcity_score"] <= 65.0


def test_unavailable_counts_are_inferred_from_missing_replacement_level_ranks():
    board = add_position_demand_metadata(_available_board(), REPLACEMENT_RANKS)

    assert infer_unavailable_position_counts(board) == KEEPER_COUNTS


def test_draft_assistant_applies_available_pool_depletion_before_live_scarcity(monkeypatch):
    board = add_position_demand_metadata(_available_board(), REPLACEMENT_RANKS)
    board["draft_rank"] = range(1, len(board) + 1)
    observed = {"depletion_seen": False}

    def inspect_live_scarcity(df):
        observed["depletion_seen"] = "keeper_depletion_multiplier" in df.columns
        assert df.loc[df["position"] == "RB", "position_keeper_count"].iloc[0] == 12
        assert df.loc[df["position"] == "WR", "position_keeper_count"].iloc[0] == 2
        result = df.copy()
        result["tier_scarcity_score"] = 0.0
        return result

    def add_brain_identity(df, _context):
        result = df.copy()
        result["brain_score"] = range(len(result), 0, -1)
        result["brain_recommendation"] = "WAIT"
        result["brain_reasons"] = [[] for _ in range(len(result))]
        result["brain_warnings"] = [[] for _ in range(len(result))]
        return result

    monkeypatch.setattr(draft_assistant, "add_live_tier_scarcity", inspect_live_scarcity)
    monkeypatch.setattr(draft_assistant, "recalculate_live_draft_score", lambda df: df.copy())
    monkeypatch.setattr(draft_assistant, "add_pressure_meter", lambda df: df.copy())
    monkeypatch.setattr(draft_assistant, "add_draft_brain", add_brain_identity)

    draft_assistant.build_draft_assistant_from_rankings(board, draft_context={})

    assert observed["depletion_seen"] is True
