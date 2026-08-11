"""
EdgeIQ Position Run Detector
Version 1

Detects whether a position run is starting,
active, or accelerating during a live draft.
"""

import pandas as pd

from fantasy_draft_model.draft_state import (
    load_draft_state,
)


POSITIONS = [
    "QB",
    "RB",
    "WR",
    "TE",
]


def get_recent_drafted_players(
    rankings_df: pd.DataFrame,
    recent_picks=8,
):
    """
    Match recent drafted player names
    back to the rankings DataFrame
    so we know their positions.
    """

    state = load_draft_state()

    drafted = state.get(
        "drafted_players",
        []
    )

    recent = drafted[
        -recent_picks:
    ]

    rows = []

    for pick in recent:

        player_name = pick[
            "player_name"
        ]

        match = rankings_df[
            rankings_df[
                "player_name_clean"
            ].str.lower()
            == player_name.lower()
        ]

        if match.empty:
            continue

        player = match.iloc[0]

        rows.append(
            {
                "player_name":
                    player_name,

                "position":
                    player["position"],

                "pick_number":
                    pick["pick_number"],
            }
        )

    return pd.DataFrame(
        rows
    )


def calculate_run_scores(
    rankings_df: pd.DataFrame,
    recent_picks=8,
):
    """
    Calculate a 0-100 run score
    for QB/RB/WR/TE.
    """

    recent_df = get_recent_drafted_players(
        rankings_df,
        recent_picks
    )

    results = []

    for position in POSITIONS:

        if recent_df.empty:

            count = 0

        else:

            count = (
                recent_df[
                    recent_df["position"]
                    == position
                ]
                .shape[0]
            )

        run_rate = (
            count
            / recent_picks
        )

        run_score = min(
            100,
            run_rate * 200
        )

        if count >= 5:

            label = "RUN ACTIVE"

        elif count >= 3:

            label = "RUN STARTING"

        elif count == 2:

            label = "WATCH"

        else:

            label = "NORMAL"

        results.append(
            {
                "position":
                    position,

                "recent_picks":
                    recent_picks,

                "position_picks":
                    count,

                "run_score":
                    round(
                        run_score,
                        1
                    ),

                "run_label":
                    label,
            }
        )

    return pd.DataFrame(
        results
    )


def get_position_run(
    rankings_df: pd.DataFrame,
    position,
    recent_picks=8,
):
    """
    Return run intelligence for one position.
    """

    run_df = calculate_run_scores(
        rankings_df,
        recent_picks
    )

    match = run_df[
        run_df["position"]
        == position
    ]

    if match.empty:

        return {
            "position":
                position,

            "position_picks":
                0,

            "run_score":
                0,

            "run_label":
                "NORMAL",
        }

    return match.iloc[0].to_dict()


def main():

    print(
        "EdgeIQ Position Run Detector ready."
    )


if __name__ == "__main__":

    main()