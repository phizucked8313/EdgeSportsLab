from fantasy_draft_model.rankings import build_draft_rankings
from fantasy_draft_model.engines.draft_brain_engine import add_draft_brain
from fantasy_draft_model.engines.pressure_meter_engine import add_pressure_meter


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

    rankings = add_pressure_meter(
        rankings
    )

    # Draft Brain needs context such as:
    # picks_until_user
    # roster state
    # positional runs
    # pressure
    #
    # We will expand this context as the live
    # draft assistant becomes more interactive.
    rankings = add_draft_brain(
        rankings,
        draft_context,
    )

    rankings = (
        rankings
        .sort_values(
            "brain_score",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    return rankings


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
        "tier_status",
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
