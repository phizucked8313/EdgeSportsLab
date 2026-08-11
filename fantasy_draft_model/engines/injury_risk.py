import pandas as pd


# ============================================================
# EDGEIQ INJURY / DURABILITY ENGINE
# ============================================================


# Higher number = more concerning injury type
INJURY_SEVERITY = {

    # Soft tissue
    "hamstring": 22,
    "groin": 20,
    "calf": 18,
    "quad": 18,
    "hip flexor": 17,
    "oblique": 15,

    # Foot / ankle
    "turf toe": 18,
    "high ankle sprain": 18,
    "ankle sprain": 12,

    # Knee
    "acl": 28,
    "mcl": 18,
    "meniscus": 18,
    "knee": 15,

    # Achilles
    "achilles": 30,

    # Shoulder / upper body
    "shoulder": 14,
    "collarbone": 10,
    "broken collarbone": 10,
    "wrist": 8,
    "hand": 6,
    "finger": 4,

    # Head / spine
    "concussion": 16,
    "back": 20,
    "neck": 24,

    # Generic
    "other": 10,
}


SOFT_TISSUE_INJURIES = {
    "hamstring",
    "groin",
    "calf",
    "quad",
    "hip flexor",
    "oblique",
}


MAJOR_INJURIES = {
    "acl",
    "achilles",
    "neck",
    "back",
}


# ============================================================
# POSITION BASELINE RISK
# ============================================================

POSITION_RISK = {

    "QB": 5,

    "RB": 12,

    "WR": 9,

    "TE": 10,
}


# ============================================================
# MANUAL INJURY HISTORY
# ============================================================

# Later we will load this from a CSV/database.
#
# For now, this dictionary lets us manually
# add important injuries we know about.

PLAYER_INJURY_HISTORY = {

    # Example:
    #
    # "Player Name": [
    #     {
    #         "season": 2025,
    #         "injury": "hamstring",
    #         "games_missed": 3
    #     },
    #     {
    #         "season": 2024,
    #         "injury": "hamstring",
    #         "games_missed": 2
    #     }
    # ],

}


# ============================================================
# SCORE ONE PLAYER
# ============================================================

def calculate_injury_profile(
    player_name,
    position,
    games_played_last_3_years=None
):
    """
    Calculate injury-related EdgeIQ metrics.

    Returns:
        durability_score
        injury_risk_score
        soft_tissue_risk
        major_injury_risk
        recurrence_risk
        games_missed
    """

    history = PLAYER_INJURY_HISTORY.get(
        player_name,
        []
    )


    total_risk = POSITION_RISK.get(
        position,
        8
    )


    soft_tissue_risk = 0
    major_injury_risk = 0
    recurrence_risk = 0
    games_missed = 0


    injury_counts = {}


    for injury_record in history:

        injury_type = (
            injury_record
            .get(
                "injury",
                "other"
            )
            .lower()
            .strip()
        )


        missed = injury_record.get(
            "games_missed",
            0
        )


        games_missed += missed


        severity = INJURY_SEVERITY.get(
            injury_type,
            INJURY_SEVERITY["other"]
        )


        # Base injury severity
        total_risk += severity


        # Missed games matter too
        total_risk += (
            missed * 1.5
        )


        # Count repeated injuries
        injury_counts[
            injury_type
        ] = (
            injury_counts.get(
                injury_type,
                0
            )
            + 1
        )


        # Soft tissue penalties
        if injury_type in SOFT_TISSUE_INJURIES:

            soft_tissue_risk += (
                severity
                + missed
            )


        # Major injury penalties
        if injury_type in MAJOR_INJURIES:

            major_injury_risk += (
                severity
                + missed
            )


    # ========================================================
    # RECURRENCE
    # ========================================================

    for injury_type, count in (
        injury_counts.items()
    ):

        if count > 1:

            recurrence_penalty = (
                (count - 1) * 12
            )


            # Soft tissue recurrence is worse
            if (
                injury_type
                in SOFT_TISSUE_INJURIES
            ):

                recurrence_penalty += (
                    (count - 1) * 8
                )


            recurrence_risk += (
                recurrence_penalty
            )


    total_risk += recurrence_risk


    # ========================================================
    # AVAILABILITY HISTORY
    # ========================================================

    if (
        games_played_last_3_years
        is not None
    ):

        expected_games = 51

        games_played = min(
            games_played_last_3_years,
            expected_games
        )


        availability_rate = (
            games_played
            / expected_games
        )


        missed_rate = (
            1
            - availability_rate
        )


        total_risk += (
            missed_rate * 25
        )


    # ========================================================
    # CAP SCORES
    # ========================================================

    injury_risk_score = min(
        max(
            round(total_risk, 1),
            0
        ),
        100
    )


    soft_tissue_risk = min(
        round(
            soft_tissue_risk,
            1
        ),
        100
    )


    major_injury_risk = min(
        round(
            major_injury_risk,
            1
        ),
        100
    )


    recurrence_risk = min(
        round(
            recurrence_risk,
            1
        ),
        100
    )


    # Durability is inverse of risk
    durability_score = round(
        100
        - injury_risk_score,
        1
    )


    return {

        "durability_score":
            durability_score,

        "injury_risk_score":
            injury_risk_score,

        "soft_tissue_risk":
            soft_tissue_risk,

        "major_injury_risk":
            major_injury_risk,

        "recurrence_risk":
            recurrence_risk,

        "historical_games_missed":
            games_missed,
    }


# ============================================================
# ADD INJURY SCORES TO DATAFRAME
# ============================================================

def add_injury_scores(df):
    """
    Add EdgeIQ injury metrics to
    the master player DataFrame.

    QB rushing/contact exposure is used
    as a small added risk modifier.
    """

    df = df.copy()

    profiles = []

    for _, row in df.iterrows():

        player_name = row[
            "player_name_clean"
        ]

        position = row[
            "position"
        ]

        profile = calculate_injury_profile(
            player_name,
            position
        )

        # -----------------------------------------
        # QB CONTACT EXPOSURE
        # -----------------------------------------

        if (
            position == "QB"
            and "qb_contact_exposure" in df.columns
        ):

            contact_exposure = row.get(
                "qb_contact_exposure",
                0
            )

            # Maximum added QB rushing/contact
            # penalty = 12 injury-risk points.
            contact_penalty = (
                contact_exposure
                / 100
            ) * 12

            profile[
                "qb_contact_exposure"
            ] = round(
                contact_exposure,
                1
            )

            profile[
                "qb_contact_injury_penalty"
            ] = round(
                contact_penalty,
                1
            )

            adjusted_risk = (
                profile[
                    "injury_risk_score"
                ]
                + contact_penalty
            )

            adjusted_risk = min(
                adjusted_risk,
                100
            )

            profile[
                "injury_risk_score"
            ] = round(
                adjusted_risk,
                1
            )

            profile[
                "durability_score"
            ] = round(
                100
                - adjusted_risk,
                1
            )

        else:

            profile[
                "qb_contact_exposure"
            ] = 0.0

            profile[
                "qb_contact_injury_penalty"
            ] = 0.0

        profiles.append(
            profile
        )

    injury_df = pd.DataFrame(
        profiles,
        index=df.index
    )

    df = pd.concat(
        [
            df,
            injury_df
        ],
        axis=1
    )

    return df




# ============================================================
# INJURY RISK LABEL
# ============================================================

def injury_risk_label(
    risk_score
):

    if risk_score <= 15:

        return "Very Low"


    if risk_score <= 30:

        return "Low"


    if risk_score <= 45:

        return "Moderate"


    if risk_score <= 60:

        return "Elevated"


    if risk_score <= 75:

        return "High"


    return "Very High"


# ============================================================
# TEST ENGINE
# ============================================================

def main():

    test_players = [

        {
            "player_name_clean":
                "Healthy Player",

            "position":
                "WR"
        },

        {
            "player_name_clean":
                "Soft Tissue Player",

            "position":
                "WR"
        }
    ]


    PLAYER_INJURY_HISTORY[
        "Soft Tissue Player"
    ] = [

        {
            "season": 2025,
            "injury": "hamstring",
            "games_missed": 3
        },

        {
            "season": 2024,
            "injury": "hamstring",
            "games_missed": 2
        },

        {
            "season": 2023,
            "injury": "groin",
            "games_missed": 1
        }
    ]


    test_df = pd.DataFrame(
        test_players
    )


    test_df = add_injury_scores(
        test_df
    )


    test_df[
        "injury_risk_label"
    ] = (

        test_df[
            "injury_risk_score"
        ]

        .apply(
            injury_risk_label
        )
    )


    print(
        "\nEDGEIQ INJURY ENGINE\n"
    )


    print(
        test_df.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()