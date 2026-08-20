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
from fantasy_draft_model.engines.draft_brain_engine import (
    add_draft_brain,
)

from fantasy_draft_model.engines.draft_order_engine import (
    get_managers_before_user,
)

from fantasy_draft_model.engines.manager_need_threat_engine import (
    calculate_manager_need_threat,
    get_position_threat,
)

from fantasy_draft_model.models.league_manager import (
    get_user_draft_slot,
    get_league,
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

    league_name = "Drunk Sundays"

    league = get_league(
        league_name
    )

    user_slot = get_user_draft_slot(
        league_name
    )

    df = build_draft_rankings()

    df = recalculate_after_keepers(
        df,
        "league_name"
    )

    df = add_pressure_meter(
    df
)
    
    available = get_best_available(
        df,
        league_name="league_name",
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
        user_slot=user_slot,
        rounds=league["rounds"],
        team_count=league["team_count"]
    )

    df = add_draft_brain(
        df,
        draft_context
)

    managers_before = get_managers_before_user(
        draft_context["slots_before_user"],
        league_name=league_name
)       

    threat_df = calculate_manager_need_threat(
        df,
        draft_context["slots_before_user"],
        league_name=league_name
)



    available = get_best_available(
        df,
        league_name="league_name",
        limit=limit
)

    print("\nPOSITION THREAT")

    for _, threat in threat_df.iterrows():

        print(
            f"{threat['position']}: "
            f"{threat['threat_label']} | "
            f"{int(threat['needy_managers'])} needy managers"
    )

    print()

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

    print("\nManagers Before Your Pick")

    for manager in managers_before:

        print(
            f"Slot {manager['draft_slot']}: "
            f"{manager['manager']}"
    )

    print("\n")

    
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
            f"Tier: {row['position']} Tier {int(row['tier'])} | "
            f"{int(row['tier_remaining'])} remaining | "
            f"Scarcity {row['tier_scarcity_score']:.1f}/100 | "
            f"Next projection drop {row['tier_next_projection_drop']:.1f} | "
            f"Next VORP drop {row['tier_next_vorp_drop']:.1f}"
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
            f"Draft Brain: "
            f"{row['brain_score']:.0f}/100 "
            f"{row['brain_recommendation']}"
    )

        if row["brain_reasons"]:

            print(
            "Why:"
        )

        for reason in row["brain_reasons"]:

            print(
                f"  + {reason}"
            )

        if row["brain_warnings"]:

            print(
                "Warnings:"
        )

        for warning in row["brain_warnings"]:

            print(
                f"  - {warning}"
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

        position_threat = get_position_threat(
            df,
            draft_context["slots_before_user"],
            row["position"],
            league_name=league_name
)

        print(
            f"{row['position']} Threat: "
            f"{position_threat['threat_label']} "
            f"({int(position_threat['needy_managers'])} needy managers)"
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
