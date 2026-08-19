import pandas as pd
import nflreadpy as nfl


CURRENT_SEASON = 2026

FANTASY_POSITIONS = [
    "QB",
    "RB",
    "WR",
    "TE",
]


def load_current_rosters():
    """
    Load current NFL roster information for EdgeIQ.

    This is used to attach current-season identity information
    to the historical statistics used by the projection engine.
    """

    print(
        f"\nLoading {CURRENT_SEASON} NFL rosters..."
    )

    rosters = nfl.load_rosters(
        seasons=[CURRENT_SEASON]
    )

    # nflreadpy currently returns a Polars DataFrame.
    # EdgeIQ uses pandas throughout the model.
    rosters = rosters.to_pandas()

    print(
        f"Downloaded {len(rosters):,} roster rows."
    )

    return rosters


def prepare_fantasy_rosters():
    """
    Clean the current NFL roster data and keep
    fantasy-relevant offensive players.
    """

    df = load_current_rosters()

    # Keep fantasy positions only
    df = df[
        df["position"].isin(FANTASY_POSITIONS)
    ].copy()

    # Keep the fields EdgeIQ needs
    columns = [
        "gsis_id",
        "espn_id",
        "sleeper_id",
        "full_name",
        "first_name",
        "last_name",
        "team",
        "position",
        "depth_chart_position",
        "status",
        "years_exp",
        "entry_year",
        "rookie_year",
        "draft_club",
        "draft_number",
    ]

    df = df[columns].copy()

    # EdgeIQ standard player-name field
    df["player_name_clean"] = (
        df["full_name"]
        .fillna("")
        .str.strip()
    )

    # Mark rookies
    df["is_rookie"] = (
        df["rookie_year"] == CURRENT_SEASON
    )

    # Remove duplicate roster records
    df = (
        df
        .drop_duplicates(
            subset=["gsis_id", "full_name"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return df


def main():

    df = prepare_fantasy_rosters()

    print(
        "\n============================================"
    )

    print(
        "EDGEIQ 2026 FANTASY ROSTERS"
    )

    print(
        "============================================\n"
    )

    display_columns = [
        "player_name_clean",
        "position",
        "team",
        "status",
        "years_exp",
        "is_rookie",
    ]

    print(
        df[
            display_columns
        ]
        .head(50)
        .to_string(index=False)
    )

    print(
        f"\nFantasy players loaded: {len(df):,}"
    )


if __name__ == "__main__":
    main()