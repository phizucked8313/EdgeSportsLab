"""
EdgeIQ What If I Wait Engine
Version 1

Evaluates whether a fantasy manager should draft
a player now or risk waiting until the next pick.

Version 1 uses:
- Draft Pressure
- VORP
- Tier
- Projected Points
- Draft Score
- Number of picks until next selection
"""

import pandas as pd


# ============================================================
# ESTIMATE SURVIVAL
# ============================================================

def estimate_survival_score(
    pressure_score,
    picks_until_next
):
    """
    Estimate a player's chance of surviving
    until the user's next pick.

    IMPORTANT:
    This is currently a heuristic estimate,
    not a calibrated probability.
    """

    pressure_score = max(
        0,
        min(
            100,
            pressure_score
        )
    )

    picks_until_next = max(
        1,
        picks_until_next
    )

    # Higher pressure means lower survival.
    base_survival = (
        100
        - pressure_score
    )

    # More picks between turns means more danger.
    pick_penalty = (
        picks_until_next
        * 3
    )

    survival_score = (
        base_survival
        - pick_penalty
    )

    return round(
        max(
            0,
            min(
                100,
                survival_score
            )
        ),
        1
    )


# ============================================================
# FIND NEXT SAME-POSITION OPTIONS
# ============================================================

def get_fallback_players(
    df: pd.DataFrame,
    player_row,
    number_of_players=3
):
    """
    Find the next best available players
    at the same position.
    """

    position = (
        player_row["position"]
    )

    draft_rank = (
        player_row["draft_rank"]
    )

    fallback = df[
        (
            df["position"]
            == position
        )
        &
        (
            df["draft_rank"]
            > draft_rank
        )
    ].copy()

    fallback = (
        fallback
        .sort_values(
            "draft_rank"
        )
        .head(
            number_of_players
        )
    )

    return fallback


# ============================================================
# VALUE DROP
# ============================================================

def calculate_value_drop(
    player_row,
    fallback_df
):
    """
    Measure what is lost if the user
    passes on the current player.
    """

    if fallback_df.empty:

        return {
            "next_player": None,
            "projection_drop": 0.0,
            "vorp_drop": 0.0,
            "draft_score_drop": 0.0,
        }

    next_player = (
        fallback_df.iloc[0]
    )

    projection_drop = (
        player_row["projected_points"]
        - next_player["projected_points"]
    )

    vorp_drop = (
        player_row["vorp"]
        - next_player["vorp"]
    )

    draft_score_drop = (
        player_row["draft_score"]
        - next_player["draft_score"]
    )

    return {

        "next_player":
            next_player["player_name_clean"],

        "projection_drop":
            round(
                projection_drop,
                1
            ),

        "vorp_drop":
            round(
                vorp_drop,
                1
            ),

        "draft_score_drop":
            round(
                draft_score_drop,
                1
            ),
    }


# ============================================================
# DECISION
# ============================================================

def create_wait_recommendation(
    player_row,
    survival_score,
    value_drop
):
    """
    Create EdgeIQ's draft recommendation.
    """

    player_row.get(
    "pressure_score",
    0,
)
    pressure = float(
    player_row.get(
        "pressure_score",
        0,
    )
)
    
    tier_status = (
        player_row["tier_status"]
    )

    projection_drop = (
        value_drop[
            "projection_drop"
        ]
    )

    vorp_drop = (
        value_drop[
            "vorp_drop"
        ]
    )


    # -----------------------------------------
    # DO NOT WAIT
    # -----------------------------------------

    if tier_status == "LAST PLAYER IN TIER":

        return (
            "DO NOT WAIT",
            "Last player remaining in the current tier."
        )


    if (
        pressure >= 85
        and survival_score <= 25
    ):

        return (
            "DO NOT WAIT",
            "High draft pressure and low chance of surviving."
        )


    if vorp_drop >= 40:

        return (
            "DO NOT WAIT",
            "Large positional value drop behind this player."
        )


    if projection_drop >= 35:

        return (
            "DO NOT WAIT",
            "Large projected fantasy-point drop to the next option."
        )


    # -----------------------------------------
    # CAUTION
    # -----------------------------------------

    if survival_score <= 45:

        return (
            "RISKY TO WAIT",
            "Player may not survive until your next selection."
        )


    # -----------------------------------------
    # SAFE
    # -----------------------------------------

    return (
        "SAFE TO WAIT",
        "Comparable options may still be available later."
    )


# ============================================================
# COMPLETE WHAT-IF REPORT
# ============================================================

def analyze_wait(
    df: pd.DataFrame,
    player_name,
    picks_until_next=10
):
    """
    Analyze whether the user should draft
    a player now or wait.
    """

    player = df[
        df["player_name_clean"]
        .str.lower()
        == player_name.lower()
    ]


    if player.empty:

        return {
            "error":
                f"Player not found: {player_name}"
        }


    player_row = (
        player.iloc[0]
    )


    survival_score = (
    estimate_survival_score(
        player_row.get(
            "pressure_score",
            0,
        ),
        picks_until_next,
    )
)


    fallback_df = (
        get_fallback_players(
            df,
            player_row
        )
    )


    value_drop = (
        calculate_value_drop(
            player_row,
            fallback_df
        )
    )


    recommendation, reason = (
        create_wait_recommendation(
            player_row,
            survival_score,
            value_drop
        )
    )


    fallback_names = (
        fallback_df[
            "player_name_clean"
        ]
        .tolist()
    )


    return {

        "player":
            player_name,

        "position":
            player_row[
                "position"
            ],

        "tier": int(
            player_row.get("tier", 0)
            if pd.notna(player_row.get("tier", 0))
            else 0
        ),

        "pressure_score": float(
            player_row.get(
                "pressure_score",
                0,
            )
        ),

        "survival_score":
            survival_score,

        "picks_until_next":
            picks_until_next,

        "fallback_players":
            fallback_names,

        "next_player":
            value_drop[
                "next_player"
            ],

        "projection_drop":
            value_drop[
                "projection_drop"
            ],

        "vorp_drop":
            value_drop[
                "vorp_drop"
            ],

        "draft_score_drop":
            value_drop[
                "draft_score_drop"
            ],

        "recommendation":
            recommendation,

        "reason":
            reason,
    }