import pandas as pd

from fantasy_draft_model.models.projections import create_master_player_table
from fantasy_draft_model.engines.injury_risk import (
    add_injury_scores,
    injury_risk_label,
)


# ============================================================
# EDGEIQ PLAYER PROFILES
# ============================================================


def build_player_profiles(league_key):
    """
    Build the complete EdgeIQ player profile table.

    Starts with the master player table,
    then adds injury and durability metrics.
    """

    print("\nBuilding EdgeIQ player profiles...")

    df = create_master_player_table(league_key)

    # -----------------------------------------
    # ADD INJURY / DURABILITY SCORES
    # -----------------------------------------

    #df = add_injury_scores(
    #   df
    #)

    #df["injury_risk_label"] = (
    #    df["injury_risk_score"]
    #    .apply(
    #        injury_risk_label
    #    )
    #)

    return df


# ============================================================
# DISPLAY PROFILE
# ============================================================

def display_player_profile(
    df,
    player_name
):
    """
    Display one player's EdgeIQ profile.
    """

    player = df[
        df["player_name_clean"]
        .str.lower()
        == player_name.lower()
    ]

    if player.empty:

        print(
            f"\nPlayer not found: "
            f"{player_name}"
        )

        return


    columns = [

        # Identity
        "player_name_clean",
        "position",
        "team",

        # Production
        "games_played",
        "custom_fantasy_points",
        "custom_points_per_game",

        # Opportunity
        "carries",
        "targets",
        "receptions",
        "target_share",
        "receiving_air_yards",
        "air_yards_share",
        "wopr",

        # Efficiency
        "yards_per_carry",
        "yards_per_target",
        "yards_per_reception",
        "catch_rate",

        # Big games
        "games_300_pass",
        "games_100_rush",
        "games_100_receive",

        # Injury
        "durability_score",
        "injury_risk_score",
        "injury_risk_label",
        "soft_tissue_risk",
        "major_injury_risk",
        "recurrence_risk",
        "historical_games_missed",
    ]


    available_columns = [

        column
        for column in columns
        if column in player.columns
    ]


    print(
        "\n=========================================="
    )

    print(
        "EDGEIQ PLAYER PROFILE"
    )

    print(
        "==========================================\n"
    )


    print(

        player[
            available_columns
        ]

        .round(2)

        .to_string(
            index=False
        )
    )


# ============================================================
# TEST
# ============================================================

def main():

    profiles_df = (
        build_player_profiles("drunk_sundays")
    )


    print(
        f"\nPlayer profiles created: "
        f"{len(profiles_df):,}"
    )


    print(
        "\n=========================================="
    )

    print(
        "TOP 30 PLAYER PROFILES"
    )

    print(
        "==========================================\n"
    )


    columns = [

        "player_name_clean",
        "position",
        "team",

        "custom_fantasy_points",
        "custom_points_per_game",

        "durability_score",
        "injury_risk_score",
        "injury_risk_label",

        "soft_tissue_risk",
        "recurrence_risk",
    ]


    print(

        profiles_df[
            columns
        ]

        .head(30)

        .round(2)

        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()

    