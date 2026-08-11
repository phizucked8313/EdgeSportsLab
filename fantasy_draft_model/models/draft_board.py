"""
EdgeIQ Draft Board
Version 1
"""

from fantasy_draft_model.rankings import build_draft_rankings
from fantasy_draft_model.draft_state import (
    get_drafted_player_names,
)
from fantasy_draft_model.keepers import (
    get_keeper_player_names,
)

from fantasy_draft_model.engines.keeper_adjustment_engine import (
    recalculate_after_keepers,
)

from fantasy_draft_model.engines.pressure_meter_engine import (
    add_pressure_meter,
)

from fantasy_draft_model.engines.what_if_i_wait_engine import (
    analyze_wait,
)

from fantasy_draft_model.engines.run_detector_engine import (
    calculate_run_scores,
    get_position_run,
)

from fantasy_draft_model.engines.roster_tracker_engine import (
    display_team_needs,
)

from fantasy_draft_model.engines.snake_draft_engine import (
    get_draft_context,
)

from fantasy_draft_model.draft_state import (
    get_drafted_player_names,
    load_draft_state,

)






def get_best_available(
    df,
    league_name="Drunk Sundays",
    limit=20
):
    """
    Remove both keepers and drafted players,
    then return the best players remaining.
    """

    drafted_players = (
        get_drafted_player_names()
    )

    keeper_players = (
        get_keeper_player_names(
            league_name
        )
    )


    unavailable_players = {

        player.lower()

        for player
        in (
            drafted_players
            + keeper_players
        )
    }


    available = df[

        ~df[
            "player_name_clean"
        ]
        .str.lower()
        .isin(
            unavailable_players
        )

    ].copy()


    return (

        available
        .sort_values(
            "draft_rank"
        )
        .head(
            limit
        )
    )



def display_draft_board(limit=20):

    df = build_draft_rankings()

    df = recalculate_after_keepers(
        df,
        "Drunk Sundays"
    )

    df = add_pressure_meter(
    df
)
    
    available = get_best_available(
        df,
        league_name="Drunk Sundays",
        limit=limit
    )
    run_df = calculate_run_scores(
        df,
        recent_picks=8
)

    state = load_draft_state()

    current_pick = state.get(
        "current_pick",
        1
    )

    draft_context = get_draft_context(
        current_pick=current_pick,
        user_slot=1,
        rounds=15,
        team_count=12
    )

    print("\nDRAFT CONTEXT")

    print(
        f"Round: {draft_context['round']}"
    )

    print(
        f"Overall Pick: {draft_context['current_pick']}"
    )

    print(
        f"Current Draft Slot: {draft_context['current_draft_slot']}"
    )

    print(
        f"Your Next Pick: {draft_context['next_user_pick']}"
    )

    print(
        f"Picks Until Your Turn: {draft_context['picks_until_user']}"
    )

    print(
        f"Draft Slots Before You: {draft_context['slots_before_user']}"
    )
    
    print("\nPOSITION RUN MONITOR")

    for _, run in run_df.iterrows():

        print(
            f"{run['position']}: "
            f"{int(run['position_picks'])} "
            f"of last "
            f"{int(run['recent_picks'])} picks | "
            f"{run['run_label']}"
    )


    print("\n")

    display_team_needs(
        df
    )

    print(
        "\n=============================================="
    )

    print(
        "             EDGEIQ DRAFT WAR ROOM"
    )

    print(
        "==============================================\n"
    )

    print(
        "BEST AVAILABLE PLAYERS\n"
    )

    for _, row in available.iterrows():

        print(
            f"#{int(row['draft_rank'])} "
            f"{row['player_name_clean']}"
        )

        print(
            f"{row['position_rank_label']} | "
            f"{row['team']} | "
            f"Tier {int(row['tier'])}"
        )

        print(
            f"EdgeScore: "
            f"{row['edgescore']:.1f}"
        )

        print(
            f"Draft Score: "
            f"{row['draft_score']:.1f}"
        )

        print(
            f"Projected Points: "
            f"{row['projected_points']:.1f}"
        )

        print(
            f"VORP: "
            f"{row['vorp']:.1f}"
        )

        print(
            f"Confidence: "
            f"{row['projection_confidence']:.1f}%"
        )

        print(
            f"Tier Status: "
            f"{row['tier_status']}"
        )

        print(
            f"Pressure: "
            f"{row['pressure_bar']} "
            f"{row['pressure_score']:.0f}/100 "
            f"{row['pressure_label']}"
)

    wait_report = analyze_wait(df,

        row["player_name_clean"],
        picks_until_next=max(
            1,
            draft_context["picks_until_user"]
        )
)

    print(
            f"What If I Wait?: "
            f"{wait_report['recommendation']}"
)

    print(
            f"Reason: "
            f"{wait_report['reason']}"
)

    print(
            f"Estimated Survival: "
            f"{wait_report['survival_score']:.0f}/100"
)
    print(
        f"Picks Until Next Pick: "
        f"{draft_context['picks_until_user']}"
    )
    if wait_report["next_player"]:

        print(
            f"Next {row['position']} Option: "
            f"{wait_report['next_player']}"
    )

        print(
            f"Projected Drop: "
            f"{wait_report['projection_drop']:.1f} pts"
    )

        print(
            f"VORP Drop: "
            f"{wait_report['vorp_drop']:.1f}"
    )

    position_run = get_position_run(
        df,
        row["position"],
        recent_picks=8
)

    print(
        f"{row['position']} Run: "
        f"{position_run['run_label']} "
        f"({int(position_run['position_picks'])} "
        f"of last 8 picks)"
)
    print(
        f"Draft Advice: "
        f"{row['draft_value']}"
        )


    print(
            f"Hidden Edge: "
            f"{row['hidden_edge']}"
        )

    print(
            "----------------------------------------------"
        )


def main():

    display_draft_board(
        limit=20
    )


if __name__ == "__main__":

    main()