from fantasy_draft_model.rankings import (
    add_available_pool_depletion_metadata,
    build_draft_rankings,
    infer_unavailable_position_counts,
    recalculate_live_draft_score,
)
from fantasy_draft_model.engines.draft_brain_engine import add_draft_brain
from fantasy_draft_model.engines.pressure_meter_engine import add_pressure_meter
from fantasy_draft_model.engines.tier_engine import add_live_tier_scarcity


LIVE_SCORE_DEFAULTS = {
    "vorp": 0.0,
    "edgescore": 0.0,
    "projection_score": 0.0,
    "projection_confidence": 0.0,
}

EMPTY_BRAIN_COLUMNS = {
    "brain_score": "float64",
    "brain_recommendation": "object",
    "brain_reasons": "object",
    "brain_warnings": "object",
}


def build_draft_assistant_from_rankings(
    rankings,
    draft_context=None,
):
    """Apply live draft pressure and Draft Brain context to built rankings."""
    if draft_context is None:
        draft_context = {}

    live_rankings = rankings.copy()
    for column, default in LIVE_SCORE_DEFAULTS.items():
        if column not in live_rankings.columns:
            live_rankings[column] = default

    unavailable_counts = infer_unavailable_position_counts(live_rankings)
    live_rankings = add_available_pool_depletion_metadata(
        live_rankings,
        unavailable_counts,
    )
    live_rankings = add_live_tier_scarcity(live_rankings)
    live_rankings = recalculate_live_draft_score(live_rankings)
    live_rankings = add_pressure_meter(live_rankings)
    if live_rankings.empty:
        for column, dtype in EMPTY_BRAIN_COLUMNS.items():
            live_rankings[column] = live_rankings.index.to_series().astype(dtype)
    else:
        live_rankings = add_draft_brain(
            live_rankings,
            draft_context,
        )
    return (
        live_rankings
        .sort_values(
            "brain_score",
            ascending=False,
        )
        .reset_index(drop=True)
    )


def build_draft_assistant(
    league_key,
    draft_context=None,
):
    """
    Build the EdgeIQ Draft Assistant board.

    Uses the same injury-adjusted EdgeIQ rankings
    that power the mock draft and CPU draft.
    """

    if draft_context is None:
        draft_context = {}

    print("\nBuilding EdgeIQ Draft Assistant...")

    rankings = build_draft_rankings(
        league_key
    ).copy()

    return build_draft_assistant_from_rankings(
        rankings,
        draft_context=draft_context,
    )


def show_top_recommendations(
    assistant_board,
    limit=20,
):
    """
    Display the best EdgeIQ recommendations.
    """

    columns = [
        "player_name_clean",
        "position",
        "team",
        "draft_rank",
        "position_rank_label",
        "tier",
        "tier_remaining",
        "tier_scarcity_score",
        "tier_next_projection_drop",
        "tier_next_vorp_drop",
        "projected_points",
        "vorp",
        "edgescore",
        "brain_score",
        "brain_recommendation",
        "brain_reasons",
        "brain_warnings",
    ]

    columns = [
        column
        for column in columns
        if column in assistant_board.columns
    ]

    print(
        assistant_board[
            columns
        ]
        .head(limit)
        .to_string(index=False)
    )


def main():

    draft_context = {
        "picks_until_user": 10,
    }

    board = build_draft_assistant(
        "drunk_sundays",
        draft_context=draft_context,
    )

    print("\n========================================")
    print(" EDGEIQ DRAFT ASSISTANT")
    print("========================================\n")

    show_top_recommendations(
        board,
        limit=20,
    )


if __name__ == "__main__":
    main()
