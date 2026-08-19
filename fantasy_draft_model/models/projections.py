import numpy as np
import pandas as pd

from fantasy_draft_model.integrations.data_loader import load_weekly_player_stats
from fantasy_draft_model.integrations.roster_loader import prepare_fantasy_rosters






# ============================================================
# EDGEIQ MASTER PLAYER TABLE
# ============================================================


FANTASY_POSITIONS = [
    "QB",
    "RB",
    "WR",
    "TE",
]


# ============================================================
# CLEAN WEEKLY DATA
# ============================================================

def prepare_weekly_data():
    """
    Load 2025 weekly NFL data and keep only
    fantasy-relevant offensive players.
    """

    df = load_weekly_player_stats()

    # Regular season only
    if "season_type" in df.columns:
        df = df[
            df["season_type"] == "REG"
        ].copy()

    # Fantasy positions only
    df = df[
        df["position"].isin(
            FANTASY_POSITIONS
        )
    ].copy()

    # Use full display name
    df["player_name_clean"] = (
        df["player_display_name"]
        .fillna(
            df["player_name"]
        )
    )

    return df


# ============================================================
# BONUS GAME FLAGS
# ============================================================

def add_bonus_flags(df):
    """
    Identify individual games that triggered
    our fantasy league bonuses.
    """

    df = df.copy()

    df["game_300_pass"] = (
        df["passing_yards"]
        .fillna(0)
        >= 300
    ).astype(int)

    df["game_100_rush"] = (
        df["rushing_yards"]
        .fillna(0)
        >= 100
    ).astype(int)

    df["game_100_receive"] = (
        df["receiving_yards"]
        .fillna(0)
        >= 100
    ).astype(int)

    return df


# ============================================================
# AGGREGATE TO ONE PLAYER
# ============================================================

def build_master_player_table():
    """
    Convert weekly NFL data into one row
    per fantasy-relevant player.
    """

    weekly_df = prepare_weekly_data()

    weekly_df = add_bonus_flags(
        weekly_df
    )

    master_df = (
        weekly_df
        .groupby(
            [
                "player_id",
                "player_name_clean",
                "position",
            ],
            as_index=False,
        )
        .agg(
            team=(
                "team",
                "last",
            ),

            games_played=(
                "week",
                "count",
            ),

            completions=(
                "completions",
                "sum",
            ),

            attempts=(
                "attempts",
                "sum",
            ),

            passing_yards=(
                "passing_yards",
                "sum",
            ),

            passing_tds=(
                "passing_tds",
                "sum",
            ),

            passing_interceptions=(
                "passing_interceptions",
                "sum",
            ),

            carries=(
                "carries",
                "sum",
            ),

            rushing_yards=(
                "rushing_yards",
                "sum",
            ),

            rushing_tds=(
                "rushing_tds",
                "sum",
            ),

            receptions=(
                "receptions",
                "sum",
            ),

            targets=(
                "targets",
                "sum",
            ),

            receiving_yards=(
                "receiving_yards",
                "sum",
            ),

            receiving_tds=(
                "receiving_tds",
                "sum",
            ),

            receiving_air_yards=(
                "receiving_air_yards",
                "sum",
            ),

            target_share=(
                "target_share",
                "mean",
            ),

            air_yards_share=(
                "air_yards_share",
                "mean",
            ),

            wopr=(
                "wopr",
                "mean",
            ),

            actual_ppr_points=(
                "fantasy_points_ppr",
                "sum",
            ),

            games_300_pass=(
                "game_300_pass",
                "sum",
            ),

            games_100_rush=(
                "game_100_rush",
                "sum",
            ),

            games_100_receive=(
                "game_100_receive",
                "sum",
            ),
        )
    )

    return master_df


def add_current_roster_identity(df):
    """
    Merge 2025 historical production with the current 2026 roster.

    Veterans keep their 2025 stats but receive current 2026
    team/position information.

    2026 players without 2025 stats are added to the player pool
    with zero historical production so rookies are not excluded.
    """

    historical_df = df.copy()

    roster_df = prepare_fantasy_rosters().copy()

    roster_df = roster_df.rename(
        columns={
            "gsis_id": "player_id",
            "player_name_clean": "roster_player_name",
            "team": "current_team",
            "position": "current_position",
        }
    )
    roster_columns = [
        "player_id",
        "roster_player_name",
        "current_team",
        "current_position",
        "status",
        "years_exp",
        "entry_year",
        "rookie_year",
        "draft_club",
        "draft_number",
        "is_rookie",
    ]

    roster_df = roster_df[roster_columns].copy()

    # Merge historical production with current roster identity.
    merged_df = historical_df.merge(
        roster_df,
        on="player_id",
        how="outer",
    )

    # Current roster identity is authoritative.
    merged_df["player_name_clean"] = (
        merged_df["roster_player_name"]
        .fillna(merged_df["player_name_clean"])
    )

    merged_df["team"] = (
        merged_df["current_team"]
        .fillna(merged_df["team"])
    )

    merged_df["position"] = (
        merged_df["current_position"]
        .fillna(merged_df["position"])
    )

    # New players/rookies have no 2025 production.
    # Fill numeric historical fields with zero.
    identity_columns = {
        "player_id",
        "player_name_clean",
        "team",
        "position",
        "roster_player_name",
        "current_team",
        "current_position",
        "status",
    }

    numeric_columns = [
        column
        for column in merged_df.columns
        if column not in identity_columns
        and merged_df[column].dtype.kind in "biufc"
    ]

    merged_df[numeric_columns] = (
        merged_df[numeric_columns]
        .fillna(0)
    )

    # Remove temporary merge fields.
    merged_df = merged_df.drop(
        columns=[
            "roster_player_name",
            "current_team",
            "current_position",
        ]
    )

    return merged_df




# ============================================================
# ADD EDGEIQ CALCULATED METRICS
# ============================================================

def add_calculated_metrics(df):
    """
    Add useful efficiency and scoring metrics.
    """

    df = df.copy()

    df["scrimmage_yards"] = (
        df["rushing_yards"]
        + df["receiving_yards"]
    )

    df["total_tds"] = (
        df["passing_tds"]
        + df["rushing_tds"]
        + df["receiving_tds"]
    )

    df["catch_rate"] = np.where(
        df["targets"] > 0,
        df["receptions"]
        / df["targets"],
        0,
    )

    df["yards_per_target"] = np.where(
        df["targets"] > 0,
        df["receiving_yards"]
        / df["targets"],
        0,
    )

    df["yards_per_carry"] = np.where(
        df["carries"] > 0,
        df["rushing_yards"]
        / df["carries"],
        0,
    )

    df["yards_per_reception"] = np.where(
        df["receptions"] > 0,
        df["receiving_yards"]
        / df["receptions"],
        0,
    )

    df["air_yards_per_target"] = np.where(
        df["targets"] > 0,
        df["receiving_air_yards"]
        / df["targets"],
        0,
    )

    df["ppr_points_per_game"] = np.where(
        df["games_played"] > 0,
        df["actual_ppr_points"]
        / df["games_played"],
        0,
    )

    return df


# ============================================================
# CALCULATE OUR LEAGUE'S 2025 FANTASY POINTS
# ============================================================

def add_custom_fantasy_scoring(df):
    """
    Calculate fantasy scoring using the user's
    keeper league scoring rules.
    """

    df = df.copy()

    df["custom_fantasy_points"] = (
        # PPR
        df["receptions"] * 1.0

        # Yardage
        + df["rushing_yards"] * 0.10
        + df["receiving_yards"] * 0.10
        + df["passing_yards"] * 0.04

        # Touchdowns
        + df["rushing_tds"] * 6
        + df["receiving_tds"] * 6
        + df["passing_tds"] * 4

        # Big-game bonuses
        + df["games_300_pass"] * 3
        + df["games_100_rush"] * 3
        + df["games_100_receive"] * 3
    )

    df["custom_points_per_game"] = np.where(
        df["games_played"] > 0,
        df["custom_fantasy_points"]
        / df["games_played"],
        0,
    )

    return df


# ============================================================
# CREATE MASTER TABLE
# ============================================================

def create_master_player_table():

    df = build_master_player_table()

    df = add_current_roster_identity(
        df
    )



    df = add_calculated_metrics(
        df
    )

    df = add_custom_fantasy_scoring(
        df
    )

    df = df.sort_values(
        by="custom_fantasy_points",
        ascending=False,
    ).reset_index(
        drop=True
    )

    return df





# ============================================================
# TEST
# ============================================================

def main():

    master_df = (
        create_master_player_table()
    )

    print(
        "\n=========================================="
    )

    print(
        "EDGEIQ MASTER PLAYER TABLE"
    )

    print(
        "==========================================\n"
    )

    display_columns = [
        "player_name_clean",
        "position",
        "team",
        "games_played",
        "targets",
        "receptions",
        "passing_yards",
        "rushing_yards",
        "receiving_yards",
        "games_300_pass",
        "games_100_rush",
        "games_100_receive",
        "custom_fantasy_points",
        "custom_points_per_game",
        "target_share",
        "air_yards_share",
        "wopr",
    ]

    print(
        master_df[
            display_columns
        ]
        .head(50)
        .round(2)
        .to_string(
            index=False
        )
    )

    print(
        f"\nTotal fantasy players: "
        f"{len(master_df):,}"
    )


if __name__ == "__main__":
    main()